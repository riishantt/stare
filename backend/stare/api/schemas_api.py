"""Request and response models of the HTTP API (CONTRACTS section 8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from stare.schemas import CitationCheck

Role = Literal["attorney", "paralegal", "admin"]


# ---- auth and users ------------------------------------------------------------------------------
class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: Role
    active: bool = True
    created_at: datetime | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: Role


class UserPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


# ---- matters and documents ---------------------------------------------------------------------------
class MatterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    court_id: str | None = None
    notes: str = ""


class EntityOut(BaseModel):
    entity_type: str
    placeholder: str
    start: int | None = None
    end: int | None = None


class DocumentOut(BaseModel):
    id: int
    file_name: str
    page_count: int
    ocr_used: bool
    redacted_text: str
    redaction_count: int
    entities: list[EntityOut]
    redaction_engine: str
    created_at: datetime | None = None


class DocumentPatch(BaseModel):
    redacted_text: str = Field(max_length=2_000_000)


class MatterSummary(BaseModel):
    id: int
    matter_number: str
    title: str
    court_id: str | None = None
    court_name: str | None = None
    claims: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    created_at: datetime | None = None
    last_run_status: str | None = None
    document_count: int = 0


class RunBrief(BaseModel):
    id: int
    status: str
    created_at: datetime | None = None
    llm_provider: str = ""


class MatterDetail(MatterSummary):
    notes: str = ""
    case_record: dict[str, Any] | None = None
    documents: list[DocumentOut] = Field(default_factory=list)
    runs: list[RunBrief] = Field(default_factory=list)


# ---- runs ----------------------------------------------------------------------------------------
class RunOut(BaseModel):
    """Mirrors ResearchService.snapshot()."""

    id: int
    case_id: int
    status: str
    case_record: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    authorities: list[dict[str, Any]] = Field(default_factory=list)
    adverse: list[dict[str, Any]] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
    memo: dict[str, Any] | None = None
    memo_version: int | None = None
    memo_approved_by: int | None = None
    memo_approved_at: datetime | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int | None = None
    cost_usd: float = 0.0
    llm_provider: str = ""
    created_at: datetime | None = None
    plan_approved_by: int | None = None
    plan_approved_at: datetime | None = None
    loop_count: int = 0
    error: str | None = None


class MemoChangesIn(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)


class GraphNode(BaseModel):
    id: str
    label: str
    citation: str
    status: str | None = None
    check_status: str | None = None
    court: str | None = None
    year: int | None = None
    adverse: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    treatment: str | None = None


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class OpinionOut(BaseModel):
    id: int
    case_name: str
    citation: str
    court: str | None = None
    court_id: str | None = None
    date_filed: str | None = None
    url: str | None = None
    text: str


# ---- firewall ----------------------------------------------------------------------------------------
class FirewallCheckIn(BaseModel):
    text: str = Field(min_length=1, max_length=300_000)


class FirewallCheckOut(BaseModel):
    checks: list[CitationCheck]
    summary: str
    counts: dict[str, int]
    exportable: bool
    cleaned_text: str
    removed: list[str]
    redaction_count: int = 0


# ---- admin -----------------------------------------------------------------------------------------
class AuditOut(BaseModel):
    id: int
    at: datetime
    user_id: int | None = None
    user_name: str | None = None
    action: str
    entity: str
    entity_id: int | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class SettingsOut(BaseModel):
    retention_days: int
    llm_provider: str
    model: str
    fast_model: str


class SettingsPatch(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class HealthOut(BaseModel):
    status: str
    version: str
    llm_provider: str
    corpus: dict[str, int]
    index_built: bool
