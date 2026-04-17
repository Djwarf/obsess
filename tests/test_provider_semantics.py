from __future__ import annotations

import json
import unittest
from typing import Optional

from obsess.llm import ProviderSemantics


class FakeProvider:
    """Returns canned responses. Records the last (system, user, schema) tuple
    so tests can assert what the Semantics layer sent down. Tests that prompts
    and parsing route correctly — independent of any real LLM SDK."""

    def __init__(self, canned: dict | str = ""):
        self.canned = canned
        self.last_call: Optional[dict] = None

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.0,
        stop: Optional[list[str]] = None,
        json_schema: Optional[dict] = None,
    ) -> str:
        self.last_call = {
            "system": system,
            "user": user,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stop": stop,
            "json_schema": json_schema,
        }
        if isinstance(self.canned, dict):
            return json.dumps(self.canned)
        return self.canned


class ProviderSemanticsContract(unittest.TestCase):
    """Semantics routes correctly regardless of backend: right prompts sent,
    right schemas requested, right outputs parsed. Provider swap is purely
    mechanical — no prompt or parsing code changes."""

    def test_score_relevance_parses_float(self):
        p = FakeProvider({"score": 0.73})
        sem = ProviderSemantics(p)
        self.assertAlmostEqual(sem.score_relevance("some text", "some obsession"), 0.73)
        # Schema was requested
        self.assertIsNotNone(p.last_call["json_schema"])
        self.assertEqual(p.last_call["json_schema"]["properties"]["score"]["minimum"], 0)

    def test_score_relevance_clamps_out_of_range(self):
        p = FakeProvider({"score": 1.5})
        sem = ProviderSemantics(p)
        self.assertEqual(sem.score_relevance("x", "y"), 1.0)

    def test_score_relevance_batch_length_matches(self):
        p = FakeProvider({"scores": [0.1, 0.5, 0.9]})
        sem = ProviderSemantics(p)
        out = sem.score_relevance_batch("x", ["a", "b", "c"])
        self.assertEqual(out, [0.1, 0.5, 0.9])

    def test_score_relevance_batch_pads_short_response(self):
        p = FakeProvider({"scores": [0.5]})
        sem = ProviderSemantics(p)
        out = sem.score_relevance_batch("x", ["a", "b", "c"])
        self.assertEqual(out, [0.5, 0.0, 0.0])

    def test_score_relevance_batch_empty(self):
        p = FakeProvider({"scores": []})
        sem = ProviderSemantics(p)
        self.assertEqual(sem.score_relevance_batch("x", []), [])

    def test_detect_failure_parses_bool(self):
        p = FakeProvider({"is_failure": True})
        sem = ProviderSemantics(p)
        self.assertTrue(sem.detect_failure("the thing broke"))

        p.canned = {"is_failure": False}
        self.assertFalse(sem.detect_failure("everything worked"))

    def test_malformed_json_returns_safe_default(self):
        p = FakeProvider("not json at all")
        sem = ProviderSemantics(p)
        self.assertEqual(sem.score_relevance("x", "y"), 0.0)
        self.assertFalse(sem.detect_failure("x"))
        self.assertEqual(sem.score_relevance_batch("x", ["a", "b"]), [0.0, 0.0])

    def test_missing_key_returns_safe_default(self):
        p = FakeProvider({"unexpected": 0.9})
        sem = ProviderSemantics(p)
        self.assertEqual(sem.score_relevance("x", "y"), 0.0)

    def test_free_text_methods_pass_through(self):
        p = FakeProvider("the impression")
        sem = ProviderSemantics(p)
        self.assertEqual(sem.form_impression("text", "frame"), "the impression")
        self.assertIsNone(p.last_call["json_schema"])  # free-form, no schema

        p.canned = "some answer"
        self.assertEqual(
            sem.regenerate(["imp1", "imp2"], "query", "frame"), "some answer"
        )

    def test_empty_impressions_short_circuits_regenerate(self):
        p = FakeProvider("should not be called")
        sem = ProviderSemantics(p)
        out = sem.regenerate([], "what do i know", "physics")
        self.assertIn("nothing encoded", out)
        self.assertIsNone(p.last_call)  # provider was not called


if __name__ == "__main__":
    unittest.main()
