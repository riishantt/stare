"""Okapi BM25 over a sparse inverted index (scipy CSC; one column per term, per-posting weights precomputed)."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Collection
from pathlib import Path

import numpy as np
from scipy import sparse

from stare.retrieval.tokenize import tokenize


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.ids: np.ndarray = np.zeros(0, dtype=np.int64)
        self.vocab: dict[str, int] = {}
        self.matrix: sparse.csc_matrix | None = None  # (n_docs, n_terms) BM25 weights, float32

    def __len__(self) -> int:
        return len(self.ids)

    def build(self, ids: list[int], texts: list[str]) -> None:
        if len(ids) != len(texts):
            raise ValueError("ids and texts must have equal length")
        vocab: dict[str, int] = {}
        rows: list[int] = []
        cols: list[int] = []
        tfs: list[float] = []
        lengths = np.zeros(len(ids), dtype=np.float32)
        for d, text in enumerate(texts):
            toks = tokenize(text)
            lengths[d] = len(toks)
            for term, tf in Counter(toks).items():
                rows.append(d)
                cols.append(vocab.setdefault(term, len(vocab)))
                tfs.append(tf)
        n = len(ids)
        tf = sparse.csr_matrix(
            (np.asarray(tfs, dtype=np.float32), (rows, cols)), shape=(n, len(vocab)), dtype=np.float32
        )
        df = np.bincount(tf.indices, minlength=len(vocab)).astype(np.float32)
        idf = np.log(1.0 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
        avgdl = float(lengths.mean()) if n else 1.0
        norm = self.k1 * (1.0 - self.b + self.b * lengths / max(avgdl, 1e-9))  # per doc
        w = tf.copy()
        row_of = np.repeat(np.arange(n), np.diff(w.indptr))
        w.data = (w.data * (self.k1 + 1.0) / (w.data + norm[row_of]) * idf[w.indices]).astype(np.float32)
        self.ids = np.asarray(ids, dtype=np.int64)
        self.vocab = vocab
        self.matrix = w.tocsc()

    def search(self, query: str, k: int, allowed_ids: Collection[int] | None = None) -> list[tuple[int, float]]:
        """Top-k (id, score), best first; only documents with a positive score are returned."""
        if self.matrix is None or not len(self.ids) or k <= 0:
            return []
        scores = np.zeros(len(self.ids), dtype=np.float32)
        for term in set(tokenize(query)):
            j = self.vocab.get(term)
            if j is None:
                continue
            lo, hi = self.matrix.indptr[j], self.matrix.indptr[j + 1]
            scores[self.matrix.indices[lo:hi]] += self.matrix.data[lo:hi]
        if allowed_ids is not None:
            scores[~np.isin(self.ids, np.fromiter(allowed_ids, dtype=np.int64))] = 0.0
        return top_k(self.ids, scores, k)

    # --- persistence -----------------------------------------------------------------------
    def save(self, path: Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        assert self.matrix is not None, "build() first"
        sparse.save_npz(path / "bm25.npz", self.matrix)
        np.save(path / "bm25_ids.npy", self.ids)
        (path / "bm25_vocab.json").write_text(json.dumps({"k1": self.k1, "b": self.b, "vocab": self.vocab}))

    @classmethod
    def load(cls, path: Path) -> BM25Index:
        path = Path(path)
        meta = json.loads((path / "bm25_vocab.json").read_text())
        idx = cls(meta["k1"], meta["b"])
        idx.vocab = meta["vocab"]
        idx.ids = np.load(path / "bm25_ids.npy")
        idx.matrix = sparse.load_npz(path / "bm25.npz").tocsc()
        return idx


def top_k(ids: np.ndarray, scores: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Top-k positive scores, best first; ties broken by position (stable)."""
    pos = np.flatnonzero(scores > 0)
    if not len(pos):
        return []
    if len(pos) > k:
        pos = pos[np.argpartition(-scores[pos], k - 1)[:k]]
    pos = pos[np.lexsort((pos, -scores[pos]))]
    return [(int(ids[i]), float(scores[i])) for i in pos]
