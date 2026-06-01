from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ttc_dense_verifier.data_pipeline.generation_prompts import build_generation_requests
from ttc_dense_verifier.data_pipeline.preference import build_preference_pairs, split_by_prompt_id
from ttc_dense_verifier.data_pipeline.records import AnswerRecord, PromptRecord
from ttc_dense_verifier.data_pipeline.taxonomy import build_taxonomy_prompts
from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.demo.static_site import write_demo_page
from ttc_dense_verifier.evaluation.judge import build_judge_requests
from ttc_dense_verifier.evaluation.reports import (
    build_error_breakdown,
    build_human_review_rows,
    build_latency_table,
    build_overall_table,
    write_csv,
)
from ttc_dense_verifier.inference.artifacts import build_inference_record
from ttc_dense_verifier.serving.batch import run_generation_requests, score_preference_pairs
from ttc_dense_verifier.serving.clients import Candidate, RuleBasedVerifierClient, ScriptedGeneratorClient
from ttc_dense_verifier.training.reward_dataset import build_dataset_info, to_reward_model_record
from ttc_dense_verifier.training.sft_dataset import build_dataset_info as build_sft_dataset_info
from ttc_dense_verifier.training.sft_dataset import to_sft_record
from ttc_dense_verifier.training.validation import validate_verifier_scores
from ttc_dense_verifier.utils.jsonl import write_jsonl


