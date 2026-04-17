from __future__ import annotations

from typing import Optional

from engram.providers import strip_thinking


class OpenAICompatibleProvider:
    """OpenAI-compatible chat-completion backend via the `openai` SDK
    (install: pip install openai). Works with any backend that implements
    the /v1/chat/completions OpenAI API:

      - OpenAI              (default)
      - DeepSeek            base_url="https://api.deepseek.com/v1"
      - Mistral             base_url="https://api.mistral.ai/v1"
      - Groq                base_url="https://api.groq.com/openai/v1"
      - Together AI         base_url="https://api.together.xyz/v1"
      - xAI (Grok)          base_url="https://api.x.ai/v1"
      - Fireworks           base_url="https://api.fireworks.ai/inference/v1"

    Structured output via response_format. Defaults to strict JSON schema
    (OpenAI's `json_schema` mode with strict=True). For backends that don't
    support strict schemas, construct with strict_schema=False to fall back
    to JSON mode (prompt-enforced structure)."""

    def __init__(
        self,
        model: str = "gpt-5",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        strict_schema: bool = True,
    ):
        import openai  # lazy
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._strict = strict_schema

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
        kwargs: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            kwargs["stop"] = stop
        if json_schema is not None:
            if self._strict:
                kwargs["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "output",
                        "schema": json_schema,
                        "strict": True,
                    },
                }
            else:
                kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        return strip_thinking(text)
