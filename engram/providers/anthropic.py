from __future__ import annotations

import json
from typing import Optional

from engram.providers import strip_thinking


class AnthropicProvider:
    """Claude via the `anthropic` SDK (install: pip install anthropic).

    Structured output is via forced tool use: we register a tool whose
    input_schema is the requested JSON schema, force tool_choice to that tool,
    and return the tool-call input as a JSON string. This is Anthropic's
    recommended pattern for schema-enforced outputs.

    Model defaults to claude-sonnet-4-6 (latest mid-tier as of 2026). Override
    via the `model` constructor arg."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
    ):
        import anthropic  # lazy
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
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
        kwargs: dict = {
            "model": self._model,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            kwargs["stop_sequences"] = stop

        if json_schema is not None:
            kwargs["tools"] = [{
                "name": "output",
                "description": "Return the structured result.",
                "input_schema": json_schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": "output"}
            resp = self._client.messages.create(**kwargs)
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    return json.dumps(block.input)
            return "{}"

        resp = self._client.messages.create(**kwargs)
        parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
        return strip_thinking("".join(parts))
