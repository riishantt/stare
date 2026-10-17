"""Hybrid retrieval: BM25 + dense (LSA by default) -> RRF -> rerank, with RAG-Fusion and authority grouping."""

from __future__ import annotations

import json
from collections.abc import Callable, Collection

import numpy as np
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from stare.config import Settings, get_settings
from stare.db.models import Chunk, CourtRow, Opinion, StatuteSection
from stare.retrieval.bm25 import BM25Index, top_k
from stare.retrieval.embed import Embedder, get_embedder, load_embedder
from stare.retrieval.rerank import Reranker, get_reranker
from stare.retrieval.rrf import rrf
from stare.schemas import Authority, RetrievedChunk

BATCH = 512
EMBEDDER_FILE = "embedder.joblib"
DENSE_FILE, DENSE_IDS_FILE, META_FILE = "dense.npy", "dense_ids.npy", "index_meta.json"


class IndexNotBuiltError(RuntimeError):
    pass


class IndexStaleError(RuntimeError):
    pass


class HybridRetriever:
    def __init__(self, session_factory: Callable[[], Session], settings: Settings | None = None):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.reranker: Reranker = get_reranker(self.settings)
        self._loaded_mtime: int | None = None
        self._bm25: BM25Index | None = None
        self._embedder: Embedder | None = None
        self._matrix: np.ndarray | None = None  # (n, dim) float32, memory-mapped
        self._dense_ids: np.ndarray | None = None

    # ------------------------------------------------------------------ build
    @classmethod
    def build_index(cls, session: Session, settings: Settings | None = None) -> dict:
        """Fit the embedder over every chunk, store embeddings in Chunk.embedding, build BM25 and save
        everything under settings.index_dir. Returns small stats."""
        settings = settings or get_settings()
        out = settings.index_dir
        out.mkdir(parents=True, exist_ok=True)
        rows = session.execute(select(Chunk.id, Chunk.text).order_by(Chunk.id)).all()
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        if not ids:
            raise IndexNotBuiltError("No chunks in the database; ingest a corpus first (`stare ingest ...`).")

        embedder = get_embedder(settings)
        embedder.fit(texts)
        dense = np.zeros((len(ids), embedder.dim), dtype=np.float32)
        for i in range(0, len(ids), BATCH):
            vecs = embedder.embed(texts[i : i + BATCH])
            dense[i : i + BATCH] = vecs
            session.execute(update(Chunk), [{"id": cid, "embedding": v} for cid, v in zip(ids[i : i + BATCH], vecs)])
            session.commit()

        bm25 = BM25Index()
        bm25.build(ids, texts)
        bm25.save(out)
        embedder.save(out / EMBEDDER_FILE)
        np.save(out / DENSE_FILE, dense)
        np.save(out / DENSE_IDS_FILE, np.asarray(ids, dtype=np.int64))
        (out / META_FILE).write_text(
            json.dumps({"n_chunks": len(ids), "embedder": settings.embedder, "dim": embedder.dim})
        )
        return {"chunks": len(ids), "terms": len(bm25.vocab), "dim": embedder.dim}

    # ------------------------------------------------------------------ load
    def _load(self) -> None:
        d = self.settings.index_dir
        meta_path = d / META_FILE
        needed = [meta_path, d / "bm25.npz", d / EMBEDDER_FILE, d / DENSE_FILE]
        if not all(p.exists() for p in needed):
            raise IndexNotBuiltError(
                f"Retrieval index not found in {d}. Run `stare index build` after ingesting the corpus."
            )
        mtime = meta_path.stat().st_mtime_ns
        if mtime == self._loaded_mtime:
            return
        meta = json.loads(meta_path.read_text())
        with self.session_factory() as s:
            n_db = s.scalar(select(func.count(Chunk.id))) or 0
        if n_db != meta["n_chunks"]:
            raise IndexStaleError(
                f"Retrieval index is stale ({meta['n_chunks']} indexed chunks vs {n_db} in the database). "
                "Run `stare index build` to rebuild it."
            )
        self._bm25 = BM25Index.load(d)
        self._embedder = load_embedder(self.settings, d / EMBEDDER_FILE)
        self._matrix = np.load(d / DENSE_FILE, mmap_mode="r")
        self._dense_ids = np.load(d / DENSE_IDS_FILE)
        self._loaded_mtime = mtime

    # ------------------------------------------------------------------ search
    def _allowed_ids(self, session: Session, kinds, court_ids) -> set[int] | None:
        if not kinds and not court_ids:
            return None
        q = select(Chunk.id)
        if kinds:
            q = q.where(Chunk.kind.in_(kinds))
        if court_ids:
            q = q.join(Opinion, Opinion.id == Chunk.opinion_id).where(Opinion.court_id.in_(court_ids))
        return set(session.scalars(q))

    def _dense_search(
        self, session: Session, query: str, n: int, kinds, court_ids, allowed: set[int] | None
    ) -> list[int]:
        assert self._embedder is not None
        qv = self._embedder.embed([query])[0]
        if not qv.any():
            return []
        if self.settings.is_postgres:  # pgvector: cosine distance operator
            sql = "SELECT c.id FROM chunks c "
            params: dict = {"q": "[" + ",".join(f"{x:.6f}" for x in qv) + "]", "n": n}
            where = ["c.embedding IS NOT NULL"]
            if court_ids:
                sql += "JOIN opinions o ON o.id = c.opinion_id "
                where.append("o.court_id = ANY(:courts)")
                params["courts"] = list(court_ids)
            if kinds:
                where.append("c.kind = ANY(:kinds)")
                params["kinds"] = list(kinds)
            sql += "WHERE " + " AND ".join(where) + " ORDER BY c.embedding <=> CAST(:q AS vector) LIMIT :n"
            return [r[0] for r in session.execute(text(sql), params)]
        assert self._matrix is not None and self._dense_ids is not None
        scores = np.asarray(self._matrix @ qv, dtype=np.float32)
        if allowed is not None:
            scores[~np.isin(self._dense_ids, np.fromiter(allowed, dtype=np.int64))] = 0.0
        return [cid for cid, _ in top_k(self._dense_ids, scores, n)]

    def search(
        self, query: str, k: int = 30, *, kinds: Collection[str] | None = None,
        court_ids: Collection[str] | None = None,
    ) -> list[RetrievedChunk]:
        self._load()
        assert self._bm25 is not None
        n = max(self.settings.candidates_per_query, k)
        with self.session_factory() as s:
            allowed = self._allowed_ids(s, kinds, court_ids)
            bm25_ids = [cid for cid, _ in self._bm25.search(query, n, allowed)]
            dense_ids = self._dense_search(s, query, n, kinds, court_ids, allowed)
            fused = rrf([bm25_ids, dense_ids], self.settings.rrf_k)[: max(2 * k, 50, 0)]
            if not fused:
                return []
            rows = {c.id: c for c in s.scalars(select(Chunk).where(Chunk.id.in_([i for i, _ in fused])))}
        b_rank = {cid: r for r, cid in enumerate(bm25_ids, 1)}
        d_rank = {cid: r for r, cid in enumerate(dense_ids, 1)}
        cands = [
            RetrievedChunk(
                chunk_id=cid, kind=rows[cid].kind, opinion_id=rows[cid].opinion_id,
                section_id=rows[cid].section_id, text=rows[cid].text, part=rows[cid].part or "majority",
                bm25_rank=b_rank.get(cid),
                dense_rank=d_rank.get(cid), rrf_score=score, query=query,
            )
            for cid, score in fused
            if cid in rows
        ]
        return self.reranker.rerank(query, cands)[:k]

    def search_many(self, queries: list[str], k: int = 30, **kw) -> list[RetrievedChunk]:
        """RAG-Fusion: one query per legal element, result lists fused by RRF."""
        per_query = [self.search(q, k=k, **kw) for q in queries]
        fused = rrf([[c.chunk_id for c in res] for res in per_query], self.settings.rrf_k)
        return self._fuse_best(per_query, fused, k)

    @staticmethod
    def _fuse_best(per_query: list[list[RetrievedChunk]], fused, k: int) -> list[RetrievedChunk]:
        best: dict[int, tuple[int, RetrievedChunk]] = {}
        for res in per_query:
            for pos, c in enumerate(res):
                if c.chunk_id not in best or pos < best[c.chunk_id][0]:
                    best[c.chunk_id] = (pos, c)
        return [best[cid][1].model_copy(update={"rrf_score": score}) for cid, score in fused[:k]]

    # ------------------------------------------------------------------ authorities
    def authorities_from_chunks(self, chunks: list[RetrievedChunk], limit: int) -> list[Authority]:
        groups: dict[str, list[RetrievedChunk]] = {}
        for c in chunks:
            if c.opinion_id is not None:
                key = f"op:{c.opinion_id}"
            elif c.section_id is not None:
                key = f"sec:{c.section_id}"
            else:
                continue
            groups.setdefault(key, []).append(c)
        keys = list(groups)[:limit]
        if not keys:
            return []
        with self.session_factory() as s:
            ops = {o.id: o for o in s.scalars(select(Opinion).where(Opinion.id.in_(
                [int(k[3:]) for k in keys if k.startswith("op:")])))}
            secs = {x.id: x for x in s.scalars(select(StatuteSection).where(StatuteSection.id.in_(
                [int(k[4:]) for k in keys if k.startswith("sec:")])))}
            court_names = {
                r.id: r.name
                for r in s.scalars(select(CourtRow).where(CourtRow.id.in_({o.court_id for o in ops.values() if o.court_id})))
            }

        def score(c: RetrievedChunk) -> float:
            return c.rerank_score if c.rerank_score is not None else c.rrf_score

        best = [max(score(c) for c in groups[k]) for k in keys]
        top = max(best) if best and max(best) > 0 else 1.0
        out: list[Authority] = []
        ceiling = 1.0
        for key, b in zip(keys, best):
            ceiling = min(ceiling, max(b, 0.0) / top)  # best-first order => non-increasing relevance
            passages = sorted(groups[key], key=score, reverse=True)[:3]
            if key.startswith("op:") and (o := ops.get(int(key[3:]))):
                out.append(Authority(
                    key=key, kind="case", citation=o.citation, case_name=o.case_name, court_id=o.court_id,
                    court_name=court_names.get(o.court_id), year=o.year, date_filed=o.date_filed,
                    published=o.published, url=o.url, opinion_id=o.id, relevance=round(ceiling, 6),
                    passages=passages,
                ))
            elif key.startswith("sec:") and (x := secs.get(int(key[4:]))):
                out.append(Authority(
                    key=key, kind="regulation" if x.code == "CFR" else "statute", citation=x.citation,
                    case_name="", url=x.url, section_id=x.id, relevance=round(ceiling, 6), passages=passages,
                ))
        return out
