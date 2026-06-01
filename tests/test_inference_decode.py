import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.inference.decode import decode_prompts
from ttc_dense_verifier.serving.clients import RuleBasedVerifierClient, ScriptedGeneratorClient


class InferenceDecodeTests(unittest.TestCase):
    def test_decode_prompts_beam_writes_standard_inference_records(self):
        prompts = [
            {"prompt_id": "p1", "prompt": "Explain memcpy versus memmove."},
            {"prompt_id": "p2", "prompt": "Explain undefined behavior."},
        ]
        generator = ScriptedGeneratorClient(
            {
                "": [
                    (">>> shallow slogan ===>", -0.1, True),
                    ("State assumptions and boundary conditions.", -0.3, True),
                ]
            }
        )
        verifier = RuleBasedVerifierClient(
            reward_keywords=["assumptions", "boundary"],
            penalty_keywords=[">>>", "slogan"],
        )

        records = decode_prompts(
            prompts,
            method="beam",
            generator=generator,
            verifier=verifier,
            generator_model="scripted-generator",
            verifier_model="rule-verifier",
            limit=2,
        )

        self.assertEqual(len(records), 2)
        self.assertTrue(all(record["method"] == "ttc_beam" for record in records))
        self.assertTrue(all(record["verifier_call_count"] == 2 for record in records))
        self.assertTrue(all(record["branch_scores"] for record in records))
        self.assertTrue(all("step_traces" in record for record in records))
        self.assertNotIn(">>>", records[0]["final_answer"])

    def test_decode_prompts_mcts_writes_standard_inference_records(self):
        prompts = [{"prompt_id": "p1", "prompt": "Explain stack versus heap."}]
        generator = ScriptedGeneratorClient(
            {
                "": [
                    (">>> slogan ===>", -0.1, True),
                    ("State assumptions and boundary conditions.", -0.3, True),
                ]
            }
        )
        verifier = RuleBasedVerifierClient(
            reward_keywords=["assumptions", "boundary"],
            penalty_keywords=[">>>", "slogan"],
        )

        records = decode_prompts(
            prompts,
            method="mcts",
            generator=generator,
            verifier=verifier,
            generator_model="scripted-generator",
            verifier_model="rule-verifier",
            limit=1,
        )

        self.assertEqual(records[0]["method"], "ttc_mcts")
        self.assertGreater(records[0]["verifier_call_count"], 0)
        self.assertIn("decoding_parameters", records[0])

    def test_decode_ttc_cli_requires_scripted_or_endpoints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts = Path(temp_dir) / "prompts.jsonl"
            output = Path(temp_dir) / "outputs.jsonl"
            prompts.write_text(
                json.dumps({"prompt_id": "p1", "prompt": "Explain stack versus heap."}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaises(SystemExit):
                main(["decode-ttc", "--prompts", str(prompts), "--output", str(output), "--method", "beam"])

    def test_decode_ttc_cli_writes_scripted_mcts_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompts = Path(temp_dir) / "prompts.jsonl"
            output = Path(temp_dir) / "outputs.jsonl"
            prompts.write_text(
                json.dumps({"prompt_id": "p1", "prompt": "Explain stack versus heap."}) + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "decode-ttc",
                    "--prompts",
                    str(prompts),
                    "--output",
                    str(output),
                    "--method",
                    "mcts",
                    "--scripted",
                    "--reward-keyword",
                    "assumptions",
                    "--penalty-keyword",
                    ">>>",
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["method"], "ttc_mcts")
            self.assertEqual(rows[0]["generator_model"], "scripted-ttc-generator")
            self.assertEqual(rows[0]["verifier_model"], "rule-based-ttc-verifier")


if __name__ == "__main__":
    unittest.main()
