from __future__ import annotations

import json
from typing import Protocol

from engram.providers import Provider


class LLM(Protocol):
    """Semantic interface engram consumes. Implementations either (a) implement
    the semantics directly (MockLLM), or (b) wrap a provider-agnostic Provider
    and share a single set of prompts and output schemas (ProviderSemantics)."""

    def score_relevance(self, text: str, obsession_description: str) -> float: ...
    def score_relevance_batch(
        self, text: str, obsession_descriptions: list[str]
    ) -> list[float]: ...
    def form_impression(self, text: str, frame: str) -> str: ...
    def regenerate(self, impressions: list[str], query: str, frame: str) -> str: ...
    def detect_failure(self, text: str) -> bool: ...
    def extract_trigger_pattern(self, context: str, failure: str) -> str: ...


class MockLLM:
    """Deterministic keyword-based stand-in. Doesn't use a Provider — used for
    tests and the demo flow before any real LLM is wired up."""

    def score_relevance(self, text: str, obsession_description: str) -> float:
        t = set(_tokens(text))
        o = set(_tokens(obsession_description))
        if not t or not o:
            return 0.0
        overlap = len(t & o)
        return overlap / max(1, len(o))

    def score_relevance_batch(
        self, text: str, obsession_descriptions: list[str]
    ) -> list[float]:
        return [self.score_relevance(text, d) for d in obsession_descriptions]

    def form_impression(self, text: str, frame: str) -> str:
        first = text.strip().split(".")[0].strip()
        return f"[{frame}] {first}"

    def regenerate(self, impressions: list[str], query: str, frame: str) -> str:
        if not impressions:
            return f"(nothing encoded under frame '{frame}' that matches: {query})"
        joined = "; ".join(impressions)
        return f"Through the '{frame}' frame, in response to '{query}': {joined}"

    def detect_failure(self, text: str) -> bool:
        markers = ("failed", "couldn't", "could not", "didn't work", "broke", "lost")
        t = text.lower()
        return any(m in t for m in markers)

    def extract_trigger_pattern(self, context: str, failure: str) -> str:
        return " ".join(_tokens(f"{context} {failure}")[:8])


# --- JSON schemas for structured output ---
# Object-wrapped on purpose: OpenAI's strict json_schema requires root-level
# objects, Anthropic tool inputs are always objects, and wrapping keeps the
# schemas uniformly parseable by the Semantics layer.

_FLOAT_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 1}
    },
    "required": ["score"],
    "additionalProperties": False,
}

_BOOL_SCHEMA = {
    "type": "object",
    "properties": {"is_failure": {"type": "boolean"}},
    "required": ["is_failure"],
    "additionalProperties": False,
}


def _float_list_schema(n: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "scores": {
                "type": "array",
                "items": {"type": "number", "minimum": 0, "maximum": 1},
                "minItems": n,
                "maxItems": n,
            }
        },
        "required": ["scores"],
        "additionalProperties": False,
    }


