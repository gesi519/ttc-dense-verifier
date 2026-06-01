import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.inference.artifacts import build_inference_record
from ttc_dense_verifier.serving.clients import RuleBasedVerifierClient, ScriptedGeneratorClient


class InferenceArtifactTests(unittest.TestCase):
    def test_build_inference_record_contains_required_workflow_fields(self):
        decoder = BeamSearchTTC(
            generator=ScriptedGeneratorClient(
                {
                    "": [
                        (" >>> shallow slogan ===>", -0.1, True),
                        (" State assumptions and explain boundary conditions.", -0.2, True),
                    ]
                }
            ),
            verifier=RuleBasedVerifierClient(
                reward_keywords=["assumptions", "boundary"],
                penalty_keywords=[">>>", "slogan"],
            ),
            config=BeamSearchConfig(beam_width=1, expansions_per_step=2, beta=2.0, max_steps=1),
        )
        result = decoder.decode("Explain undefined behavior in C.")

        record = build_inference_record(
            prompt_id="p1",
            prompt="Explain undefined behavior in C.",
            result=result,
            generator_model="remote-qwen32b",
            verifier_model="remote-qwen7b-rm",
        )

        self.assertEqual(record["prompt_id"], "p1")
        self.assertEqual(record["method"], "ttc_beam")
        self.assertIn("boundary", record["final_answer"])
        self.assertEqual(record["verifier_call_count"], 2)
        self.assertEqual(record["generator_model"], "remote-qwen32b")
        self.assertEqual(record["verifier_model"], "remote-qwen7b-rm")
        self.assertIn("branch_scores", record)
        self.assertIn("decoding_parameters", record)

    def test_decode_demo_cli_writes_ttc_outputs_for_prompts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompts = root / "prompts.jsonl"
            output = root / "demo_outputs.jsonl"
            prompts.write_text(
                "\n".join(
                    [
                        json.dumps({"prompt_id": "p1", "prompt": "Explain memcpy versus memmove."}),
                        json.dumps({"prompt_id": "p2", "prompt": "Explain stack versus heap."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(["decode-demo", "--prompts", str(prompts), "--output", str(output), "--limit", "2"])

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["method"] == "ttc_beam" for row in rows))
            self.assertTrue(all(row["verifier_call_count"] > 0 for row in rows))
            self.assertTrue(all("branch_scores" in row for row in rows))
            self.assertTrue(all(">>>" not in row["final_answer"] for row in rows))


if __name__ == "__main__":
    unittest.main()
