from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from safetensors.torch import load_file
from transformers import AutoTokenizer
from trl import AutoModelForCausalLMWithValueHead


class ScoreRequest(BaseModel):
    prompt: str
    answer: str


@dataclass(frozen=True)
class ServiceConfig:
    run_id: str
    base_model_path: str
    checkpoint_path: str
    host: str
    port: int
    max_length: int
    dtype: str
    device_map: str


class VerifierScorer:
    def __init__(self, cfg: ServiceConfig) -> None:
        self.cfg = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(cfg.checkpoint_path, trust_remote_code=False)
        dtype = torch.bfloat16 if cfg.dtype == "bfloat16" else torch.float16
        self.model = AutoModelForCausalLMWithValueHead.from_pretrained(
            cfg.checkpoint_path,
            dtype=dtype,
            device_map=cfg.device_map,
        )
        value_head_path = Path(cfg.checkpoint_path) / "value_head.safetensors"
        if not value_head_path.exists():
            raise FileNotFoundError(f"missing value head: {value_head_path}")
        state = load_file(str(value_head_path))
        self.model.v_head.load_state_dict({key.removeprefix("v_head."): value for key, value in state.items()})
        self.model.eval()

    @property
    def device(self) -> torch.device:
        return self.model.pretrained_model.device

    def score(self, prompt: str, answer: str) -> float:
        text = self.tokenizer.apply_chat_template(
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ],
            tokenize=False,
            add_generation_prompt=False,
        )
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.cfg.max_length,
        ).to(self.device)
        with torch.no_grad():
            output = self.model(**inputs, return_dict=True)
        values = output[-1] if isinstance(output, tuple) else output.value
        return float(values[0, -1].float().item())


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a LLaMA-Factory/TRL value-head verifier over HTTP.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = _load_config(Path(args.config))
    metadata = {
        "run_id": cfg.run_id,
        "config_path": args.config,
        "base_model_path": cfg.base_model_path,
        "checkpoint_path": cfg.checkpoint_path,
        "host": cfg.host,
        "port": cfg.port,
        "max_length": cfg.max_length,
        "dtype": cfg.dtype,
        "device_map": cfg.device_map,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
    }
    if args.dry_run:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0

    os.environ.setdefault("NCCL_P2P_DISABLE", "1")
    os.environ.setdefault("NCCL_IB_DISABLE", "1")
    scorer = VerifierScorer(cfg)
    app = FastAPI(title="TTC verifier scorer")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {**metadata, "device": str(scorer.device), "ok": True}

    @app.post("/score")
    def score(request: ScoreRequest) -> dict[str, Any]:
        value = scorer.score(request.prompt, request.answer)
        return {"score": value, "run_id": cfg.run_id}

    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")
    return 0


def _load_config(path: Path) -> ServiceConfig:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    service = data["service"]
    model = data["model"]
    return ServiceConfig(
        run_id=str(data["run_id"]),
        base_model_path=str(model["base_model_path"]),
        checkpoint_path=str(model["checkpoint_path"]),
        host=str(service.get("host", "0.0.0.0")),
        port=int(service.get("port", 8001)),
        max_length=int(service.get("max_length", 2048)),
        dtype=str(service.get("dtype", "bfloat16")),
        device_map=str(service.get("device_map", "auto")),
    )


def _git_commit() -> str:
    if not Path(".git/HEAD").exists():
        return "not-a-git-checkout"
    return os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())

