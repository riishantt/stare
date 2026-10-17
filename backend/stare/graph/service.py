"""ResearchService: the only interface the HTTP API uses to drive research runs.

Graph steps run in a small worker pool (or inline when `synchronous=True`, used by tests and the
evaluation harness). Trace events are persisted as AgentStep rows and published on the event bus.
Every state change that matters is written to the audit log.
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from stare.agents.base import AgentDeps
from stare.agents.memo_firewall import MEMO_FIELDS, check_memo, export_violations
from stare.agents.state import dump
from stare.config import Settings, get_settings
from stare.db.models import AgentStep, AuditLog, CaseFile, CitationCheckRow, CourtRow, Document, MemoRow, ResearchRun, User
from stare.export.docx_exporter import MemoExporter
from stare.graph.events import EventBus, EventSubscription, bus
from stare.graph.orchestrator import build_graph
from stare.intake.planner import draft_plan
from stare.llm import get_llm
from stare.llm.base import ChatModel
from stare.schemas import CaseRecord, Memo, ResearchPlan, TraceEvent

EDITABLE_MEMO_FIELDS = MEMO_FIELDS  # every field the Firewall re-checks; nothing else is taken from an edit


class RunStateError(RuntimeError):
    """The run is not in a state that allows the requested action (HTTP 409)."""


class ExportBlockedError(RunStateError):
    def __init__(self, problems: list[str]):
        super().__init__("export blocked: " + "; ".join(problems))
        self.problems = problems


class MemoVerificationError(ValueError):
    """Attorney edits introduced citations that fail the Firewall (HTTP 422)."""

    def __init__(self, problems: list[str]):
        super().__init__("edited memo contains citations that failed verification: " + "; ".join(problems))
        self.problems = problems


def audit(session: Session, user_id: int | None, action: str, entity: str, entity_id: int | None, **detail) -> None:
    session.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail))


class ResearchService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings | None = None,
        llm: ChatModel | None = None,
        *,
        synchronous: bool = False,
        event_bus: EventBus | None = None,
    ):
        self.sf = session_factory
        self.settings = settings or get_settings()
        self.llm = llm or get_llm(self.settings)
        self.bus = event_bus or bus
        self.synchronous = synchronous
        self.deps = AgentDeps(llm=self.llm, session_factory=session_factory, settings=self.settings, emit=self._emit)
        self.graph = build_graph(self.deps)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="stare-run")
        self._locks: dict[int, threading.Lock] = {}
        self._seq_lock = threading.Lock()

    # ================================================================================== public API

    def start_run(self, case_id: int, user_id: int) -> int:
        with self.sf() as s:
            case = s.get(CaseFile, case_id)
            if case is None:
                raise LookupError(f"matter {case_id} not found")
            docs = list(s.scalars(select(Document).where(Document.case_id == case_id).order_by(Document.id)))
            if not docs:
                raise RunStateError("upload at least one document before starting a run")
            run = ResearchRun(case_id=case_id, created_by=user_id, thread_id=uuid.uuid4().hex,
                              status="intake_running", llm_provider=self.llm.name)
            s.add(run)
            s.flush()
            audit(s, user_id, "run.started", "run", run.id, case_id=case_id, documents=[d.id for d in docs])
            s.commit()
            run_id = run.id
            initial = {
                "run_id": run_id, "case_id": case_id, "user_id": user_id,
                "document_ids": [d.id for d in docs],
                "redacted_text": "\n\n".join(d.redacted_text for d in docs),
                "case_record": case.case_record,
            }
            if initial["case_record"] is None:
                initial.pop("case_record")
        self._submit(run_id, lambda: self._invoke(run_id, initial))
        return run_id

    def update_case_record(self, run_id: int, record: CaseRecord, user_id: int) -> None:
        """Save a reviewed case record and redraft the plan from it, so added or removed claims are researched."""
        run = self._require(run_id, "awaiting_plan_approval")
        plan = draft_plan(record, self.llm)
        self.graph.update_state(self._config(run), {"case_record": dump(record), "plan": dump(plan)})
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            row.case_record_json = dump(record)
            row.plan_json = dump(plan)
            case = s.get(CaseFile, row.case_id)
            case.case_record = dump(record)
            case.claims = [c.model_dump() for c in record.claims]
            case.court_id = record.court_id if record.court_id and s.get(CourtRow, record.court_id) else case.court_id
            audit(s, user_id, "case_record.edited", "run", run_id)
            s.commit()

    def approve_plan(self, run_id: int, plan: ResearchPlan, user_id: int) -> None:
        run = self._require(run_id, "awaiting_plan_approval")
        now = datetime.now(UTC)
        plan = plan.model_copy(update={"approved_by": user_id, "approved_at": now})
        with self.sf() as s:
            self._transition(s, run_id, "awaiting_plan_approval", "researching")
            row = s.get(ResearchRun, run_id)
            row.plan_json = dump(plan)
            row.plan_approved_by = user_id
            row.plan_approved_at = now
            audit(s, user_id, "plan.approved", "run", run_id, items=[i.id for i in plan.items if i.checked],
                  instructions=bool(plan.instructions))
            s.commit()
        self._publish_status(run_id, "researching")
        decision = {"action": "approve", "plan": dump(plan), "user_id": user_id, "at_ms": int(time.time() * 1000)}
        self._submit(run_id, lambda: self._invoke(run_id, Command(resume=decision), config=self._config(run)))

    def request_memo_changes(self, run_id: int, instruction: str, user_id: int) -> None:
        run = self._require(run_id, "awaiting_memo_approval")
        with self.sf() as s:
            self._transition(s, run_id, "awaiting_memo_approval", "researching")
            audit(s, user_id, "memo.changes_requested", "run", run_id, instruction_chars=len(instruction))
            s.commit()
        self._publish_status(run_id, "researching")
        decision = {"action": "changes", "instruction": instruction, "user_id": user_id}
        self._submit(run_id, lambda: self._invoke(run_id, Command(resume=decision), config=self._config(run)))

    def approve_memo(self, run_id: int, memo: Memo | None, user_id: int) -> None:
        run = self._require(run_id, "awaiting_memo_approval")
        payload = None
        if memo is not None:
            memo = self._apply_edits(run_id, memo)
            cleaned, _ = check_memo(memo, self.deps.firewall)
            problems = export_violations(memo, self.deps.firewall)
            if problems or len(cleaned.removed_citations) > len(memo.removed_citations):
                raise MemoVerificationError(problems or cleaned.removed_citations[len(memo.removed_citations):])
            payload = dump(cleaned)
        decision = {"action": "approve", "memo": payload, "user_id": user_id}
        with self.sf() as s:  # a second click (or a cancel) that got here first wins
            self._transition(s, run_id, "awaiting_memo_approval", "approved")
            s.commit()
        with self._lock(run_id):  # fast: only the gate node runs
            self._invoke(run_id, Command(resume=decision), config=self._config(run))
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            if row.status != "approved":  # the gate step failed or the run was cancelled meanwhile
                return
            m = s.scalars(select(MemoRow).where(MemoRow.run_id == run_id).order_by(MemoRow.version.desc())).first()
            if m is not None:
                m.approved_by = user_id
                m.approved_at = datetime.now(UTC)
                if payload:
                    m.irac_json = payload
                    m.edited_by = user_id
            row.status = "approved"
            audit(s, user_id, "memo.approved", "run", run_id, edited=memo is not None, memo_version=m.version if m else None)
            s.commit()
        self._publish_status(run_id, "approved")

    def cancel(self, run_id: int, user_id: int) -> None:
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            if row is None:
                raise LookupError(f"run {run_id} not found")
            if row.status in ("exported", "cancelled"):
                raise RunStateError(f"run is already {row.status}")
            row.status = "cancelled"
            row.finished_at = datetime.now(UTC)
            audit(s, user_id, "run.cancelled", "run", run_id)
            s.commit()
        self._publish_status(run_id, "cancelled")

    def export_docx(self, run_id: int, user_id: int) -> bytes:
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            if row is None:
                raise LookupError(f"run {run_id} not found")
            if row.status not in ("approved", "exported"):
                raise RunStateError("the memo must be approved by an attorney before export")
            m = s.scalars(select(MemoRow).where(MemoRow.run_id == run_id).order_by(MemoRow.version.desc())).first()
            if m is None or m.approved_by is None:
                raise RunStateError("no approved memo for this run")
            memo = Memo.model_validate(m.irac_json)
            problems = export_violations(memo, self.deps.firewall)
            if problems:
                audit(s, user_id, "memo.export_blocked", "run", run_id, problems=problems)
                s.commit()
                raise ExportBlockedError(problems)
            case = s.get(CaseFile, row.case_id)
            court = s.get(CourtRow, case.court_id) if case.court_id else None
            approver = s.get(User, m.approved_by)
            checks = [c.check_json for c in s.scalars(select(CitationCheckRow).where(CitationCheckRow.run_id == run_id))]
            data = MemoExporter().to_docx(memo, {
                "matter_number": case.matter_number, "matter_title": case.title,
                "court": court.name if court else "", "approved_by": approver.name if approver else "",
                "approved_at": m.approved_at, "run_id": run_id, "checks": checks,
            })
            m.exported_at = datetime.now(UTC)
            row.status = "exported"
            audit(s, user_id, "memo.exported", "run", run_id, memo_version=m.version, bytes=len(data),
                  citations=len(memo.citations))
            s.commit()
        self._publish_status(run_id, "exported")
        return data

    def subscribe(self, run_id: int) -> EventSubscription:
        return self.bus.subscribe(run_id)

    def wait_idle(self, run_id: int, timeout: float = 120.0) -> None:
        """Block until no graph step is running for this run (used by tests and evaluation)."""
        lock = self._lock(run_id)
        if lock.acquire(timeout=timeout):
            lock.release()

    def snapshot(self, run_id: int) -> dict[str, Any]:
        """Everything the UI needs about a run (RunOut)."""
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            if row is None:
                raise LookupError(f"run {run_id} not found")
            memo = s.scalars(select(MemoRow).where(MemoRow.run_id == run_id).order_by(MemoRow.version.desc())).first()
            steps = list(s.scalars(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.seq)))
            checks = list(s.scalars(select(CitationCheckRow).where(CitationCheckRow.run_id == run_id).order_by(CitationCheckRow.id)))
            return {
                "id": row.id, "case_id": row.case_id, "status": row.status,
                "case_record": row.case_record_json, "plan": row.plan_json,
                "authorities": row.authorities_json or [], "adverse": row.adverse_json or [],
                "checks": [c.check_json | {"phase": c.phase} for c in checks],
                "memo": memo.irac_json if memo else None,
                "memo_version": memo.version if memo else None,
                "memo_approved_by": memo.approved_by if memo else None,
                "memo_approved_at": memo.approved_at if memo else None,
                "steps": [_step_dict(st) for st in steps],
                "latency_ms": row.latency_ms, "cost_usd": row.cost_usd, "llm_provider": row.llm_provider,
                "created_at": row.created_at, "plan_approved_by": row.plan_approved_by,
                "plan_approved_at": row.plan_approved_at, "loop_count": row.loop_count, "error": row.error,
            }

    # ================================================================================== internals

    def _config(self, run: ResearchRun) -> dict:
        return {"configurable": {"thread_id": run.thread_id}, "recursion_limit": 60}

    def _require(self, run_id: int, status: str) -> ResearchRun:
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
        if row is None:
            raise LookupError(f"run {run_id} not found")
        if row.status != status:
            raise RunStateError(f"run is '{row.status}', expected '{status}'")
        return row

    @staticmethod
    def _transition(s: Session, run_id: int, expected: str, new: str) -> None:
        """Atomically move a run from `expected` to `new`. Two approvals racing for the same gate must not
        both resume the graph: the second would be delivered to the *next* interrupt (e.g. a plan approval
        approving the memo)."""
        res = s.execute(update(ResearchRun).where(ResearchRun.id == run_id, ResearchRun.status == expected)
                        .values(status=new))
        if res.rowcount != 1:
            current = s.scalar(select(ResearchRun.status).where(ResearchRun.id == run_id))
            raise RunStateError(f"run is '{current}', expected '{expected}'")

    def _apply_edits(self, run_id: int, edited: Memo) -> Memo:
        """Take only the prose from an attorney-edited memo. The reference list, Firewall warnings and
        removals are the server's: a client cannot add a reference marked 'verified' or drop a warning."""
        with self.sf() as s:
            m = s.scalars(select(MemoRow).where(MemoRow.run_id == run_id).order_by(MemoRow.version.desc())).first()
        if m is None:
            raise RunStateError("no memo to approve for this run")
        current = Memo.model_validate(m.irac_json)
        return current.model_copy(update={f: getattr(edited, f) for f in EDITABLE_MEMO_FIELDS})

    def _lock(self, run_id: int) -> threading.Lock:
        with self._seq_lock:
            return self._locks.setdefault(run_id, threading.Lock())

    def _submit(self, run_id: int, fn) -> None:
        lock = self._lock(run_id)
        lock.acquire()  # released by the worker; serialises steps of one run

        def task():
            try:
                fn()
            finally:
                lock.release()

        if self.synchronous:
            task()
        else:
            self.pool.submit(task)

    def _invoke(self, run_id: int, payload: Any, config: dict | None = None) -> None:
        if config is None:
            with self.sf() as s:
                config = self._config(s.get(ResearchRun, run_id))
        try:
            self.graph.invoke(payload, config)
        except Exception as exc:  # a failed run is recorded, never left hanging
            with self.sf() as s:
                row = s.get(ResearchRun, run_id)
                if row.status == "cancelled":
                    return
                row.status = "failed"
                row.error = f"{type(exc).__name__}: {exc}"
                row.finished_at = datetime.now(UTC)
                audit(s, None, "run.failed", "run", run_id, error=row.error)
                s.commit()
            self._publish_status(run_id, "failed", error=str(exc))
            if self.synchronous:
                raise
            return
        self._sync_from_graph(run_id, config)

    def _sync_from_graph(self, run_id: int, config: dict) -> None:
        snap = self.graph.get_state(config)
        values = snap.values
        waiting = {i.value.get("type") for t in snap.tasks for i in t.interrupts}
        with self.sf() as s:
            row = s.get(ResearchRun, run_id)
            if row.status == "cancelled":
                return
            row.case_record_json = values.get("case_record")
            row.plan_json = values.get("plan")
            row.authorities_json = values.get("verified") or values.get("shortlist")
            row.adverse_json = values.get("adverse")
            row.loop_count = values.get("loop_count", 0)
            row.cost_usd = round(self.llm.usage.cost_usd, 4)
            if "plan_approval" in waiting:
                row.status = "awaiting_plan_approval"
                case = s.get(CaseFile, row.case_id)
                if case.case_record is None:
                    case.case_record = values.get("case_record")
                    rec = CaseRecord.model_validate(values.get("case_record") or {})
                    case.claims = [c.model_dump() for c in rec.claims]
                    if rec.court_id and s.get(CourtRow, rec.court_id) and not case.court_id:
                        case.court_id = rec.court_id
            elif "memo_approval" in waiting:
                row.status = "awaiting_memo_approval"
                if values.get("plan_approved_at_ms"):
                    row.latency_ms = int(time.time() * 1000) - values["plan_approved_at_ms"]
                self._store_memo_and_checks(s, row, values)
            elif not snap.next:
                row.status = "approved" if values.get("memo_approved") else values.get("status", row.status)
                row.finished_at = datetime.now(UTC)
            s.commit()
            status = row.status
        self._publish_status(run_id, status)

    def _store_memo_and_checks(self, s: Session, row: ResearchRun, values: dict) -> None:
        memo = values.get("memo")
        if memo:
            latest = s.scalars(select(MemoRow).where(MemoRow.run_id == row.id).order_by(MemoRow.version.desc())).first()
            if latest is None or latest.irac_json != memo:
                s.add(MemoRow(run_id=row.id, version=(latest.version + 1) if latest else 1, irac_json=memo))
        s.query(CitationCheckRow).filter(CitationCheckRow.run_id == row.id).delete()
        for c in values.get("checks") or []:
            gates = {g["gate"]: g["outcome"] for g in c.get("gates", [])}
            s.add(CitationCheckRow(
                run_id=row.id, opinion_id=c.get("opinion_id"), raw_citation=c["citation"].get("raw") or c["citation"]["cite"],
                phase=c.get("phase", "candidates"),
                exists=None if 2 not in gates else gates[2] == "pass",
                quote_ok=None if gates.get(3) in (None, "skip") else gates[3] == "pass",
                good_law=None if gates.get(4) in (None, "skip", "unresolved") else gates[4] == "pass",
                status=c["status"], reason=c.get("reason", ""), check_json={k: v for k, v in c.items() if k != "phase"},
            ))

    def _emit(self, event: TraceEvent) -> None:
        with self.sf() as s:
            seq = (s.scalar(select(func.max(AgentStep.seq)).where(AgentStep.run_id == event.run_id)) or 0) + 1
            event = event.model_copy(update={"seq": seq})
            s.add(AgentStep(
                run_id=event.run_id, seq=seq, agent_name=event.agent, status=event.status, summary=event.summary,
                output_json=event.data, started_at=event.started_at, ended_at=event.ended_at,
                duration_ms=event.duration_ms,
            ))
            s.commit()
        self.bus.publish(event.run_id, {"type": "trace", **event.model_dump(mode="json")})

    def _publish_status(self, run_id: int, status: str, **extra) -> None:
        self.bus.publish(run_id, {"type": "status", "run_id": run_id, "status": status, **extra})


def _step_dict(st: AgentStep) -> dict:
    return {
        "seq": st.seq, "agent": st.agent_name, "status": st.status, "summary": st.summary, "data": st.output_json,
        "started_at": st.started_at, "ended_at": st.ended_at, "duration_ms": st.duration_ms,
    }
