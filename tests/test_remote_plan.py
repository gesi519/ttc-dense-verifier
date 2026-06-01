import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.remote.plan import (
    build_remote_jobs,
    render_env_check_script,
    render_health_check_script,
    render_runbook_script,
    render_generator_service_script,
    render_verifier_service_script,
    render_switch_verifier_script,
    write_remote_runbook,
)


class RemotePlanTests(unittest.TestCase):
    def test_build_remote_jobs_covers_workflow_long_running_jobs(self):
        jobs = build_remote_jobs(remote_project_dir="/srv/ttc")
        names = [job["name"] for job in jobs]

        self.assertEqual(
            names,
            [
                "prompt_expansion",
                "negative_request_render",
                "negative_answer_generation",
                "positive_request_render",
                "positive_answer_generation",
                "preference_split_export",
                "rm_dataset_export",
                "sft_dataset_export",
                "training_input_validation",
                "verifier_rm_training",
                "generator_sft_lora_training",
                "trained_verifier_service_switch",
                "verifier_validation_scoring",
                "verifier_score_validation",
                "ttc_beam_inference",
                "ttc_mcts_inference",
                "evaluation_export",
            ],
        )
        self.assertTrue(all(job["log_path"].startswith("/srv/ttc/outputs/logs/") for job in jobs))
        self.assertTrue(all(job["config_path"] for job in jobs))
        self.assertTrue(all(job["output_paths"] for job in jobs))
        self.assertIn("configs/training/verifier_rm_qwen7b.yaml", jobs[9]["config_path"])
        self.assertIn("run-generation-requests", jobs[2]["command"])
        self.assertEqual(jobs[2]["config_path"], "configs/data_generation/negative_generation.yaml")
        self.assertIn("prepare-preferences", jobs[5]["command"])
        self.assertIn("export-rm-dataset", jobs[6]["command"])
        self.assertIn("export-sft-dataset", jobs[7]["command"])
        self.assertIn("data/training/sft/dataset_info.json", jobs[7]["output_paths"])
        self.assertIn("validate-training-inputs", jobs[8]["command"])
        self.assertIn("outputs/logs/training_input_validation_${TTC_RUN_ID}.json", jobs[8]["output_paths"])
        self.assertEqual(jobs[0]["phase"], "data_prepare")
        self.assertEqual(jobs[8]["phase"], "training_validation")
        self.assertEqual(jobs[9]["phase"], "training")
        self.assertIn("export-training-summary", jobs[9]["command"])
        self.assertIn("outputs/logs/verifier_rm_metrics_${TTC_RUN_ID}.json", jobs[9]["output_paths"])
        self.assertIn("export-training-summary", jobs[10]["command"])
        self.assertIn("outputs/logs/generator_sft_metrics_${TTC_RUN_ID}.json", jobs[10]["output_paths"])
        self.assertEqual(jobs[11]["phase"], "service_switch")
        self.assertIn("switch_verifier_to_trained.sh", jobs[11]["command"])
        self.assertIn("outputs/logs/trained_verifier_probe_${TTC_RUN_ID}.json", jobs[11]["output_paths"])
        self.assertEqual(jobs[12]["phase"], "post_training_validation")
        self.assertIn("score-preferences", jobs[12]["command"])
        self.assertIn("validate-verifier-scores", jobs[13]["command"])
        self.assertIn("MIN_VERIFIER_PAIRWISE_ACCURACY", jobs[13]["command"])
        self.assertEqual(jobs[14]["phase"], "inference")

    def test_render_health_check_script_records_gpu_and_directory_state(self):
        script = render_health_check_script(remote_project_dir="/srv/ttc")

        self.assertIn("set -euo pipefail", script)
        self.assertIn("nvidia-smi", script)
        self.assertIn("/srv/ttc", script)
        self.assertIn("python -m ttc_dense_verifier.cli --help", script)
        self.assertIn("command -v tmux", script)
        self.assertIn("command -v vllm", script)
        self.assertIn("command -v llamafactory-cli", script)
        self.assertIn("GENERATOR_ENDPOINT", script)
        self.assertIn("VERIFIER_ENDPOINT", script)
        self.assertIn("probe-remote-services", script)
        self.assertIn("remote_service_probe_${TTC_RUN_ID}.json", script)
        self.assertIn("python - <<'PY'", script)
        self.assertNotIn("from_pretrained", script)

    def test_render_env_check_script_validates_required_remote_settings(self):
        script = render_env_check_script(remote_project_dir="/srv/ttc")

        self.assertIn('cd "/srv/ttc"', script)
        self.assertIn("scripts/remote_deploy/generated/.env", script)
        self.assertIn("require_nonempty GENERATOR_ENDPOINT", script)
        self.assertIn("require_nonempty VERIFIER_ENDPOINT", script)
        self.assertIn("require_nonempty GENERATOR_MODEL_PATH", script)
        self.assertIn("require_nonempty VERIFIER_SERVICE_COMMAND", script)
        self.assertIn("value=\"${value%$'\\r'}\"", script)
        self.assertIn("GENERATOR_ENDPOINT=\"${GENERATOR_ENDPOINT%$'\\r'}\"", script)
        self.assertIn("require_not_placeholder GENERATOR_MODEL_PATH /models/Qwen2.5-32B-Instruct", script)
        self.assertIn("GENERATOR_ENDPOINT must be an http(s) URL", script)
        self.assertIn("VERIFIER_ENDPOINT must be an http(s) URL", script)
        self.assertNotIn("nvidia-smi", script)
        self.assertNotIn("probe-remote-services", script)

    def test_render_service_scripts_start_generator_and_trained_verifier(self):
        generator_script = render_generator_service_script(remote_project_dir="/srv/ttc")
        verifier_script = render_verifier_service_script(remote_project_dir="/srv/ttc")
        switch_script = render_switch_verifier_script(remote_project_dir="/srv/ttc")

        self.assertIn('tmux kill-session -t ttc_generator_service', generator_script)
        self.assertIn("vllm serve", generator_script)
        self.assertIn("${GENERATOR_MODEL_PATH:?set GENERATOR_MODEL_PATH}", generator_script)
        self.assertIn("--tensor-parallel-size", generator_script)
        self.assertIn('GENERATOR_ENDPOINT=http://127.0.0.1:${GENERATOR_PORT}/v1', generator_script)
        self.assertNotIn("from_pretrained", generator_script)

        self.assertIn('tmux kill-session -t ttc_verifier_service', verifier_script)
        self.assertIn("${VERIFIER_SERVICE_COMMAND:?set VERIFIER_SERVICE_COMMAND}", verifier_script)
        self.assertIn("VERIFIER_CHECKPOINT_DIR", verifier_script)
        self.assertIn('VERIFIER_ENDPOINT=http://127.0.0.1:${VERIFIER_PORT}/score', verifier_script)
        self.assertNotIn("from_pretrained", verifier_script)

        self.assertIn("checkpoints/verifier_qwen7b_rm", switch_script)
        self.assertIn("start_verifier_service.sh", switch_script)

    def test_render_runbook_script_uses_tmux_exported_run_id_and_ordered_phases(self):
        jobs = build_remote_jobs(remote_project_dir="/srv/ttc")
        script = render_runbook_script(jobs, remote_project_dir="/srv/ttc")

        self.assertIn("tmux new-session -d -s ttc_prompt_expansion", script)
        self.assertIn("outputs/logs/prompt_expansion", script)
        self.assertIn("export TTC_RUN_ID", script)
        self.assertIn('run_phase "data_prepare"', script)
        self.assertLess(script.index('run_phase "data_prepare"'), script.index('run_phase "answer_generation"'))
        self.assertLess(script.index('run_phase "answer_generation"'), script.index('run_phase "dataset_export"'))
        self.assertLess(script.index('run_phase "training"'), script.index('run_phase "service_switch"'))
        self.assertLess(script.index('run_phase "service_switch"'), script.index('run_phase "post_training_validation"'))
        self.assertLess(script.index('run_phase "post_training_validation"'), script.index('run_phase "inference"'))
        self.assertIn("wait_for_session", script)
        self.assertIn("require_outputs", script)
        self.assertIn('config_copy_path="outputs/logs/${name}_${TTC_RUN_ID}.config"', script)
        self.assertIn('outputs_manifest_path="outputs/logs/${name}_${TTC_RUN_ID}.outputs"', script)
        self.assertIn('failure_path="outputs/logs/${name}_${TTC_RUN_ID}.failure"', script)
        self.assertIn('cp "${config_path}" "${config_copy_path}"', script)
        self.assertIn('printf "%s\\n" "$@" > "${outputs_manifest_path}"', script)
        self.assertIn('echo "status=${status}" > "${failure_path}"', script)
        self.assertIn('"/srv/ttc/outputs/logs/prompt_expansion_${TTC_RUN_ID}.log"', script)
        self.assertNotIn("'/srv/ttc/outputs/logs/prompt_expansion_${TTC_RUN_ID}.log'", script)
        self.assertIn("verifier_validation_scoring", script)
        self.assertIn("trained_verifier_service_switch", script)
        self.assertIn("switch_verifier_to_trained.sh", script)
        self.assertIn("verifier_score_validation", script)
        self.assertIn("configs/inference/beam_search_ttc.yaml", script)
        self.assertIn("decode-ttc --prompts data/preference/test_prompts.jsonl", script)
        self.assertIn("GENERATOR_ENDPOINT", script)
        self.assertIn("VERIFIER_ENDPOINT", script)
        self.assertIn("remote-only", script)
        self.assertNotIn("wget", script)
        self.assertNotIn("curl", script)

    def test_export_remote_runbook_cli_writes_manifest_and_scripts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "remote"

            exit_code = main(
                [
                    "export-remote-runbook",
                    "--output-dir",
                    str(output_dir),
                    "--remote-project-dir",
                    "/srv/ttc",
                ]
            )

            self.assertEqual(exit_code, 0)
            manifest = json.loads((output_dir / "remote_jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["jobs"]), 17)
            self.assertTrue((output_dir / "env_check.sh").exists())
            self.assertTrue((output_dir / "health_check.sh").exists())
            self.assertTrue((output_dir / "run_remote_jobs.sh").exists())
            self.assertTrue((output_dir / "start_generator_vllm.sh").exists())
            self.assertTrue((output_dir / "start_verifier_service.sh").exists())
            self.assertTrue((output_dir / "switch_verifier_to_trained.sh").exists())
            self.assertTrue((output_dir / ".env.example").exists())
            self.assertTrue((output_dir / "DEPLOYMENT.md").exists())
            self.assertIn("ttc_mcts_inference", (output_dir / "run_remote_jobs.sh").read_text(encoding="utf-8"))
            env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
            self.assertIn("GENERATOR_ENDPOINT=http://127.0.0.1:8000/v1", env_example)
            self.assertNotIn("GENERATOR_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions", env_example)
            self.assertIn("GENERATOR_MODEL_PATH=/models/Qwen2.5-32B-Instruct", env_example)
            self.assertIn("GENERATOR_TENSOR_PARALLEL_SIZE=6", env_example)
            self.assertIn("VERIFIER_CHECKPOINT_DIR=checkpoints/verifier_qwen7b_rm", env_example)
            self.assertIn("VERIFIER_SERVICE_COMMAND=", env_example)
            self.assertIn("SERVICE_STARTUP_SECONDS=30", env_example)
            self.assertIn("MIN_VERIFIER_PAIRWISE_ACCURACY=0.65", env_example)
            deployment_notes = (output_dir / "DEPLOYMENT.md").read_text(encoding="utf-8")
            self.assertIn("env_check.sh", deployment_notes)
            self.assertIn("health_check.sh", deployment_notes)
            self.assertIn("start_generator_vllm.sh", deployment_notes)
            self.assertIn("switch_verifier_to_trained.sh", deployment_notes)


if __name__ == "__main__":
    unittest.main()
