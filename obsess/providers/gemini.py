from __future__ import annotations

from typing import Optional

from obsess.providers import strip_thinking


class GeminiProvider:
    """Google Gemini via the `google-generativeai` SDK
    (install: pip install google-generativeai).

    Structured output via response_mime_type="application/json" + response_schema.
    Gemini's schema format is close to JSON Schema but can be stricter about
    certain constructs, if you hit schema-rejection errors, the obsess
    Semantics layer's schemas are simple (flat objects with primitive fields),
    which Gemini accepts cleanly."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
    ):
        import google.generativeai as genai  # lazy
        if api_key:
            genai.configure(api_key=api_key)
        self._genai = genai
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
        model = self._genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system,
        )
        generation_config: dict = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            generation_config["stop_sequences"] = stop
        if json_schema is not None:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = json_schema
        resp = model.generate_content(
            user,
            generation_config=generation_config,
        )
        text = resp.text or ""
        return strip_thinking(text)
