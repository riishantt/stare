"""Relational schema (Figure 11 of the proposal, plus the tables the implementation needs).

Works on SQLite (laptop default) and on PostgreSQL 16 + pgvector (production). Embeddings use
EmbeddingType: a pgvector `vector(dim)` column on PostgreSQL and a float32 BLOB on SQLite.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from stare.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class EmbeddingType(TypeDecorator):
    """numpy float32 vector <-> pgvector (PostgreSQL) or raw bytes (SQLite)."""

    impl = LargeBinary
    cache_ok = True

    def __init__(self, dim: int | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim or get_settings().embedding_dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector  # optional dependency

            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(LargeBinary())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        arr = np.asarray(value, dtype=np.float32)
        if dialect.name == "postgresql":
            return arr.tolist()
        return arr.tobytes()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):
            return np.frombuffer(bytes(value), dtype=np.float32)
        return np.asarray(value, dtype=np.float32)


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


# ==============================================================================================
# Users and matters
# ==============================================================================================


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # attorney | paralegal | admin
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CaseFile(Base):
    """A matter. Named CASE_FILE in the ER diagram."""

    __tablename__ = "case_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    matter_number: Mapped[str] = mapped_column(String(40), unique=True)  # "M-0142"
    title: Mapped[str] = mapped_column(String(300))  # "[PLAINTIFF] v. Acme Logistics Inc."
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    court_id: Mapped[str | None] = mapped_column(ForeignKey("courts.id"), nullable=True)
    claims: Mapped[list] = mapped_column(JSON, default=list)  # list[Claim] as dicts
    case_record: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # CaseRecord as dict
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list[Document]] = relationship(back_populates="case_file", cascade="all, delete-orphan")
    runs: Mapped[list[ResearchRun]] = relationship(back_populates="case_file", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case_files.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(300))
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    redacted_text: Mapped[str] = mapped_column(Text)  # raw text is never stored (NFR-03)
    redaction_entities: Mapped[list] = mapped_column(JSON, default=list)  # list[RedactedEntity]
    redaction_engine: Mapped[str] = mapped_column(String(20), default="regex")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    case_file: Mapped[CaseFile] = relationship(back_populates="documents")


# ==============================================================================================
# Research runs
# ==============================================================================================

RUN_STATUSES = (
    "created",
    "intake_running",
    "awaiting_plan_approval",
    "researching",
    "awaiting_memo_approval",
    "approved",
    "exported",
    "failed",
    "cancelled",
)


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case_files.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)  # LangGraph checkpoint thread
    status: Mapped[str] = mapped_column(String(30), default="created")
    case_record_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    authorities_json: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[Authority]
    adverse_json: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[Authority]
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    loop_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # approved plan -> memo
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    llm_provider: Mapped[str] = mapped_column(String(40), default="offline")
    plan_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    plan_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case_file: Mapped[CaseFile] = relationship(back_populates="runs")
    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.seq"
    )
    checks: Mapped[list[CitationCheckRow]] = relationship(back_populates="run", cascade="all, delete-orphan")
    memos: Mapped[list[MemoRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="MemoRow.version"
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    agent_name: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text, default="")
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped[ResearchRun] = relationship(back_populates="steps")


class CitationCheckRow(Base):
    __tablename__ = "citation_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    opinion_id: Mapped[int | None] = mapped_column(ForeignKey("opinions.id"), nullable=True)
    raw_citation: Mapped[str] = mapped_column(Text)
    phase: Mapped[str] = mapped_column(String(20), default="candidates")  # candidates | adverse | memo
    exists: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    quote_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    good_law: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # verified | warning | blocked | unresolved
    reason: Mapped[str] = mapped_column(Text, default="")
    check_json: Mapped[dict] = mapped_column(JSON, default=dict)  # full CitationCheck
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[ResearchRun] = relationship(back_populates="checks")


class MemoRow(Base):
    __tablename__ = "memos"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("research_runs.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    irac_json: Mapped[dict] = mapped_column(JSON)  # Memo
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[ResearchRun] = relationship(back_populates="memos")


class AuditLog(Base):
    """Append-only record of every run, approval, export and admin action (FR-12, NFR-05)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))  # e.g. "plan.approved", "memo.exported"
    entity: Mapped[str] = mapped_column(String(40))  # "run", "matter", "document", "user"
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # never raw client text


