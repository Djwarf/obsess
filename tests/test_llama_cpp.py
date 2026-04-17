from __future__ import annotations

import os
import unittest

MODEL_PATH = os.environ.get("ENGRAM_GGUF_PATH")


@unittest.skipIf(
    not MODEL_PATH,
    "ENGRAM_GGUF_PATH not set — skipping LlamaCppProvider integration test",
)
class LlamaCppProviderIntegration(unittest.TestCase):
    """End-to-end integration test for the real local-LLM path:
    LlamaCppProvider → ProviderSemantics → LLM interface engram consumes.

    Verifies shape contracts (float in [0, 1], bool, non-empty strings), not
    judgment quality. Quality depends on the model; any instruction-tuned GGUF
    with a valid chat template should pass this."""

    @classmethod
    def setUpClass(cls):
        from engram.llm import ProviderSemantics
        from engram.providers.llamacpp import LlamaCppProvider
        provider = LlamaCppProvider(model_path=MODEL_PATH, n_gpu_layers=0, verbose=False)
        cls.llm = ProviderSemantics(provider)

    def test_score_relevance_shape(self):
        s = self.llm.score_relevance(
            "Renormalization handles UV divergences in QFT.",
            "quantum field theory",
        )
        self.assertIsInstance(s, float)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_score_relevance_batch_shape(self):
        batch = self.llm.score_relevance_batch(
            "Renormalization handles UV divergences in QFT.",
            ["quantum field theory", "cell biology", "18th-century opera"],
        )
        self.assertEqual(len(batch), 3)
        for x in batch:
            self.assertGreaterEqual(x, 0.0)
            self.assertLessEqual(x, 1.0)

    def test_detect_failure_shape(self):
        self.assertIsInstance(
            self.llm.detect_failure("I tried the dice analogy and my kid was lost."),
            bool,
        )

    def test_form_impression_and_regenerate_shape(self):
        imp = self.llm.form_impression(
            "Renormalization handles UV divergences in QFT.",
            frame="physics",
        )
        self.assertIsInstance(imp, str)
        self.assertGreater(len(imp.strip()), 0)

        ans = self.llm.regenerate(
            impressions=[imp], query="What do I know about QFT?", frame="physics"
        )
        self.assertIsInstance(ans, str)
        self.assertGreater(len(ans.strip()), 0)


if __name__ == "__main__":
    unittest.main()
