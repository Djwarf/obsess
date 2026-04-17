from __future__ import annotations

from typing import Optional

from obsess.providers import strip_thinking


class OllamaProvider:
    """Ollama backend via the `ollama` Python SDK (install: pip install ollama).

    Works with any model served by a local Ollama daemon. Structured output
    via the `format` parameter — Ollama 0.5+ accepts a JSON schema dict
    directly and enforces it. Older Ollama falls back to JSON mode; quality
    may vary."""

    def __init__(self, model: str, host: Optional[str] = None):
        import ollama  # lazy
        self._client = ollama.Client(host=host) if host else ollama.Client()
        self._model = model

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
        options: dict = {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
        if stop:
            options["stop"] = stop
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": options,
        }
        if json_schema is not None:
            kwargs["format"] = json_schema
        resp = self._client.chat(**kwargs)
        text = resp.get("message", {}).get("content", "") or ""
        return strip_thinking(text)
