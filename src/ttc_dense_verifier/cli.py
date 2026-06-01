from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Sequence

from ttc_dense_verifier.data_pipeline.preference import build_preference_pairs, split_by_prompt_id
from ttc_dense_verifier.data_pipeline.generation_prompts import build_generation_requests
from ttc_dense_verifier.data_pipeline.records import AnswerRecord, PromptRecord
from ttc_dense_verifier.data_pipeline.taxonomy import build_taxonomy_prompts
from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.decoding.mcts import MCTSConfig
from ttc_dense_verifier.demo.static_site import write_demo_page
from ttc_dense_verifier.evaluation.code_guardrail import (
    build_code_guardrail_prompts,
    evaluate_code_guardrail_outputs,
)
from ttc_dense_verifier.evaluation.figures import write_paper_figures
from ttc_dense_verifier.evaluation.metrics import compute_text_metrics, summarize_metrics
from ttc_dense_verifier.evaluation.judge import build_judge_requests
from ttc_dense_verifier.evaluation.reports import (
    build_error_breakdown,
    build_human_preference_table,
    build_human_review_rows,
    build_latency_table,
    build_overall_table,
    write_csv,
)
from ttc_dense_verifier.inference.artifacts import build_inference_record
from ttc_dense_verifier.inference.decode import decode_prompts
from ttc_dense_verifier.remote.plan import write_remote_runbook
from ttc_dense_verifier.serving.batch import run_generation_requests, score_preference_pairs
from ttc_dense_verifier.serving.clients import (
    Candidate,
    HTTPVerifierClient,
    OpenAICompatibleGeneratorClient,
    RuleBasedVerifierClient,
    ScriptedGeneratorClient,
)
from ttc_dense_verifier.serving.health import probe_remote_services
from ttc_dense_verifier.training.reward_dataset import build_dataset_info as build_rm_dataset_info
from ttc_dense_verifier.training.reward_dataset import to_reward_model_record
from ttc_dense_verifier.training.run_summary import summarize_training_run
from ttc_dense_verifier.training.sft_dataset import build_dataset_info as build_sft_dataset_info
from ttc_dense_verifier.training.sft_dataset import to_sft_record
from ttc_dense_verifier.training.input_validation import validate_training_inputs
from ttc_dense_verifier.training.validation import validate_verifier_scores
from ttc_dense_verifier.utils.jsonl import read_jsonl, write_jsonl
from ttc_dense_verifier.workflow.local_smoke import run_local_smoke


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ttc-verifier")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_questions = subparsers.add_parser("build-questions", help="Write deterministic C/system taxonomy prompts.")
    build_questions.add_argument("--output", required=True)
    build_questions.add_argument("--limit", type=int, default=5000)

    generation_requests = subparsers.add_parser(
        "build-generation-requests",
        help="Render positive or negative answer-generation requests for remote model jobs.",
    )
    generation_requests.add_argument("--questions", required=True)
    generation_requests.add_argument("--mode", choices=["negative", "positive"], required=True)
    generation_requests.add_argument("--model", required=True)
    generation_requests.add_argument("--output", required=True)

    run_generation = subparsers.add_parser(
        "run-generation-requests",
        help="Run answer-generation requests through a remote endpoint or scripted local smoke response.",
    )
    run_generation.add_argument("--input", required=True)
    run_generation.add_argument("--output", required=True)
    run_generation.add_argument("--endpoint")
    run_generation.add_argument("--model", default="remote-model")
    run_generation.add_argument("--api-key")
    run_generation.add_argument("--scripted-answer")

    prepare = subparsers.add_parser("prepare-preferences", help="Build preference splits from aligned JSONL files.")
    prepare.add_argument("--questions", required=True)
    prepare.add_argument("--positive", required=True)
    prepare.add_argument("--negative", required=True)
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--seed", type=int, default=13)

    evaluate = subparsers.add_parser("evaluate-static", help="Compute static metrics for generation outputs.")
    evaluate.add_argument("--input", required=True)
    evaluate.add_argument("--output-dir", required=True)

    build_guardrail = subparsers.add_parser(
        "build-code-guardrail",
        help="Write a small C/system code-ability guardrail prompt set.",
    )
    build_guardrail.add_argument("--output", required=True)
    build_guardrail.add_argument("--limit", type=int, default=30)

    eval_guardrail = subparsers.add_parser(
        "evaluate-code-guardrail",
        help="Evaluate generated answers against the C/system code-ability guardrail.",
    )
    eval_guardrail.add_argument("--prompts", required=True)
    eval_guardrail.add_argument("--outputs", required=True)
    eval_guardrail.add_argument("--output-dir", required=True)

    demo = subparsers.add_parser("decode-demo", help="Run an offline TTC Beam Search demo with scripted candidates.")
    demo.add_argument("--prompts", required=True)
    demo.add_argument("--output", required=True)
    demo.add_argument("--limit", type=int, default=5)

    decode_ttc = subparsers.add_parser(
        "decode-ttc",
        help="Run TTC Beam or MCTS decoding with scripted smoke clients or remote endpoints.",
    )
    decode_ttc.add_argument("--prompts", required=True)
    decode_ttc.add_argument("--output", required=True)
    decode_ttc.add_argument("--method", choices=["beam", "mcts"], required=True)
    decode_ttc.add_argument("--limit", type=int)
    decode_ttc.add_argument("--scripted", action="store_true")
    decode_ttc.add_argument("--generator-endpoint")
    decode_ttc.add_argument("--generator-model", default="remote-generator")
    decode_ttc.add_argument("--verifier-endpoint")
    decode_ttc.add_argument("--verifier-model", default="remote-verifier")
    decode_ttc.add_argument("--api-key")
    decode_ttc.add_argument("--good-answer", default="State assumptions and boundary conditions before giving a concise technical example.")
    decode_ttc.add_argument("--bad-answer", default=">>> Shallow slogan answer ===>")
    decode_ttc.add_argument("--reward-keyword", action="append", default=[])
    decode_ttc.add_argument("--penalty-keyword", action="append", default=[])
    decode_ttc.add_argument("--beam-width", type=int, default=4)
    decode_ttc.add_argument("--expansions", type=int, default=4)
    decode_ttc.add_argument("--max-steps", type=int, default=8)
    decode_ttc.add_argument("--simulation-budget", type=int, default=32)
    decode_ttc.add_argument("--beta", type=float, default=1.0)

    rm_export = subparsers.add_parser(
        "export-rm-dataset",
        help="Convert preference splits to reward-model training JSONL and dataset_info.json.",
    )
    rm_export.add_argument("--train", required=True)
    rm_export.add_argument("--val", required=True)
    rm_export.add_argument("--output-dir", required=True)
    rm_export.add_argument("--dataset-name", default="ttc_rm")

    sft_export = subparsers.add_parser(
        "export-sft-dataset",
        help="Export positive chosen answers as an SFT baseline dataset.",
    )
    sft_export.add_argument("--input", required=True)
    sft_export.add_argument("--output", required=True)

    verifier_validation = subparsers.add_parser(
        "validate-verifier-scores",
        help="Validate verifier chosen/rejected score ordering from JSONL scores.",
    )
    verifier_validation.add_argument("--input", required=True)
    verifier_validation.add_argument("--output", required=True)
    verifier_validation.add_argument("--min-pairwise-accuracy", type=float, default=0.65)

    training_inputs = subparsers.add_parser(
        "validate-training-inputs",
        help="Dry-run validate LLaMA-Factory training configs, dataset_info.json, and JSONL columns.",
    )
    training_inputs.add_argument("--rm-config", required=True)
    training_inputs.add_argument("--sft-config", required=True)
    training_inputs.add_argument("--rm-dataset-dir", required=True)
    training_inputs.add_argument("--sft-dataset-dir", required=True)
    training_inputs.add_argument("--output", required=True)

    training_summary = subparsers.add_parser(
        "export-training-summary",
        help="Summarize LLaMA-Factory trainer_state.json and checkpoint output without loading models.",
    )
    training_summary.add_argument("--config", required=True)
    training_summary.add_argument("--output", required=True)
    training_summary.add_argument("--label", default="")

    score_preferences = subparsers.add_parser(
        "score-preferences",
        help="Score preference pairs with a remote verifier endpoint or local rule-based smoke verifier.",
    )
    score_preferences.add_argument("--input", required=True)
    score_preferences.add_argument("--output", required=True)
    score_preferences.add_argument("--endpoint")
    score_preferences.add_argument("--api-key")
    score_preferences.add_argument("--reward-keyword", action="append", default=[])
    score_preferences.add_argument("--penalty-keyword", action="append", default=[])

    remote_probe = subparsers.add_parser(
        "probe-remote-services",
        help="Probe remote generator and verifier endpoints with one tiny request each.",
    )
    remote_probe.add_argument("--generator-endpoint", required=True)
    remote_probe.add_argument("--generator-model", required=True)
    remote_probe.add_argument("--verifier-endpoint", required=True)
    remote_probe.add_argument("--api-key")
    remote_probe.add_argument("--timeout-seconds", type=float, default=10.0)
    remote_probe.add_argument("--output", required=True)

    eval_assets = subparsers.add_parser(
        "export-evaluation-assets",
        help="Export paper tables, judge requests, and human-review CSV from inference outputs.",
    )
    eval_assets.add_argument("--input", required=True)
    eval_assets.add_argument("--output-dir", required=True)
    eval_assets.add_argument("--judge-model", required=True)

    human_preference = subparsers.add_parser(
        "export-human-preference-table",
        help="Aggregate completed human-review CSV rows into paper Table 4.",
    )
    human_preference.add_argument("--input", required=True)
    human_preference.add_argument("--output", required=True)

    paper_figures = subparsers.add_parser(
        "export-paper-figures",
        help="Export paper-ready Figure 1-4 source artifacts from inference logs.",
    )
    paper_figures.add_argument("--input", required=True)
    paper_figures.add_argument("--output-dir", required=True)

    demo_page = subparsers.add_parser(
        "export-demo-page",
        help="Render a self-contained HTML page from TTC inference logs.",
    )
    demo_page.add_argument("--input", required=True)
    demo_page.add_argument("--output", required=True)
    demo_page.add_argument("--title", default="TTC Dense Verifier Demo")

    remote_runbook = subparsers.add_parser(
        "export-remote-runbook",
        help="Write remote health-check and tmux runbook scripts without executing them.",
    )
    remote_runbook.add_argument("--output-dir", required=True)
    remote_runbook.add_argument("--remote-project-dir", required=True)

    local_smoke = subparsers.add_parser(
        "run-local-smoke",
        help="Run a local scripted end-to-end smoke workflow without model downloads or network calls.",
    )
    local_smoke.add_argument("--output-dir", required=True)
    local_smoke.add_argument("--limit", type=int, default=12)

    args = parser.parse_args(argv)
    if args.command == "build-questions":
        return _build_questions(args)
    if args.command == "build-generation-requests":
        return _build_generation_requests(args)
    if args.command == "run-generation-requests":
        return _run_generation_requests(args)
    if args.command == "prepare-preferences":
        return _prepare_preferences(args)
    if args.command == "evaluate-static":
        return _evaluate_static(args)
    if args.command == "build-code-guardrail":
        return _build_code_guardrail(args)
    if args.command == "evaluate-code-guardrail":
        return _evaluate_code_guardrail(args)
    if args.command == "decode-demo":
        return _decode_demo(args)
    if args.command == "decode-ttc":
        return _decode_ttc(args)
    if args.command == "export-rm-dataset":
        return _export_rm_dataset(args)
    if args.command == "export-sft-dataset":
        return _export_sft_dataset(args)
    if args.command == "validate-verifier-scores":
        return _validate_verifier_scores(args)
    if args.command == "validate-training-inputs":
        return _validate_training_inputs(args)
    if args.command == "export-training-summary":
        return _export_training_summary(args)
    if args.command == "score-preferences":
        return _score_preferences(args)
    if args.command == "probe-remote-services":
        return _probe_remote_services(args)
    if args.command == "export-evaluation-assets":
        return _export_evaluation_assets(args)
    if args.command == "export-human-preference-table":
        return _export_human_preference_table(args)
    if args.command == "export-paper-figures":
        return _export_paper_figures(args)
    if args.command == "export-demo-page":
        return _export_demo_page(args)
    if args.command == "export-remote-runbook":
        return _export_remote_runbook(args)
    if args.command == "run-local-smoke":
        return _run_local_smoke(args)
    parser.error(f"Unknown command: {args.command}")
    return 2


