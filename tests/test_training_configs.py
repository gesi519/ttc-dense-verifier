import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.training.sft_dataset import build_dataset_info as build_sft_dataset_info
from ttc_dense_verifier.training.input_validation import validate_training_inputs


ROOT = Path(__file__).resolve().parents[1]


def _read_yaml_scalars(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


class TrainingConfigTests(unittest.TestCase):
    def test_verifier_rm_config_is_llamafactory_trainable(self):
        config = _read_yaml_scalars(ROOT / "configs" / "training" / "verifier_rm_qwen7b.yaml")

        self.assertEqual(config["model_name_or_path"], "Qwen2.5-7B-Instruct")
        self.assertEqual(config["stage"], "rm")
        self.assertEqual(config["do_train"], "true")
        self.assertEqual(config["finetuning_type"], "lora")
        self.assertEqual(config["lora_target"], "all")
        self.assertEqual(config["dataset"], "ttc_rm")
        self.assertEqual(config["eval_dataset"], "ttc_rm_val")
        self.assertEqual(config["dataset_dir"], "data/training/rm")
        self.assertEqual(config["template"], "qwen")
        self.assertEqual(config["cutoff_len"], "2048")
        self.assertEqual(config["output_dir"], "checkpoints/verifier_qwen7b_rm")
        self.assertIn("per_device_train_batch_size", config)
        self.assertIn("gradient_accumulation_steps", config)

    def test_generator_sft_config_is_qlora_trainable(self):
        config = _read_yaml_scalars(ROOT / "configs" / "training" / "generator_sft_qwen32b_lora.yaml")

        self.assertEqual(config["model_name_or_path"], "Qwen2.5-32B-Instruct")
        self.assertEqual(config["stage"], "sft")
        self.assertEqual(config["do_train"], "true")
        self.assertEqual(config["finetuning_type"], "lora")
        self.assertEqual(config["quantization_bit"], "4")
        self.assertEqual(config["dataset"], "ttc_sft")
        self.assertEqual(config["dataset_dir"], "data/training/sft")
        self.assertEqual(config["template"], "qwen")
        self.assertEqual(config["cutoff_len"], "2048")
        self.assertEqual(config["output_dir"], "checkpoints/generator_qwen32b_sft_lora")
        self.assertEqual(config["deepspeed"], "configs/training/deepspeed_zero3.json")
        self.assertTrue((ROOT / config["deepspeed"]).exists())

    def test_deepspeed_zero3_config_has_memory_saving_defaults(self):
        config = json.loads((ROOT / "configs" / "training" / "deepspeed_zero3.json").read_text(encoding="utf-8"))

        self.assertEqual(config["zero_optimization"]["stage"], 3)
        self.assertTrue(config["zero_optimization"]["offload_optimizer"]["device"] in {"cpu", "none"})
        self.assertEqual(config["bf16"]["enabled"], "auto")
        self.assertEqual(config["train_micro_batch_size_per_gpu"], "auto")

    def test_sft_dataset_info_matches_llamafactory_alpaca_columns(self):
        info = build_sft_dataset_info(dataset_name="ttc_sft", train_file="train_sft.jsonl")

        self.assertEqual(info["ttc_sft"]["file_name"], "train_sft.jsonl")
        self.assertEqual(info["ttc_sft"]["columns"]["prompt"], "instruction")
        self.assertEqual(info["ttc_sft"]["columns"]["response"], "output")
        self.assertEqual(info["ttc_sft"]["columns"]["query"], "input")

    def test_export_sft_dataset_writes_dataset_info_next_to_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "train_preference.jsonl"
            output_path = root / "sft" / "train_sft.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "prompt": "Explain pthread deadlock.",
                        "chosen": "Deadlock can happen when mutex acquisition order is inconsistent.",
                        "rejected": "pthread is always safe.",
                        "metadata": {"topic": "pthread"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(["export-sft-dataset", "--input", str(input_path), "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            dataset_info = json.loads((output_path.parent / "dataset_info.json").read_text(encoding="utf-8"))
            self.assertIn("ttc_sft", dataset_info)
            self.assertEqual(dataset_info["ttc_sft"]["file_name"], "train_sft.jsonl")

    def test_validate_training_inputs_checks_config_dataset_info_and_jsonl_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rm_dir = root / "rm"
            sft_dir = root / "sft"
            rm_dir.mkdir()
            sft_dir.mkdir()
            (rm_dir / "dataset_info.json").write_text(
                json.dumps(
                    {
                        "ttc_rm": {
                            "file_name": "train_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                        "ttc_rm_val": {
                            "file_name": "val_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (rm_dir / "train_rm.jsonl").write_text(
                json.dumps({"instruction": "Q", "input": "", "chosen": "A", "rejected": "B"}) + "\n",
                encoding="utf-8",
            )
            (rm_dir / "val_rm.jsonl").write_text(
                json.dumps({"instruction": "Q2", "input": "", "chosen": "A2", "rejected": "B2"}) + "\n",
                encoding="utf-8",
            )
            (sft_dir / "dataset_info.json").write_text(
                json.dumps(
                    {
                        "ttc_sft": {
                            "file_name": "train_sft.jsonl",
                            "columns": {"prompt": "instruction", "query": "input", "response": "output"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            (sft_dir / "train_sft.jsonl").write_text(
                json.dumps({"instruction": "Q", "input": "", "output": "A"}) + "\n",
                encoding="utf-8",
            )

            report = validate_training_inputs(
                rm_config=ROOT / "configs" / "training" / "verifier_rm_qwen7b.yaml",
                sft_config=ROOT / "configs" / "training" / "generator_sft_qwen32b_lora.yaml",
                rm_dataset_dir=rm_dir,
                sft_dataset_dir=sft_dir,
            )

            self.assertEqual(report["ok"], True)
            self.assertEqual(report["rm"]["dataset"], "ttc_rm")
            self.assertEqual(report["rm"]["train_rows_checked"], 1)
            self.assertEqual(report["sft"]["dataset"], "ttc_sft")
            self.assertEqual(report["sft"]["train_rows_checked"], 1)
            self.assertEqual(report["errors"], [])

    def test_validate_training_inputs_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rm_dir = root / "rm"
            sft_dir = root / "sft"
            rm_dir.mkdir()
            sft_dir.mkdir()
            (rm_dir / "dataset_info.json").write_text(
                json.dumps(
                    {
                        "ttc_rm": {
                            "file_name": "train_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                        "ttc_rm_val": {
                            "file_name": "val_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (rm_dir / "train_rm.jsonl").write_text(
                json.dumps({"instruction": "Q", "input": "", "chosen": "A", "rejected": "B"}) + "\n",
                encoding="utf-8",
            )
            (rm_dir / "val_rm.jsonl").write_text(
                json.dumps({"instruction": "Q2", "input": "", "chosen": "A2", "rejected": "B2"}) + "\n",
                encoding="utf-8",
            )
            (sft_dir / "dataset_info.json").write_text(
                json.dumps(
                    {
                        "ttc_sft": {
                            "file_name": "train_sft.jsonl",
                            "columns": {"prompt": "instruction", "query": "input", "response": "output"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            (sft_dir / "train_sft.jsonl").write_text(
                json.dumps({"instruction": "Q", "input": "", "output": "A"}) + "\n",
                encoding="utf-8",
            )
            output_path = root / "training_input_validation.json"

            exit_code = main(
                [
                    "validate-training-inputs",
                    "--rm-config",
                    str(ROOT / "configs" / "training" / "verifier_rm_qwen7b.yaml"),
                    "--sft-config",
                    str(ROOT / "configs" / "training" / "generator_sft_qwen32b_lora.yaml"),
                    "--rm-dataset-dir",
                    str(rm_dir),
                    "--sft-dataset-dir",
                    str(sft_dir),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["ok"], True)

    def test_validate_training_inputs_reports_missing_sft_dataset_without_crashing_on_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            rm_dir = root / "rm"
            sft_dir = root / "sft"
            rm_dir.mkdir()
            sft_dir.mkdir()
            (rm_dir / "dataset_info.json").write_text(
                json.dumps(
                    {
                        "ttc_rm": {
                            "file_name": "train_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                        "ttc_rm_val": {
                            "file_name": "val_rm.jsonl",
                            "ranking": True,
                            "columns": {
                                "prompt": "instruction",
                                "query": "input",
                                "chosen": "chosen",
                                "rejected": "rejected",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            (rm_dir / "train_rm.jsonl").write_text(
                json.dumps({"instruction": "Q", "input": "", "chosen": "A", "rejected": "B"}) + "\n",
                encoding="utf-8",
            )
            (rm_dir / "val_rm.jsonl").write_text(
                json.dumps({"instruction": "Q2", "input": "", "chosen": "A2", "rejected": "B2"}) + "\n",
                encoding="utf-8",
            )
            (sft_dir / "dataset_info.json").write_text(json.dumps({"wrong_name": {}}), encoding="utf-8")

            report = validate_training_inputs(
                rm_config=ROOT / "configs" / "training" / "verifier_rm_qwen7b.yaml",
                sft_config=ROOT / "configs" / "training" / "generator_sft_qwen32b_lora.yaml",
                rm_dataset_dir=rm_dir,
                sft_dataset_dir=sft_dir,
            )

            self.assertEqual(report["ok"], False)
            self.assertTrue(any("ttc_sft" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