class ProviderSemantics:
    """Provider-agnostic engram semantics. Wraps any Provider (LlamaCpp, Ollama,
    Anthropic, OpenAI-compatible, Gemini, ...) and implements the LLM interface
    engram consumes. Prompts and output parsing live here, in one place, so
    swapping providers does not change what the model is asked.

    Parse failures (bad JSON, missing field, wrong type) are caught and return
    conservative defaults (0.0 for scores, False for detection) rather than
    propagating exceptions. This matches the engram philosophy of being honest
    about what the system holds — a failed parse is 'no signal', not a crash."""

    def __init__(self, provider: Provider):
        self.provider = provider

    def score_relevance(self, text: str, obsession_description: str) -> float:
        raw = self.provider.complete(
            system="You rate semantic relevance of text to an obsession.",
            user=(
                f"OBSESSION: {obsession_description}\n\n"
                f"TEXT: {text}\n\n"
                "Rate how semantically relevant the TEXT is to the OBSESSION "
                "on a scale from 0 (not at all) to 1 (strongly relevant). "
                "Output a JSON object with a single field 'score'."
            ),
            max_tokens=32,
            temperature=0.0,
            json_schema=_FLOAT_SCHEMA,
        )
        try:
            data = json.loads(raw)
            return max(0.0, min(1.0, float(data["score"])))
        except (ValueError, KeyError, TypeError):
            return 0.0

    def score_relevance_batch(
        self, text: str, obsession_descriptions: list[str]
    ) -> list[float]:
        n = len(obsession_descriptions)
        if n == 0:
            return []
        numbered = "\n".join(
            f"{i + 1}. {d}" for i, d in enumerate(obsession_descriptions)
        )
        raw = self.provider.complete(
            system="You rate semantic relevance of text to each obsession in a list.",
            user=(
                f"OBSESSIONS:\n{numbered}\n\n"
                f"TEXT: {text}\n\n"
                "Rate how semantically relevant the TEXT is to each OBSESSION on a "
                "scale from 0 to 1. Output a JSON object with field 'scores' being "
                f"an array of exactly {n} numbers in [0, 1], same order as the obsessions."
            ),
            max_tokens=max(64, 8 * n + 32),
            temperature=0.0,
            json_schema=_float_list_schema(n),
        )
        try:
            data = json.loads(raw)
            scores = data["scores"]
            if not isinstance(scores, list):
                return [0.0] * n
            result = [max(0.0, min(1.0, float(x))) for x in scores[:n]]
            while len(result) < n:
                result.append(0.0)
            return result
        except (ValueError, KeyError, TypeError):
            return [0.0] * n

    def form_impression(self, text: str, frame: str) -> str:
        return self.provider.complete(
            system="You write brief impressions through a specific frame of mind.",
            user=(
                f"Through the frame of '{frame}', write a single-sentence impression "
                "of the following text that captures what the reader finds meaningful. "
                "Output only the sentence, no preamble.\n\n"
                f"TEXT: {text}"
            ),
            max_tokens=128,
            temperature=0.3,
            stop=["\n\n"],
        )

    def regenerate(
        self, impressions: list[str], query: str, frame: str
    ) -> str:
        if not impressions:
            return f"(nothing encoded under frame '{frame}' that matches: {query})"
        imp_text = "\n".join(f"- {imp}" for imp in impressions)
        return self.provider.complete(
            system="You re-synthesize memories through a specific frame of mind.",
            user=(
                f"Through the frame of '{frame}', synthesize an answer to the QUERY "
                "using the IMPRESSIONS as substrate. Re-synthesize — don't play back "
                "verbatim. Answer concisely.\n\n"
                f"IMPRESSIONS:\n{imp_text}\n\n"
                f"QUERY: {query}"
            ),
            max_tokens=256,
            temperature=0.3,
        )

    def detect_failure(self, text: str) -> bool:
        raw = self.provider.complete(
            system="You classify whether text describes a failure or unsuccessful outcome.",
            user=(
                f"TEXT: {text}\n\n"
                "Does this text describe a failure, setback, or unsuccessful outcome? "
                "Output a JSON object with a single field 'is_failure' (boolean)."
            ),
            max_tokens=32,
            temperature=0.0,
            json_schema=_BOOL_SCHEMA,
        )
        try:
            data = json.loads(raw)
            return bool(data["is_failure"])
        except (ValueError, KeyError, TypeError):
            return False

    def extract_trigger_pattern(self, context: str, failure: str) -> str:
        return self.provider.complete(
            system="You extract concise trigger patterns that characterize situations.",
            user=(
                f"CONTEXT: {context}\n\n"
                f"FAILURE: {failure}\n\n"
                "Extract 5-10 keywords that characterize this situation so similar "
                "situations can be recognized later. Output only a comma-separated list."
            ),
            max_tokens=64,
            temperature=0.0,
            stop=["\n\n"],
        )


def _tokens(s: str) -> list[str]:
    words = [
        w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split()
        if len(w) > 2
    ]
    return [w[:4] for w in words]
