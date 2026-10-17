"""`stare` command line. Sub-apps: db, ingest, index (other modules add commands here)."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="STARE: verified US employment-discrimination legal research", no_args_is_help=True)
db_app = typer.Typer(help="Database setup", no_args_is_help=True)
ingest_app = typer.Typer(help="Corpus ingestion", no_args_is_help=True)
eval_app = typer.Typer(help="Evaluation (Table 29 metrics)", no_args_is_help=True)
app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")
app.add_typer(eval_app, name="eval")

DEMO_USERS = [
    ("Daniel Ortiz", "attorney@stare.local", "attorney"),
    ("Kevin Lee", "paralegal@stare.local", "paralegal"),
    ("Linda Park", "admin@stare.local", "admin"),
]
DEMO_PASSWORD = "stare-demo"


def _echo(msg: str) -> None:
    typer.echo(msg)


# ---- db -----------------------------------------------------------------------------------------


@db_app.command("init")
def db_init() -> None:
    """Create all tables."""
    from stare.db import init_db

    init_db()
    _echo("database initialised")


def seed_users(session) -> int:
    from sqlalchemy import select

    from stare.api.auth import create_user
    from stare.db.models import User

    added = 0
    for name, email, role in DEMO_USERS:
        if session.scalar(select(User.id).where(User.email == email)):
            continue
        create_user(session, name, email, DEMO_PASSWORD, role)
        added += 1
    session.commit()
    return added


@db_app.command("seed-users")
def db_seed_users() -> None:
    """Create the demo users (attorney / paralegal / admin @stare.local, password 'stare-demo')."""
    from stare.db import init_db, session_scope

    init_db()
    with session_scope() as s:
        n = seed_users(s)
    _echo(f"{n} demo user(s) created")


# ---- ingest -------------------------------------------------------------------------------------


@ingest_app.command("courts")
def ingest_courts() -> None:
    """Load the federal court registry into the courts table."""
    from stare.db import init_db, session_scope
    from stare.ingest.pipeline import load_courts

    init_db()
    with session_scope() as s:
        _echo(f"{load_courts(s)} courts")


@ingest_app.command("seed")
def ingest_seed(offline: bool = typer.Option(False, help="Build only from cached raw files (no network)")) -> None:
    """Build the seed corpus (opinions, citations, edges, treatments) from data/seed/manifest.json."""
    from stare.db import init_db, session_scope
    from stare.ingest.pipeline import load_courts
    from stare.ingest.seed import build_seed

    init_db()
    with session_scope() as s:
        load_courts(s)
        _echo(str(build_seed(s, offline=offline, say=_echo)))


@ingest_app.command("statutes")
def ingest_statutes(offline: bool = typer.Option(False, help="Build only from cached raw files (no network)")) -> None:
    """Import Title VII, ADA Title I, ADEA and 29 C.F.R. 1601/1625/1630."""
    from stare.db import init_db, session_scope
    from stare.ingest.statutes import import_statutes

    init_db()
    with session_scope() as s:
        _echo(f"{import_statutes(s, offline=offline, say=_echo)} statute/regulation sections")


@ingest_app.command("chunks")
def ingest_chunks() -> None:
    """(Re)build chunks for every opinion and statute section (embeddings left NULL)."""
    from stare.db import init_db, session_scope
    from stare.ingest.pipeline import rebuild_chunks

    init_db()
    with session_scope() as s:
        _echo(f"{rebuild_chunks(s)} chunks")


@ingest_app.command("cap-bulk")
def ingest_cap_bulk(
    path: Path = typer.Argument(..., exists=True, help="Downloaded CAP reporter volume (or directory of volumes)"),
    limit: int = typer.Option(0, help="Stop after N opinions (0 = no limit)"),
    all_cases: bool = typer.Option(False, "--all", help="Do not filter to employment cases"),
) -> None:
    """Import a downloaded CAP reporter volume directory. Heavy path."""
    from stare.db import init_db, session_scope
    from stare.ingest.cap import import_cap_bulk
    from stare.ingest.pipeline import load_courts

    init_db()
    with session_scope() as s:
        load_courts(s)
    _echo(f"{import_cap_bulk(path, limit=limit or None, employment_only=not all_cases)} opinions imported")


@ingest_app.command("courtlistener-bulk")
def ingest_courtlistener_bulk(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, help="Directory of CourtListener bulk CSVs"),
    limit: int = typer.Option(0, help="Stop after N opinions (0 = no limit)"),
    court: list[str] = typer.Option([], "--court", help="Restrict to these court ids (repeatable)"),
    all_cases: bool = typer.Option(False, "--all", help="Do not filter to employment cases"),
) -> None:
    """Stream-import CourtListener bulk CSVs (employment cases in federal courts). Heavy path."""
    from stare.db import init_db, session_scope
    from stare.ingest.courtlistener_bulk import import_courtlistener_bulk
    from stare.ingest.pipeline import load_courts

    init_db()
    with session_scope() as s:
        load_courts(s)
        counts = import_courtlistener_bulk(directory, session=s, courts=set(court) or None, limit=limit or None,
                                           employment_only=not all_cases, say=_echo)
    _echo(str(counts))


@ingest_app.command("all")
def ingest_all(offline: bool = typer.Option(False, help="Build only from cached raw files (no network)")) -> None:
    """courts + seed corpus + statutes + chunks."""
    from stare.db import init_db, session_scope
    from stare.ingest.pipeline import build_corpus

    init_db()
    with session_scope() as s:
        counts = build_corpus(s, offline_only=offline, say=_echo)
    for k, v in counts.items():
        _echo(f"{k:>18}: {v}")


@ingest_app.command("refresh")
def ingest_refresh(
    bulk_dir: Path = typer.Option(None, exists=True, file_okay=False, help="Newer CourtListener bulk CSV directory"),
    offline: bool = typer.Option(False, help="Use cached raw files only (no network)"),
    index: bool = typer.Option(True, help="Rebuild the retrieval index afterwards"),
) -> None:
    """Monthly refresh of the corpus, then the index. Schedule with cron, for example:
    0 3 1 * * cd /path/to/capstone/backend && .venv/bin/stare ingest refresh"""
    from stare.config import get_settings
    from stare.db import init_db, session_scope
    from stare.ingest.pipeline import refresh_corpus
    from stare.retrieval.hybrid import HybridRetriever

    init_db()
    with session_scope() as s:
        counts = refresh_corpus(s, bulk_dir=bulk_dir, online=not offline, say=_echo)
    for k, v in counts.items():
        _echo(f"{k:>18}: {v}")
    if index:
        with session_scope() as s:
            stats = HybridRetriever.build_index(s, get_settings())
        _echo(f"index rebuilt: {stats['chunks']} chunks")


# ---- index, eval, server ----------------------------------------------------------------------

from stare.retrieval.cli import index_app  # noqa: E402

app.add_typer(index_app(), name="index")


@db_app.command("purge")
def db_purge(days: int = typer.Option(0, help="Retention in days (0 = the administrator's setting)")) -> None:
    """Delete matters whose last activity is older than the retention period (the audit log is kept)."""
    from stare.db import init_db, session_scope
    from stare.retention import purge_expired

    init_db()
    with session_scope() as s:
        _echo(str(purge_expired(s, days or None)))


@db_app.command("create-user")
def db_create_user(
    email: str = typer.Argument(...),
    name: str = typer.Option(..., prompt=True),
    role: str = typer.Option("attorney", help="attorney | paralegal | admin"),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
) -> None:
    """Create a user (use this to bootstrap the first administrator)."""
    from stare.api.auth import create_user
    from stare.db import init_db, session_scope

    if role not in ("attorney", "paralegal", "admin"):
        raise typer.Exit(code=_fail("role must be attorney, paralegal or admin"))
    init_db()
    with session_scope() as s:
        create_user(s, name, email, password, role)
    _echo(f"created {role} {email}")


@eval_app.command("run")
def eval_run(limit: int = typer.Option(0, help="Only the first N gold questions (0 = all)")) -> None:
    """Gold set + Mata fixture + export check + redaction coverage + latency -> docs/evaluation/results.md."""
    from stare.eval.runner import evaluate, write_report

    result = evaluate(limit=limit or None, say=_echo)
    path = write_report(result)
    for k, v in result["summary"].items():
        if k not in ("targets", "questions"):
            _echo(f"{k:>28}: {v}")
    _echo(f"report written to {path}")


@eval_app.command("mata")
def eval_mata() -> None:
    """Run only the Mata v. Avianca fixture through the Citation Firewall."""
    from stare.agents.base import AgentDeps
    from stare.db import get_sessionmaker
    from stare.eval.runner import mata_test
    from stare.llm import get_llm

    result = mata_test(AgentDeps(llm=get_llm(), session_factory=get_sessionmaker()))
    for cite, status in result["statuses"].items():
        _echo(f"  {status:>10}  {cite}")
    _echo(f"{'PASS' if result['passed'] else 'FAIL'}: {result['fabricated'] - result['exportable']} of "
          f"{result['fabricated']} fabricated citations stopped")
    raise typer.Exit(code=0 if result["passed"] else 1)


@eval_app.command("baseline")
def eval_baseline(
    limit: int = typer.Option(10, help="Number of gold questions"),
    answers: Path = typer.Option(None, exists=True, help="JSONL of {id, answer} produced by any general-purpose LLM"),
    provider: str = typer.Option("external", help="Label for the model that produced --answers"),
) -> None:
    """General-purpose LLM baseline (Table 29): score an LLM's unretrieved answers with the Citation Firewall.
    With --answers no model is called; without it STARE_LLM_PROVIDER is used (costs API credits)."""
    import json

    from stare.eval.baseline import run_baseline, score_answers

    if answers:
        rows = [json.loads(line) for line in answers.read_text().splitlines() if line.strip()]
        result = score_answers(rows, provider=provider)
    else:
        result = run_baseline(limit=limit)
    out = Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "baseline.json"
    out.write_text(json.dumps(result, indent=2))
    _echo(json.dumps({k: v for k, v in result.items() if k not in ("rows", "questions")} | {"questions": len(result.get("rows") or result.get("questions") or [])}, indent=2))
    _echo(f"written to {out}")


@app.command("demo")
def demo(sample: Path = typer.Argument(Path(__file__).resolve().parents[2] / "data" / "samples" / "complaint_ndtex_title7_retaliation.pdf")) -> None:
    """Run one complaint end to end in the terminal (auto-approving both gates) and save the DOCX."""
    from stare.api.auth import create_user
    from stare.db import get_sessionmaker, init_db
    from stare.db.models import CaseFile, Document, User
    from stare.graph.service import ResearchService
    from stare.intake.pdf_reader import extract_document
    from stare.intake.redactor import PIIRedactor
    from stare.schemas import ResearchPlan

    init_db()
    sf = get_sessionmaker()
    doc = extract_document(sample.read_bytes(), sample.name)
    red = PIIRedactor().redact(doc.text)
    with sf() as s:
        user = s.query(User).filter_by(email="demo-attorney@stare.local").first() or create_user(
            s, "Demo Attorney", "demo-attorney@stare.local", "stare-demo", "attorney")
        n = s.query(CaseFile).count() + 1
        case = CaseFile(matter_number=f"M-D{n:03d}", title=f"Demo: {sample.stem}", user_id=user.id)
        s.add(case)
        s.flush()
        s.add(Document(case_id=case.id, file_name=sample.name, page_count=doc.page_count, ocr_used=doc.ocr_used,
                       redacted_text=red.text, redaction_entities=[e.model_dump() for e in red.entities],
                       redaction_engine=red.engine))
        s.commit()
        user_id, case_id = user.id, case.id
    _echo(f"{sample.name}: {doc.page_count} pages, OCR={doc.ocr_used}, {len(red.entities)} personal details redacted")
    svc = ResearchService(sf, synchronous=True)
    run_id = svc.start_run(case_id, user_id)
    snap = svc.snapshot(run_id)
    _echo(f"plan: {[i['issue'] for i in snap['plan']['items']]}")
    svc.approve_plan(run_id, ResearchPlan.model_validate(snap["plan"]), user_id)
    snap = svc.snapshot(run_id)
    for st in snap["steps"]:
        if st["status"] in ("done", "error"):
            _echo(f"  {st['agent']:>18} {st['duration_ms'] or 0:>6} ms  {st['summary']}")
    if snap["status"] != "awaiting_memo_approval":
        raise typer.Exit(code=_fail(f"run ended as {snap['status']}: {snap['error']}"))
    svc.approve_memo(run_id, None, user_id)
    out = Path(f"STARE-demo-run{run_id}.docx")
    out.write_bytes(svc.export_docx(run_id, user_id))
    _echo(f"memo approved and exported to {out.resolve()} (latency {snap['latency_ms']} ms)")


@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the API server (the React app proxies /api to it)."""
    import uvicorn

    uvicorn.run("stare.api.main:app", host=host, port=port, reload=reload)


def _fail(msg: str) -> int:
    typer.echo(msg, err=True)
    return 1


if __name__ == "__main__":
    app()
