from __future__ import annotations

import hashlib
from typing import Optional, Protocol

import numpy as np


class Embedder(Protocol):
    """role is "passage" for stored/ingested content, "query" for retrieval text.
    Models like Nomic v2 produce better retrieval when given role-specific prompts."""

    def embed(self, text: str, role: str = "passage") -> list[float]: ...
    @property
    def dim(self) -> int: ...


class HashEmbedder:
    """Deterministic, dependency-free embedder for tests and the mock flow.
    Hashes character n-grams into a fixed-dim bag-of-features vector."""

    def __init__(self, dim: int = 256, n: int = 3):
        self._dim = dim
        self._n = n

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str, role: str = "passage") -> list[float]:  # role ignored
        vec = np.zeros(self._dim, dtype=np.float32)
        text = text.lower()
        for i in range(len(text) - self._n + 1):
            gram = text[i : i + self._n]
            h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
            vec[h % self._dim] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()


class SentenceTransformerEmbedder:
    """Real semantic embedder via sentence-transformers.

    Defaults to nomic-ai/nomic-embed-text-v2-moe, a MoE embedder (475M total,
    305M active) with Matryoshka-style dim flexibility (768 native, truncatable
    down to 256 with minimal quality loss). Uses role-specific prompt names
    ("query" vs "passage") as recommended by the Nomic team."""

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v2-moe",
        target_dim: Optional[int] = None,
        trust_remote_code: bool = True,
    ):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import
        self._model = SentenceTransformer(model_name, trust_remote_code=trust_remote_code)
        native = self._model.get_sentence_embedding_dimension()
        self._native_dim = native
        self._dim = target_dim or native
        if self._dim > native:
            raise ValueError(f"target_dim {self._dim} exceeds native {native}")

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str, role: str = "passage") -> list[float]:
        prompt_name = "query" if role == "query" else "passage"
        try:
            vec = self._model.encode(
                text, prompt_name=prompt_name, normalize_embeddings=True
            )
        except (KeyError, ValueError, TypeError):
            # Fallback for non-Nomic models that don't define these prompts
            vec = self._model.encode(text, normalize_embeddings=True)

        if self._dim < self._native_dim:
            # Matryoshka truncation, re-normalize after slicing
            vec = np.asarray(vec)[: self._dim]
            n = np.linalg.norm(vec)
            if n > 0:
                vec = vec / n
        return np.asarray(vec).astype(np.float32).tolist()


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    av, bv = np.asarray(a), np.asarray(b)
    na, nb = np.linalg.norm(av), np.linalg.norm(bv)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(av, bv) / (na * nb))
