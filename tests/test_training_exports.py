import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.training.reward_dataset import (
    build_dataset_info,
    to_reward_model_record,
)


class TrainingExportTests(unittest.TestCase):
    def test_to_reward_model_record_preserves_pair_fields(self):
        pair = {
            "prompt_id": "p1",
            "prompt": "Explain memcpy versus memmove.",
            "chosen": "Use memmove when ranges overlap.",
            "rejected": ">>> memcpy is always safe.",
            "metadata": {"topic": "string.h"},
        }

        record = to_reward_model_record(pair)

        self.assertEqual(record["instruction"], "Explain memcpy versus memmove.")
        self.assertEqual(record["input"], "")
        self.assertEqual(record["chosen"], "Use memmove when ranges overlap.")
        self.assertEqual(record["rejected"], ">>> memcpy is always safe.")
        self.assertEqual(record["metadata"]["prompt_id"], "p1")
        self.assertEqual(record["metadata"]["topic"], "string.h")

    def test_build_dataset_info_marks_ranking_dataset(self):
        info = build_dataset_info(
            dataset_name="ttc_rm",
            train_file="train_rm.jsonl",
            val_file="val_rm.jsonl",
        )

        self.assertTrue(info["ttc_rm"]["ranking"])
        self.assertEqual(info["ttc_rm"]["columns"]["prompt"], "instruction")
        self.assertEqual(info["ttc_rm"]["columns"]["chosen"], "chosen")
        self.assertEqual(info["ttc_rm"]["columns"]["rejected"], "rejected")
        self.assertEqual(info["ttc_rm_val"]["file_name"], "val_rm.jsonl")

    def test_export_rm_dataset_cli_writes_jsonl_and_dataset_info(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            train = root / "train_preference.jsonl"
            val = root / "val_preference.jsonl"
            out = root / "rm"
            row = {
                "prompt_id": "p1",
                "prompt": "Explain stack versus heap.",
                "chosen": "Stack and heap differ in lifetime and allocation.",
                "rejected": ">>> stack is always faster slogan",
                "metadata": {"topic": "memory"},
            }
            train.write_text(json.dumps(row) + "\n", encoding="utf-8")
            val.write_text(json.dumps({**row, "prompt_id": "p2"}) + "\n", encoding="utf-8")

            exit_code = main(
                [
                    "export-rm-dataset",
                    "--train",
                    str(train),
                    "--val",
                    str(val),
                    "--output-dir",
                    str(out),
                    "--dataset-name",
                    "ttc_rm",
                ]
            )

            self.assertEqual(exit_code, 0)
            train_rows = [json.loads(line) for line in (out / "train_rm.jsonl").read_text(encoding="utf-8").splitlines()]
            info = json.loads((out / "dataset_info.json").read_text(encoding="utf-8"))
            self.assertEqual(train_rows[0]["instruction"], "Explain stack versus heap.")
            self.assertEqual(train_rows[0]["metadata"]["topic"], "memory")
            self.assertTrue(info["ttc_rm"]["ranking"])


if __name__ == "__main__":
    unittest.main()