def _build_questions(args: argparse.Namespace) -> int:
    prompts = build_taxonomy_prompts(limit=args.limit)
    write_jsonl(args.output, prompts)
    return 0


def _build_generation_requests(args: argparse.Namespace) -> int:
    prompts = [PromptRecord.from_dict(record) for record in read_jsonl(args.questions)]
    requests = build_generation_requests(prompts, mode=args.mode, model=args.model)
    write_jsonl(args.output, requests)
    return 0


def _run_generation_requests(args: argparse.Namespace) -> int:
    requests = read_jsonl(args.input)
    if args.scripted_answer is not None:
        generator = ScriptedGeneratorClient({"": [Candidate(text=args.scripted_answer, logprob=0.0, is_complete=True)]})
    else:
        if not args.endpoint:
            raise SystemExit("--endpoint is required unless --scripted-answer is provided")
        generator = OpenAICompatibleGeneratorClient(args.endpoint, model=args.model, api_key=args.api_key)
    write_jsonl(args.output, run_generation_requests(requests, generator=generator))
    return 0


def _prepare_preferences(args: argparse.Namespace) -> int:
    prompts = [PromptRecord.from_dict(record) for record in read_jsonl(args.questions)]
    chosen = [AnswerRecord.from_dict(record) for record in read_jsonl(args.positive)]
    rejected = [AnswerRecord.from_dict(record) for record in read_jsonl(args.negative)]
    pairs, report = build_preference_pairs(prompts, chosen, rejected)
    splits = split_by_prompt_id(pairs, seed=args.seed)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "train_preference.jsonl", splits["train"])
    write_jsonl(output_dir / "val_preference.jsonl", splits["val"])
    test_prompts = [
        {
            "prompt_id": record["prompt_id"],
            "prompt": record["prompt"],
            "metadata": record.get("metadata", {}),
        }
        for record in splits["test"]
    ]
    write_jsonl(output_dir / "test_prompts.jsonl", test_prompts)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data_report.md").write_text(report.to_markdown(), encoding="utf-8")
    return 0


