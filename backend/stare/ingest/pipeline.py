"""Corpus build: courts + seed + statutes + chunks (the retrieval index is built by `stare index build`),
and the monthly refresh of the same sources (Section 5.4.2)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from stare.text import part_at
from stare.config import Settings, get_settings
from stare.courts.hierarchy import CourtHierarchy
from stare.db.models import Chunk, CourtRow, Opinion, StatuteSection
from stare.ingest.chunker import chunk_text
from stare.ingest.seed import build_seed
from stare.ingest.statutes import fetch_statutes, import_statutes


def load_courts(session: Session) -> int:
    n = 0
    for c in CourtHierarchy.default().all():
        row = session.get(CourtRow, c.id)
        if row is None:
            row = CourtRow(id=c.id)
            session.add(row)
        row.name, row.short_name, row.level, row.circuit, row.state = c.name, c.short_name, c.level, c.circuit, c.state
        n += 1
    session.commit()
    return n


def rebuild_chunks(session: Session, *, settings: Settings | None = None, batch: int = 200) -> int:
    """Delete and rebuild chunks for every opinion and statute section. Embeddings are left NULL."""
    s = settings or get_settings()
    session.execute(delete(Chunk))
    session.flush()
    total = 0
    for i, (op_id, text) in enumerate(session.execute(select(Opinion.id, Opinion.plain_text)).all(), 1):
        for ordinal, (start, piece) in enumerate(chunk_text(text, s.chunk_tokens, s.chunk_overlap)):
            session.add(Chunk(kind="opinion", opinion_id=op_id, ordinal=ordinal, text=piece, char_start=start,
                              part=part_at(text, start + min(len(piece) // 2, 200))))
            total += 1
        if i % batch == 0:
            session.flush()
    for sec in session.scalars(select(StatuteSection)):
        kind = "regulation" if sec.code == "CFR" else "statute"
        prefix = f"{sec.citation} {sec.heading}\n"
        for ordinal, (start, piece) in enumerate(chunk_text(sec.text, s.chunk_tokens, s.chunk_overlap)):
            session.add(Chunk(kind=kind, section_id=sec.id, ordinal=ordinal, text=prefix + piece, char_start=start))
            total += 1
    session.commit()
    return total


def corpus_counts(session: Session) -> dict[str, int]:
    from stare.db.models import Citation, CitationEdge, Treatment

    def n(model) -> int:
        return session.scalar(select(func.count()).select_from(model)) or 0

    return {
        "courts": n(CourtRow), "opinions": n(Opinion), "citations": n(Citation), "edges": n(CitationEdge),
        "treatments": n(Treatment), "statute_sections": n(StatuteSection), "chunks": n(Chunk),
    }


def build_corpus(session: Session, *, offline_only: bool = True,
                 say: Callable[[str], None] = lambda s: None) -> dict[str, int]:
    """courts + seed + statutes + chunks. (Retrieval index build is `HybridRetriever.build_index`.)"""
    load_courts(session)
    seed = build_seed(session, offline=offline_only, say=say)
    say(f"seed: {seed}")
    import_statutes(session, offline=offline_only, say=say)
    rebuild_chunks(session)
    return corpus_counts(session)


def refresh_corpus(session: Session, *, settings: Settings | None = None, bulk_dir: Path | None = None,
                   online: bool = True, say: Callable[[str], None] = lambda s: None) -> dict[str, int]:
    """Monthly refresh: import a newer CourtListener bulk download (new opinions and citing cases for
    Gate 4), fetch seed cases added to the manifest, re-download the statute and regulation text, and
    rebuild the chunks. Records the time in data/refresh.json. Rebuild the retrieval index afterwards."""
    from stare.ingest.courtlistener_bulk import import_courtlistener_bulk

    s = settings or get_settings()
    before = corpus_counts(session)
    load_courts(session)
    if bulk_dir is not None:
        say(f"bulk: {import_courtlistener_bulk(Path(bulk_dir), session=session, say=say)}")
    say(f"seed: {build_seed(session, offline=not online, say=say)}")
    if online:
        fetch_statutes(say=say, refetch=True)
    import_statutes(session, offline=True, say=say)
    rebuild_chunks(session, settings=s)
    after = corpus_counts(session)
    stamp = {"refreshed_at": datetime.now(UTC).isoformat(timespec="seconds"), "bulk_dir": str(bulk_dir or ""),
             "online": online, "before": before, "after": after}
    (s.data_dir / "refresh.json").write_text(json.dumps(stamp, indent=2))
    return after
