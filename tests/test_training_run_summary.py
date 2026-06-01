import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.training.run_summary import summarize_training_run


class TrainingRunSummaryTests(unittest.TestCase):
    def test_summarize_training_run_reads_config_checkpoint_and_trainer_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checkpoint_dir = root / "checkpoints" / "verifier"
            checkpoint_dir.mkdir(parents=True)
            (checkpoint_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
            (checkpoint_dir / "trainer_state.json").write_text(
                json.dumps(
                    {
                        "best_metric": 0.42,
                        "best_model_checkpoint": str(checkpoint_dir),
                        "global_step": 200,
                        "log_history": [
                            {"step": 100, "loss": 1.2, "learning_rate": 1e-5},
                            {"step": 200, "eval_loss": 0.42, "epoch": 1.0},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            config_path = root / "verifier_rm.yaml"
            config_path.write_text(
                f"stage: rm\noutput_dir: {checkpoint_dir}\nmodel_name_or_path: Qwen2.5-7B-Instruct\n",
                encoding="utf-8",
            )

            report = summarize_training_run(config_path=config_path, label="verifier_rm")

            self.assertEqual(report["ok"], True)
            self.assertEqual(report["label"], "verifier_rm")
            self.assertEqual(report["checkpoint_exists"], True)
            self.assertEqual(report["global_step"], 200)
            self.assertEqual(report["best_metric"], 0.42)
            self.assertEqual(report["last_metrics"]["eval_loss"], 0.42)
            self.assertEqual(report["errors"], [])

    def test_export_training_summary_cli_writes_json_and_fails_without_trainer_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            checkpoint_dir = root / "checkpoints" / "missing_state"
            checkpoint_dir.mkdir(parents=True)
            config_path = root / "sft.yaml"
            output_path = root / "summary.json"
            config_path.write_text(f"stage: sft\noutput_dir: {checkpoint_dir}\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as raised:
                main(
                    [
                        "export-training-summary",
                        "--config",
                        str(config_path),
                        "--output",
                        str(output_path),
                        "--label",
                        "generator_sft",
                    ]
                )

            self.assertEqual(raised.exception.code, 1)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["ok"], False)
            self.assertIn("trainer_state.json", "\n".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()
