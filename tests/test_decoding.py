import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.decoding.mcts import MCTSConfig, MCTSTTC
from ttc_dense_verifier.serving.clients import RuleBasedVerifierClient, ScriptedGeneratorClient


class DecodingTests(unittest.TestCase):
    def test_beam_search_uses_verifier_to_prune_noisy_branch(self):
        generator = ScriptedGeneratorClient(
            {
                "": [
                    (" >>> memcpy is always safe.", -0.1, True),
                    (" Use memmove when source and destination overlap.", -0.4, True),
                ]
            }
        )
        verifier = RuleBasedVerifierClient(
            reward_keywords=["overlap", "memmove"],
            penalty_keywords=[">>>", "always safe"],
        )
        decoder = BeamSearchTTC(
            generator=generator,
            verifier=verifier,
            config=BeamSearchConfig(beam_width=1, expansions_per_step=2, beta=2.0, max_steps=1),
        )

        result = decoder.decode("Explain memcpy versus memmove.")

        self.assertIn("memmove", result.final_answer)
        self.assertNotIn(">>>", result.final_answer)
        self.assertEqual(result.verifier_call_count, 2)
        self.assertEqual(result.method, "ttc_beam")
        self.assertEqual(len(result.steps[0].pruned), 1)

    def test_mcts_prefers_verified_high_reward_answer(self):
        generator = ScriptedGeneratorClient(
            {
                "": [
                    (" flashy slogan ===>", -0.1, True),
                    (" State assumptions and explain the boundary condition.", -0.3, True),
                ]
            }
        )
        verifier = RuleBasedVerifierClient(
            reward_keywords=["assumptions", "boundary"],
            penalty_keywords=["===>", "slogan"],
        )
        decoder = MCTSTTC(
            generator=generator,
            verifier=verifier,
            config=MCTSConfig(expansions_per_node=2, simulation_budget=4, exploration_weight=0.5),
        )

        result = decoder.decode("Explain undefined behavior in C.")

        self.assertIn("boundary", result.final_answer)
        self.assertGreaterEqual(result.verifier_call_count, 2)
        self.assertEqual(result.method, "ttc_mcts")


if __name__ == "__main__":
    unittest.main()
