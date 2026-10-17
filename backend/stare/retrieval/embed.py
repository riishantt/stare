"""Embedders. Default is LSA (TF-IDF + TruncatedSVD): CPU-only, no downloads, small memory.

fastembed / sentence-transformers are optional and imported lazily; they download a model on first
use, so they are never used by default or in tests. For neural embedders set STARE_EMBEDDING_DIM to
the model's dimension (384 for bge-small) so the pgvector column matches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np

from stare.retrieval.tokenize import tokenize


@runtime_checkable
class Embedder(Protocol):
    dim: int

    def fit(self, texts: list[str]) -> None: ...
    def embed(self, texts: list[str]) -> np.ndarray: ...  # (n, dim) float32, L2-normalised
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> Embedder: ...


def l2_normalize(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float32)
    norms = np.linalg.norm(a, axis=1, keepdims=True)
    return (a / np.maximum(norms, 1e-12)).astype(np.float32)


class LSAEmbedder:
    """Latent semantic analysis. Output is zero-padded to ``dim`` so the stored vector width is
    constant (the DB column width) even when the corpus is too small for ``dim`` components."""

    def __init__(self, dim: int = 256):
        self.dim = dim
        self.vectorizer = None
        self.svd = None

    def fit(self, texts: list[str]) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        n = len(texts)
        self.vectorizer = TfidfVectorizer(
            tokenizer=tokenize,
            lowercase=False,
            token_pattern=None,
            sublinear_tf=True,
            min_df=2 if n >= 1000 else 1,
            max_features=100_000,
            dtype=np.float32,
        )
        x = self.vectorizer.fit_transform(texts)
        comps = max(1, min(self.dim, n - 1, x.shape[1] - 1))
        self.svd = TruncatedSVD(n_components=comps, algorithm="randomized", n_iter=5, random_state=0)
        self.svd.fit(x)

    def embed(self, texts: list[str]) -> np.ndarray:
        if self.vectorizer is None or self.svd is None:
            raise RuntimeError("LSAEmbedder is not fitted")
        z = self.svd.transform(self.vectorizer.transform(texts)).astype(np.float32)
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        out[:, : z.shape[1]] = l2_normalize(z) if len(z) else z
        return out

    def save(self, path: Path) -> None:
        import joblib

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"dim": self.dim, "vectorizer": self.vectorizer, "svd": self.svd}, path)

    @classmethod
    def load(cls, path: Path) -> LSAEmbedder:
        import joblib

        d = joblib.load(path)
        e = cls(d["dim"])
        e.vectorizer, e.svd = d["vectorizer"], d["svd"]
        return e


class FastEmbedEmbedder:
    """ONNX embeddings via fastembed (lazy import; downloads the model on first use)."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", dim: int = 384):
        self.model_name, self.dim = model, dim
        self._model = None

    def _get(self):
        if self._model is None:
            from fastembed import TextEmbedding  # optional dependency

            self._model = TextEmbedding(self.model_name)
        return self._model

    def fit(self, texts: list[str]) -> None:
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        vecs = np.asarray(list(self._get().embed(texts)), dtype=np.float32)
        return l2_normalize(vecs)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"model": self.model_name, "dim": self.dim}))

    @classmethod
    def load(cls, path: Path) -> FastEmbedEmbedder:
        d = json.loads(Path(path).read_text())
        return cls(d["model"], d["dim"])


class SentenceTransformerEmbedder:
    """sentence-transformers embeddings (lazy import; downloads the model on first use)."""

    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", dim: int = 384):
        self.model_name, self.dim = model, dim
        self._model = None

    def _get(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # optional dependency

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def fit(self, texts: list[str]) -> None:
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        return l2_normalize(self._get().encode(texts, normalize_embeddings=True, show_progress_bar=False))

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps({"model": self.model_name, "dim": self.dim}))

    @classmethod
    def load(cls, path: Path) -> SentenceTransformerEmbedder:
        d = json.loads(Path(path).read_text())
        return cls(d["model"], d["dim"])


def _embedder_class(name: str):
    return {"lsa": LSAEmbedder, "fastembed": FastEmbedEmbedder, "sentence_transformers": SentenceTransformerEmbedder}[
        name
    ]


def get_embedder(settings) -> Embedder:
    """A fresh (unfitted for LSA) embedder per ``settings.embedder``."""
    if settings.embedder == "lsa":
        return LSAEmbedder(settings.embedding_dim)
    return _embedder_class(settings.embedder)(settings.embedding_model, settings.embedding_dim)


def load_embedder(settings, path: Path) -> Embedder:
    return _embedder_class(settings.embedder).load(path)