def _evaluate_static(args: argparse.Namespace) -> int:
    rows = []
    for record in read_jsonl(args.input):
        answer = str(record.get("answer", record.get("final_answer", "")))
        metrics = compute_text_metrics(answer)
        row = {
            "prompt_id": record.get("prompt_id"),
            "method": record.get("method", "unknown"),
            "metrics": metrics,
        }
        rows.append(row)

    output_dir = Path(args.output_dir)
    write_jsonl(output_dir / "static_metrics.jsonl", rows)
    summary = summarize_metrics(rows)
    (output_dir / "static_metrics_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def _build_code_guardrail(args: argparse.Namespace) -> int:
    write_jsonl(args.output, build_code_guardrail_prompts(limit=args.limit))
    return 0


def _evaluate_code_guardrail(args: argparse.Namespace) -> int:
    details, summary = evaluate_code_guardrail_outputs(read_jsonl(args.outputs), read_jsonl(args.prompts))
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "code_guardrail_details.csv", details)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "code_guardrail_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def _decode_demo(args: argparse.Namespace) -> int:
    rows = read_jsonl(args.prompts)[: args.limit]
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
    output_records = []
    for index, row in enumerate(rows, start=1):
        prompt_id = str(row.get("prompt_id", f"demo-{index:06d}"))
        prompt = str(row["prompt"])
        result = decoder.decode(prompt)
        output_records.append(
            build_inference_record(
                prompt_id=prompt_id,
                prompt=prompt,
                result=result,
                generator_model="scripted-demo-generator",
                verifier_model="rule-based-demo-verifier",
            )
        )
    write_jsonl(args.output, output_records)
    return 0


