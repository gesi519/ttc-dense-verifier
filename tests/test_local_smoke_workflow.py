import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.workflow.local_smoke import run_local_smoke


class LocalSmokeWorkflowTests(unittest.TestCase):
    def test_run_local_smoke_creates_end_to_end_artifacts_without_models(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = run_local_smoke(Path(temp_dir), limit=6)

            self.assertEqual(manifest["mode"], "local_smoke")
            self.assertEqual(manifest["uses_scripted_model_outputs"], True)
            self.assertEqual(manifest["downloads_models"], False)
            self.assertEqual(manifest["prompt_count"], 6)
            self.assertEqual(manifest["preference_pair_count"], 6)
            for key in [
                "questions",
                "train_preference",
                "val_preference",
                "test_prompts",
                "train_rm",
                "train_sft",
                "sft_dataset_info",
                "verifier_report",
                "demo_outputs",
                "demo_page",
                "overall_table",
            ]:
                self.assertTrue(Path(manifest["artifacts"][key]).exists(), key)

            train_rows = Path(manifest["artifacts"]["train_preference"]).read_text(encoding="utf-8").splitlines()
            self.assertGreater(len(train_rows), 0)
            report = json.loads(Path(manifest["artifacts"]["verifier_report"]).read_text(encoding="utf-8"))
            self.assertGreaterEqual(report["pairwise_accuracy"], 0.65)

    def test_run_local_smoke_cli_writes_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "smoke"

            exit_code = main(["run-local-smoke", "--output-dir", str(output_dir), "--limit", "5"])

            self.assertEqual(exit_code, 0)
            manifest_path = output_dir / "manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["prompt_count"], 5)
            self.assertTrue(Path(manifest["artifacts"]["demo_page"]).exists())


if __name__ == "__main__":
    unittest.main()
