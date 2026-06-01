from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summarize_training_run(*, config_path: str | Path, label: str = "") -> dict[str, Any]:
    errors: list[str] = []
    path = Path(config_path)
    config = _read_yaml_scalars(path, errors)
    checkpoint_dir = Path(config.get("output_dir", ""))
    checkpoint_exists = checkpoint_dir.exists() and checkpoint_dir.is_dir()
    if not checkpoint_exists:
        errors.append(f"Missing checkpoint directory from output_dir: {checkpoint_dir}")

    trainer_state_path = _find_trainer_state(checkpoint_dir)
    trainer_state: dict[str, Any] = {}
    if trainer_state_path is None:
        errors.append(f"Missing trainer_state.json under checkpoint directory: {checkpoint_dir}")
    else:
        trainer_state = _read_json(trainer_state_path, errors)

    log_history = trainer_state.get("log_history", [])
    if trainer_state and not isinstance(log_history, list):
        errors.append(f"trainer_state.json log_history must be a list: {trainer_state_path}")
        log_history = []
    if trainer_state and not log_history:
        errors.append(f"trainer_state.json has no log_history entries: {trainer_state_path}")

    return {
        "ok": not errors,
        "label": label,
        "config_path": str(path),
        "stage": config.get("stage", ""),
        "model_name_or_path": config.get("model_name_or_path", ""),
        "checkpoint_dir": str(checkpoint_dir),
        "checkpoint_exists": checkpoint_exists,
        "trainer_state_path": str(trainer_state_path) if trainer_state_path else "",
        "global_step": trainer_state.get("global_step", 0),
        "best_metric": trainer_state.get("best_metric"),
        "best_model_checkpoint": trainer_state.get("best_model_checkpoint", ""),
        "log_history_count": len(log_history),
        "last_metrics": dict(log_history[-1]) if log_history else {},
        "last_train_loss": _last_metric(log_history, "loss"),
        "last_eval_loss": _last_metric(log_history, "eval_loss"),
        "errors": errors,
    }


def _read_yaml_scalars(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.exists():
        errors.append(f"Missing config file: {path}")
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def _find_trainer_state(checkpoint_dir: Path) -> Path | None:
    direct = checkpoint_dir / "trainer_state.json"
    if direct.exists():
        return direct
    if not checkpoint_dir.exists():
        return None
    candidates = sorted(checkpoint_dir.glob("checkpoint-*/trainer_state.json"), key=lambda item: item.stat().st_mtime)
    return candidates[-1] if candidates else None


def _read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON at {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object at {path}")
        return {}
    return data


def _last_metric(log_history: list[Any], key: str) -> float | None:
    for item in reversed(log_history):
        if isinstance(item, dict) and key in item:
            try:
                return float(item[key])
            except (TypeError, ValueError):
                return None
    return None