def _decode_ttc(args: argparse.Namespace) -> int:
    prompts = read_jsonl(args.prompts)
    if args.scripted:
        generator = ScriptedGeneratorClient(
            {
                "": [
                    (args.bad_answer, -0.1, True),
                    (args.good_answer, -0.3, True),
                ]
            }
        )
        verifier = RuleBasedVerifierClient(
            reward_keywords=list(args.reward_keyword) or ["assumptions", "boundary", "technical", "example"],
            penalty_keywords=list(args.penalty_keyword) or [">>>", "slogan", "===>"],
        )
        generator_model = "scripted-ttc-generator"
        verifier_model = "rule-based-ttc-verifier"
    else:
        if not args.generator_endpoint or not args.verifier_endpoint:
            raise SystemExit("--generator-endpoint and --verifier-endpoint are required unless --scripted is provided")
        generator = OpenAICompatibleGeneratorClient(
            args.generator_endpoint,
            model=args.generator_model,
            api_key=args.api_key,
        )
        verifier = HTTPVerifierClient(args.verifier_endpoint, api_key=args.api_key)
        generator_model = args.generator_model
        verifier_model = args.verifier_model

    records = decode_prompts(
        prompts,
        method=args.method,
        generator=generator,
        verifier=verifier,
        generator_model=generator_model,
        verifier_model=verifier_model,
        limit=args.limit,
        beam_config=BeamSearchConfig(
            beam_width=args.beam_width,
            expansions_per_step=args.expansions,
            beta=args.beta,
            max_steps=args.max_steps,
        ),
        mcts_config=MCTSConfig(
            expansions_per_node=args.expansions,
            simulation_budget=args.simulation_budget,
            beta=args.beta,
        ),
    )
    write_jsonl(args.output, records)
    return 0


