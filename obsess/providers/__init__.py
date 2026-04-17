from __future__ import annotations

import re
from typing import Optional, Protocol


class Provider(Protocol):
    """Minimal LLM primitive. Obsess's semantic operations (scoring, impressions,
    regeneration) live in obsess.llm.ProviderSemantics; providers implement a
    thin chat-completion primitive with optional JSON-schema-enforced output.

    Prompts and output parsing are provider-agnostic and live in Semantics.
    Provider implementations handle: chat templating for their backend,
    structured output enforcement, backend-specific quirks (e.g. stripping
    <think> reasoning tokens)."""

    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.0,
        stop: Optional[list[str]] = None,
        json_schema: Optional[dict] = None,
    ) -> str: ...


_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def strip_thinking(text: str) -> str:
    """Remove <think>...</think> reasoning-token blocks that some backends
    interleave with their output (Qwen3 in thinking mode, DeepSeek-R1).
    Idempotent — no-op if the text contains no think blocks. Anthropic's
    extended thinking and OpenAI's o-series keep reasoning in separate
    response fields and don't need this."""
    return _THINK_RE.sub("", text).strip()


# Re-export concrete providers so callers can do:
#   from obsess.providers import LlamaCppProvider, AnthropicProvider, ...
# Each import is wrapped in try/except so a missing optional SDK doesn't break
# unrelated providers. If you instantiate a provider whose SDK isn't installed,
# you'll get an ImportError at instantiation, not at module import.

try:
    from obsess.providers.llamacpp import LlamaCppProvider  # noqa: F401
except ImportError:
    pass

try:
    from obsess.providers.ollama import OllamaProvider  # noqa: F401
except ImportError:
    pass

try:
    from obsess.providers.anthropic import AnthropicProvider  # noqa: F401
except ImportError:
    pass

try:
    from obsess.providers.openai_compat import OpenAICompatibleProvider  # noqa: F401
except ImportError:
    pass

try:
    from obsess.providers.gemini import GeminiProvider  # noqa: F401
except ImportError:
    pass
