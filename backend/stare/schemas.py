"""Domain objects shared by every STARE module.

These Pydantic models are the contract between the agents, the Citation Firewall, the API and the UI.
They are serialised into the LangGraph ResearchState and into the JSON columns of the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ----------------------------------------------------------------------------------------------
# Courts
# ----------------------------------------------------------------------------------------------

CourtLevel = Literal["supreme", "appellate", "district", "bankruptcy", "state", "other"]


class Court(BaseModel):
    id: str  # CourtListener court id, e.g. "scotus", "ca5", "txnd"
    name: str  # "United States District Court for the Northern District of Texas"
    short_name: str  # "N.D. Tex."
    level: CourtLevel
    circuit: str | None = None  # "1".."11", "dc", "fed"; None for SCOTUS
    state: str | None = None  # two-letter state for district courts


AuthorityStatus = Literal["binding", "persuasive", "flagged"]


class AuthorityRank(BaseModel):
    status: AuthorityStatus
    weight: float  # 0..1 initial weights from Table 26
    reason: str  # shown to the lawyer, e.g. "Court of appeals for Texas (Fifth Circuit)"


# ----------------------------------------------------------------------------------------------
# Intake
# ----------------------------------------------------------------------------------------------


class PageText(BaseModel):
    page_no: int
    text: str
    ocr_used: bool = False


class ExtractedDocument(BaseModel):
    text: str
    pages: list[PageText]
    ocr_used: bool = False
    page_count: int = 0


class RedactedEntity(BaseModel):
    entity_type: str  # PERSON, EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, LOCATION, DATE_OF_BIRTH, ...
    placeholder: str  # "[PERSON_1]"
    start: int  # offsets in the *redacted* text
    end: int
    score: float = 1.0


class RedactionResult(BaseModel):
    text: str  # redacted text: the only text that may reach an LLM or the database
    entities: list[RedactedEntity] = Field(default_factory=list)
    engine: Literal["presidio", "regex"] = "regex"

    @property
    def count(self) -> int:
        return len(self.entities)


Statute = Literal["title_vii", "ada", "adea"]


class Claim(BaseModel):
    statute: Statute
    theory: str  # "disparate_treatment" | "retaliation" | "hostile_work_environment" | "failure_to_accommodate" | ...
    description: str = ""


class Party(BaseModel):
    role: Literal["plaintiff", "defendant", "other"]
    name: str  # redacted placeholder for the client, real name allowed for corporate defendants


class KeyDate(BaseModel):
    label: str  # "Termination", "EEOC charge filed", "Right-to-sue letter"
    date: str  # ISO date or "2026-03" when only month known


class CaseRecord(BaseModel):
    court_id: str | None = None
    court_name: str | None = None
    circuit: str | None = None
    parties: list[Party] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    key_dates: list[KeyDate] = Field(default_factory=list)
    procedural_posture: str = ""
    facts_summary: str = ""
    redaction_count: int = 0
    client_side: Literal["plaintiff", "defendant"] = "plaintiff"


# ----------------------------------------------------------------------------------------------
# Research plan
# ----------------------------------------------------------------------------------------------


class PlanItem(BaseModel):
    id: str  # "P1"
    issue: str  # "Elements of a Title VII retaliation claim"
    statute: Statute | None = None
    elements: list[str] = Field(default_factory=list)  # legal elements the Research Agent queries
    queries: list[str] = Field(default_factory=list)  # filled by the Research Agent
    checked: bool = True  # attorney may untick an item


class ResearchPlan(BaseModel):
    question: str
    court_id: str | None = None
    items: list[PlanItem] = Field(default_factory=list)
    include_adverse: bool = True
    instructions: str = ""  # free-text instruction added by the attorney
    approved_by: int | None = None
    approved_at: datetime | None = None


# ----------------------------------------------------------------------------------------------
# Retrieval
# ----------------------------------------------------------------------------------------------

SourceKind = Literal["opinion", "statute", "regulation"]


class RetrievedChunk(BaseModel):
    chunk_id: int
    kind: SourceKind
    opinion_id: int | None = None
    section_id: int | None = None
    text: str
    part: str = "majority"  # majority | dissent | concurrence | separate (opinion of the court vs separate opinions)
    bm25_rank: int | None = None
    dense_rank: int | None = None
    rrf_score: float = 0.0
    rerank_score: float | None = None
    query: str = ""


# ----------------------------------------------------------------------------------------------
# Authorities
# ----------------------------------------------------------------------------------------------


class Authority(BaseModel):
    """A case, statute section or regulation proposed as support (or as adverse authority)."""

    key: str  # stable id: "op:123" or "sec:45"
    kind: Literal["case", "statute", "regulation"]
    citation: str  # canonical: "411 U.S. 792" / "42 U.S.C. § 2000e-3(a)"
    case_name: str = ""  # "McDonnell Douglas Corp. v. Green" (empty for statutes)
    court_id: str | None = None
    court_name: str | None = None
    year: int | None = None
    date_filed: str | None = None
    published: bool = True
    url: str | None = None
    opinion_id: int | None = None
    section_id: int | None = None
    relevance: float = 0.0  # retrieval score normalised 0..1
    rank: AuthorityRank | None = None
    final_score: float = 0.0
    passages: list[RetrievedChunk] = Field(default_factory=list)
    proposition: str = ""  # what the authority is cited for
    quote: str = ""  # exact quotation proposed for the memo (must pass Gate 3)
    plan_item_id: str | None = None
    adverse: bool = False
    adverse_reason: str = ""
    verification: CitationCheck | None = None


# ----------------------------------------------------------------------------------------------
# Citation Firewall
# ----------------------------------------------------------------------------------------------

GateOutcome = Literal["pass", "warn", "fail", "skip", "unresolved"]
CheckStatus = Literal["verified", "warning", "blocked", "unresolved"]


class GateResult(BaseModel):
    gate: Literal[1, 2, 3, 4]
    name: Literal["extract", "exists", "quote_match", "good_law"]
    outcome: GateOutcome
    detail: str = ""
    score: float | None = None  # similarity for gates 2 (case-name) and 3 (quote)


class ExtractedCitation(BaseModel):
    raw: str  # "Varghese v. China Southern Airlines Co., 925 F.3d 1339 (11th Cir. 2019)"
    cite: str  # "925 F.3d 1339"
    volume: str | None = None
    reporter: str | None = None  # normalised reporter, e.g. "F.3d"
    page: str | None = None
    pin_cite: str | None = None
    case_name: str = ""  # "Varghese v. China Southern Airlines Co."
    year: int | None = None
    court_hint: str | None = None  # "11th Cir."
    quote: str = ""  # quoted text attached to the citation in the draft
    span: tuple[int, int] = (0, 0)  # char offsets of the citation in the checked text
    quote_spans: list[tuple[int, int]] = Field(default_factory=list)  # offsets of the attached quotations
    # quotations in a later sentence, linked to this citation by position only (a guess, so a mismatch removes the
    # quotation rather than blocking the citation)
    later_quote: str = ""
    later_quote_spans: list[tuple[int, int]] = Field(default_factory=list)
    kind: Literal["case", "statute", "regulation", "short_form", "id", "unknown"] = "case"


class CitationCheck(BaseModel):
    citation: ExtractedCitation
    gates: list[GateResult] = Field(default_factory=list)
    status: CheckStatus = "unresolved"
    reason: str = ""  # one line for the source card: "no matching opinion in index or API"
    opinion_id: int | None = None
    matched_case_name: str | None = None
    source: Literal["local", "cap", "cache", "courtlistener", "statute_index"] | None = None
    url: str | None = None
    treatment: list[str] = Field(default_factory=list)  # e.g. ["superseded by statute: ADA Amendments Act of 2008"]
    unsupported_quote_spans: list[tuple[int, int]] = Field(default_factory=list)  # later quotations not in the opinion

    @property
    def exportable(self) -> bool:
        """NFR-01: only verified or attorney-acknowledged warning citations may be exported, and never next to a
        quotation that the cited opinion does not contain."""
        return self.status in ("verified", "warning") and not self.unsupported_quote_spans


# ----------------------------------------------------------------------------------------------
# Memo
# ----------------------------------------------------------------------------------------------


class MemoCitation(BaseModel):
    marker: str  # "[1]"
    citation: str
    case_name: str = ""
    url: str | None = None
    authority_key: str | None = None
    status: CheckStatus = "verified"


class Memo(BaseModel):
    title: str
    question_presented: str
    issue: str
    rule: str
    application: str
    conclusion: str
    adverse_authority: str = ""  # Opposing Counsel report, which the Memo Agent may not drop
    warnings: list[str] = Field(default_factory=list)  # Gate 4 warnings for the attorney
    citations: list[MemoCitation] = Field(default_factory=list)
    removed_citations: list[str] = Field(default_factory=list)  # blocked by the Firewall, listed in trace
    disclaimer: str = ""
    generated_by: str = "offline"  # provider/model that drafted the prose


# ----------------------------------------------------------------------------------------------
# Trace
# ----------------------------------------------------------------------------------------------

AgentName = Literal[
    "orchestrator",
    "intake",
    "research",
    "precedent",
    "opposing_counsel",
    "citation_firewall",
    "memo",
    "export",
]
StepStatus = Literal["waiting", "running", "done", "error", "skipped"]


class TraceEvent(BaseModel):
    run_id: int
    agent: AgentName
    status: StepStatus
    summary: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    data: dict = Field(default_factory=dict)
    seq: int = 0


Authority.model_rebuild()
