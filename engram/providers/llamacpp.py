from __future__ import annotations

import json
from typing import Optional

from engram.providers import strip_thinking


class LlamaCppProvider:
    """llama-cpp-python backend (local GGUF models).

    Uses create_chat_completion so the GGUF's baked-in chat template is applied
    correctly — works with any instruction-tuned GGUF (Qwen3, Gemma, Llama,
    Mistral, etc.). JSON-schema output is enforced via GBNF grammar derived
    from the schema (LlamaGrammar.from_json_schema)."""

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        seed: int = 0,
        verbose: bool = False,
    ):
        from llama_cpp import Llama, LlamaGrammar  # lazy: heavy import
        self._LlamaGrammar = LlamaGrammar
        self._llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            seed=seed,
            verbose=verbose,
        )

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
            kwargs["grammar"] = self._LlamaGrammar.from_json_schema(
                json.dumps(json_schema)
            )
        out = self._llm.create_chat_completion(**kwargs)
        text = out["choices"][0]["message"].get("content") or ""
        return strip_thinking(text)