def _export_rm_dataset(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    train_file = "train_rm.jsonl"
    val_file = "val_rm.jsonl"
    train_records = [to_reward_model_record(pair) for pair in read_jsonl(args.train)]
    val_records = [to_reward_model_record(pair) for pair in read_jsonl(args.val)]
    write_jsonl(output_dir / train_file, train_records)
    write_jsonl(output_dir / val_file, val_records)
    dataset_info = build_rm_dataset_info(args.dataset_name, train_file, val_file)
    (output_dir / "dataset_info.json").write_text(
        json.dumps(dataset_info, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def _export_sft_dataset(args: argparse.Namespace) -> int:
    output = Path(args.output)
    write_jsonl(output, [to_sft_record(pair) for pair in read_jsonl(args.input)])
    dataset_info = build_sft_dataset_info("ttc_sft", output.name)
    (output.parent / "dataset_info.json").write_text(
        json.dumps(dataset_info, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return 0


def _validate_verifier_scores(args: argparse.Namespace) -> int:
    report = validate_verifier_scores(
        read_jsonl(args.input),
        min_pairwise_accuracy=args.min_pairwise_accuracy,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return 0


def _validate_training_inputs(args: argparse.Namespace) -> int:
    report = validate_training_inputs(
        rm_config=args.rm_config,
        sft_config=args.sft_config,
        rm_dataset_dir=args.rm_dataset_dir,
        sft_dataset_dir=args.sft_dataset_dir,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(1)
    return 0


def _export_training_summary(args: argparse.Namespace) -> int:
    report = summarize_training_run(config_path=args.config, label=args.label)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(1)
    return 0


def _score_preferences(args: argparse.Namespace) -> int:
    if args.endpoint:
        verifier = HTTPVerifierClient(args.endpoint, api_key=args.api_key)
    else:
        verifier = RuleBasedVerifierClient(
            reward_keywords=list(args.reward_keyword),
            penalty_keywords=list(args.penalty_keyword),
        )
    write_jsonl(args.output, score_preference_pairs(read_jsonl(args.input), verifier=verifier))
    return 0


def _probe_remote_services(args: argparse.Namespace) -> int:
    report = probe_remote_services(
        generator_endpoint=args.generator_endpoint,
        generator_model=args.generator_model,
        verifier_endpoint=args.verifier_endpoint,
        api_key=args.api_key,
        timeout_seconds=args.timeout_seconds,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(1)
    return 0


def _export_evaluation_assets(args: argparse.Namespace) -> int:
    rows = read_jsonl(args.input)
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "table1_overall_metrics.csv", build_overall_table(rows))
    write_csv(output_dir / "table2_error_breakdown.csv", build_error_breakdown(rows))
    write_csv(output_dir / "table3_latency_cost.csv", build_latency_table(rows))
    write_csv(output_dir / "human_review.csv", build_human_review_rows(rows))
    write_jsonl(output_dir / "judge_requests.jsonl", build_judge_requests(rows, judge_model=args.judge_model))
    return 0


def _export_human_preference_table(args: argparse.Namespace) -> int:
    with Path(args.input).open("r", encoding="utf-8", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    write_csv(args.output, build_human_preference_table(review_rows))
    return 0


def _export_paper_figures(args: argparse.Namespace) -> int:
    write_paper_figures(args.output_dir, read_jsonl(args.input))
    return 0


def _export_demo_page(args: argparse.Namespace) -> int:
    records = read_jsonl(args.input)
    write_demo_page(args.output, records, title=args.title)
    return 0


def _export_remote_runbook(args: argparse.Namespace) -> int:
    write_remote_runbook(args.output_dir, remote_project_dir=args.remote_project_dir)
    return 0


def _run_local_smoke(args: argparse.Namespace) -> int:
    run_local_smoke(args.output_dir, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