def run_local_smoke(output_dir: str | Path, *, limit: int = 12) -> dict[str, Any]:
    if limit < 3:
        raise ValueError("limit must be at least 3 so train/val/test splits can be created")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    artifacts = _artifact_paths(root)

    prompts = build_taxonomy_prompts(limit=limit)
    write_jsonl(artifacts["questions"], prompts)

    positive_requests = build_generation_requests(prompts, mode="positive", model="scripted-positive-generator")
    negative_requests = build_generation_requests(prompts, mode="negative", model="scripted-negative-generator")
    write_jsonl(artifacts["positive_requests"], positive_requests)
    write_jsonl(artifacts["negative_requests"], negative_requests)

    positive_answers = run_generation_requests(
        positive_requests,
        generator=ScriptedGeneratorClient(
            {"": [Candidate("State assumptions, explain boundary conditions, and give a concise technical example.", 0.0, True)]}
        ),
    )
    negative_answers = run_generation_requests(
        negative_requests,
        generator=ScriptedGeneratorClient(
            {"": [Candidate(">>> Shallow slogan answer with unsupported claims ===>", 0.0, True)]}
        ),
    )
    write_jsonl(artifacts["positive_answers"], positive_answers)
    write_jsonl(artifacts["negative_answers"], negative_answers)

    pairs, report = build_preference_pairs(
        prompts,
        [AnswerRecord.from_dict(record) for record in positive_answers],
        [AnswerRecord.from_dict(record) for record in negative_answers],
    )
    splits = split_by_prompt_id(pairs, seed=7)
    write_jsonl(artifacts["train_preference"], splits["train"])
    write_jsonl(artifacts["val_preference"], splits["val"])
    write_jsonl(
        artifacts["test_prompts"],
        [
            {
                "prompt_id": record["prompt_id"],
                "prompt": record["prompt"],
                "metadata": record.get("metadata", {}),
            }
            for record in splits["test"]
        ],
    )
    artifacts["data_report"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["data_report"].write_text(report.to_markdown(), encoding="utf-8")

    _write_training_exports(artifacts, splits)
    score_rows = _write_verifier_scores(artifacts, [pair.to_dict() for pair in pairs])
    demo_rows = _write_demo_outputs(artifacts, splits["test"])
    _write_evaluation_assets(artifacts, demo_rows)

    manifest = {
        "mode": "local_smoke",
        "uses_scripted_model_outputs": True,
        "downloads_models": False,
        "prompt_count": len(prompts),
        "preference_pair_count": len(pairs),
        "verifier_score_count": len(score_rows),
        "demo_output_count": len(demo_rows),
        "artifacts": {name: str(path) for name, path in artifacts.items()},
    }
    artifacts["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def _artifact_paths(root: Path) -> dict[str, Path]:
    return {
        "manifest": root / "manifest.json",
        "questions": root / "data/raw_questions/questions.jsonl",
        "positive_requests": root / "data/generated_positive/positive_generation_requests.jsonl",
        "negative_requests": root / "data/generated_negative/negative_generation_requests.jsonl",
        "positive_answers": root / "data/generated_positive/positive_answers.jsonl",
        "negative_answers": root / "data/generated_negative/negative_answers.jsonl",
        "train_preference": root / "data/preference/train_preference.jsonl",
        "val_preference": root / "data/preference/val_preference.jsonl",
        "test_prompts": root / "data/preference/test_prompts.jsonl",
        "data_report": root / "data/preference/data_report.md",
        "train_rm": root / "data/training/train_rm.jsonl",
        "val_rm": root / "data/training/val_rm.jsonl",
        "dataset_info": root / "data/training/dataset_info.json",
        "train_sft": root / "data/training/train_sft.jsonl",
        "sft_dataset_info": root / "data/training/dataset_info_sft.json",
        "verifier_scores": root / "outputs/logs/verifier_scores.jsonl",
        "verifier_report": root / "outputs/logs/verifier_report.json",
        "demo_outputs": root / "outputs/demo_cases/demo_ttc_beam_outputs.jsonl",
        "demo_page": root / "outputs/demo_cases/ttc_demo.html",
        "overall_table": root / "outputs/tables/table1_overall_metrics.csv",
        "error_table": root / "outputs/tables/table2_error_breakdown.csv",
        "latency_table": root / "outputs/tables/table3_latency_cost.csv",
        "human_review": root / "outputs/tables/human_review.csv",
        "judge_requests": root / "outputs/tables/judge_requests.jsonl",
    }


def _write_training_exports(artifacts: dict[str, Path], splits: dict[str, list[dict[str, Any]]]) -> None:
    write_jsonl(artifacts["train_rm"], [to_reward_model_record(pair) for pair in splits["train"]])
    write_jsonl(artifacts["val_rm"], [to_reward_model_record(pair) for pair in splits["val"]])
    artifacts["dataset_info"].write_text(
        json.dumps(build_dataset_info("ttc_rm", "train_rm.jsonl", "val_rm.jsonl"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_jsonl(artifacts["train_sft"], [to_sft_record(pair) for pair in splits["train"]])
    artifacts["sft_dataset_info"].write_text(
        json.dumps(build_sft_dataset_info("ttc_sft", "train_sft.jsonl"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_verifier_scores(artifacts: dict[str, Path], pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verifier = RuleBasedVerifierClient(
        reward_keywords=["assumptions", "boundary", "technical", "example"],
        penalty_keywords=[">>>", "slogan", "unsupported", "===>"],
    )
    score_rows = score_preference_pairs(pairs, verifier=verifier)
    write_jsonl(artifacts["verifier_scores"], score_rows)
    report = validate_verifier_scores(score_rows)
    artifacts["verifier_report"].parent.mkdir(parents=True, exist_ok=True)
    artifacts["verifier_report"].write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return score_rows


def _write_demo_outputs(artifacts: dict[str, Path], test_prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decoder = BeamSearchTTC(
        generator=ScriptedGeneratorClient(
            {
                "": [
                    (" >>> This is a revolutionary answer ===> trust it.", -0.1, True),
                    (
                        " State assumptions first, explain the boundary conditions, and give a concise technical example.",
                        -0.3,
                        True,
                    ),
                ]
            }
        ),
        verifier=RuleBasedVerifierClient(
            reward_keywords=["assumptions", "boundary", "technical", "example"],
            penalty_keywords=[">>>", "===>", "revolutionary", "trust it"],
        ),
        config=BeamSearchConfig(beam_width=1, expansions_per_step=2, beta=2.0, max_steps=1),
    )
    demo_rows = []
    for row in test_prompts:
        result = decoder.decode(str(row["prompt"]))
        demo_rows.append(
            build_inference_record(
                prompt_id=str(row["prompt_id"]),
                prompt=str(row["prompt"]),
                result=result,
                generator_model="scripted-demo-generator",
                verifier_model="rule-based-demo-verifier",
            )
        )
    write_jsonl(artifacts["demo_outputs"], demo_rows)
    write_demo_page(artifacts["demo_page"], demo_rows)
    return demo_rows


def _write_evaluation_assets(artifacts: dict[str, Path], demo_rows: list[dict[str, Any]]) -> None:
    write_csv(artifacts["overall_table"], build_overall_table(demo_rows))
    write_csv(artifacts["error_table"], build_error_breakdown(demo_rows))
    write_csv(artifacts["latency_table"], build_latency_table(demo_rows))
    write_csv(artifacts["human_review"], build_human_review_rows(demo_rows))
    write_jsonl(artifacts["judge_requests"], build_judge_requests(demo_rows, judge_model="local-smoke-judge-placeholder"))
