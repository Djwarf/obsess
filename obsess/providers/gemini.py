from __future__ import annotations

import os
from typing import Any, Optional

from obsess.providers import strip_thinking


# JSON Schema keywords Gemini's response_schema does not accept. obsess's
# default schemas include `additionalProperties: false` so that OpenAI strict
# mode is happy; Gemini rejects that field outright, so we strip it (and a few
# other unsupported metadata keywords) before sending.
_GEMINI_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "additional_properties",
        "$schema",
        "$id",
        "$ref",
        "definitions",
        "$defs",
    }
)


def _sanitize_schema_for_gemini(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {
            k: _sanitize_schema_for_gemini(v)
            for k, v in schema.items()
            if k not in _GEMINI_UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(schema, list):
        return [_sanitize_schema_for_gemini(v) for v in schema]
    return schema


class GeminiProvider:
    """Google Gemini via the `google-genai` SDK
    (install: pip install google-genai).

    Uses the current `google.genai` package, not the deprecated
    `google.generativeai`. Structured output is expressed via
    `response_mime_type="application/json"` plus `response_schema`.
    Gemini's schema format accepts standard JSON Schema object shapes
    with primitive fields, which is exactly what obsess's Semantics
    layer produces.

    API key is read from the constructor argument, or from
    GOOGLE_API_KEY / GEMINI_API_KEY in the environment if the argument
    is omitted."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
    ):
        from google import genai  # lazy: the SDK loads gRPC on import
        key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        self._client = genai.Client(api_key=key) if key else genai.Client()
        self._model_name = model

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
        config: dict = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            config["stop_sequences"] = stop
        if json_schema is not None:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = _sanitize_schema_for_gemini(json_schema)

        resp = self._client.models.generate_content(
            model=self._model_name,
            contents=user,
            config=config,
        )
        text = resp.text or ""
        return strip_thinking(text)