class Setting(Base):
    """Administrator-editable settings (retention, model choice)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


# ==============================================================================================
# Legal corpus
# ==============================================================================================


class CourtRow(Base):
    __tablename__ = "courts"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # CourtListener id
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(60))
    level: Mapped[str] = mapped_column(String(20))
    circuit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    state: Mapped[str | None] = mapped_column(String(4), nullable=True)


class Opinion(Base):
    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(primary_key=True)
    court_id: Mapped[str | None] = mapped_column(ForeignKey("courts.id"), nullable=True, index=True)
    case_name: Mapped[str] = mapped_column(String(500))
    case_name_full: Mapped[str] = mapped_column(Text, default="")
    citation: Mapped[str] = mapped_column(String(80), index=True)  # preferred citation "411 U.S. 792"
    date_filed: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_number: Mapped[str] = mapped_column(String(200), default="")
    published: Mapped[bool] = mapped_column(Boolean, default=True)
    plain_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30))  # cap | courtlistener | courtlistener_bulk | fixture
    source_id: Mapped[str] = mapped_column(String(80), default="")  # stable id in the source
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_opinion_source"),)


class Citation(Base):
    """Citation index: (volume, reporter, page) -> opinion. One opinion has official + parallel cites."""

    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    opinion_id: Mapped[int] = mapped_column(ForeignKey("opinions.id"), index=True)
    volume: Mapped[str] = mapped_column(String(20))
    reporter: Mapped[str] = mapped_column(String(40))  # normalised with eyecite/reporters-db
    page: Mapped[str] = mapped_column(String(20))
    cite: Mapped[str] = mapped_column(String(80))  # "411 U.S. 792"
    cite_type: Mapped[str] = mapped_column(String(20), default="official")  # official | parallel | vendor

    __table_args__ = (
        UniqueConstraint("volume", "reporter", "page", "opinion_id", name="uq_citation"),
        Index("ix_citation_lookup", "volume", "reporter", "page"),
    )


class CitationEdge(Base):
    """citing opinion -> cited opinion. Gate 4 scans the citing side for negative treatment."""

    __tablename__ = "citation_edges"

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_id: Mapped[int] = mapped_column(ForeignKey("opinions.id"), index=True)
    cited_id: Mapped[int] = mapped_column(ForeignKey("opinions.id"), index=True)
    treatment: Mapped[str | None] = mapped_column(String(40), nullable=True)  # None | positive | negative:overruled ...
    context: Mapped[str] = mapped_column(Text, default="")  # sentence around the citation

    __table_args__ = (UniqueConstraint("citing_id", "cited_id", name="uq_edge"),)


class Treatment(Base):
    """Curated or classifier-derived treatment that is not visible in the citation network,
    e.g. legislative supersession ("superseded by the ADA Amendments Act of 2008")."""

    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(primary_key=True)
    opinion_id: Mapped[int] = mapped_column(ForeignKey("opinions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # overruled | abrogated | superseded_by_statute | ...
    by: Mapped[str] = mapped_column(String(300))  # "ADA Amendments Act of 2008, Pub. L. 110-325"
    note: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="warning")  # warning | negative
    source: Mapped[str] = mapped_column(String(40), default="curated")


class StatuteSection(Base):
    __tablename__ = "statute_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10))  # USC | CFR
    title: Mapped[int] = mapped_column(Integer)  # 42, 29
    section: Mapped[str] = mapped_column(String(30))  # "2000e-3", "1630.2"
    citation: Mapped[str] = mapped_column(String(80), unique=True)  # "42 U.S.C. § 2000e-3"
    heading: Mapped[str] = mapped_column(String(500))
    statute: Mapped[str | None] = mapped_column(String(20), nullable=True)  # title_vii | ada | adea
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="uscode")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # opinion | statute | regulation
    opinion_id: Mapped[int | None] = mapped_column(ForeignKey("opinions.id"), nullable=True, index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("statute_sections.id"), nullable=True, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    part: Mapped[str] = mapped_column(String(20), default="majority")  # majority | dissent | concurrence | separate
    embedding: Mapped[np.ndarray | None] = mapped_column(EmbeddingType(), nullable=True)
