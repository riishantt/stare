from datetime import UTC, datetime, timedelta

from stare.db.models import AuditLog, CaseFile, Document, ResearchRun, User
from stare.retention import purge_expired


def test_purge_removes_only_expired_matters_and_keeps_audit(session):
    now = datetime(2026, 10, 17, tzinfo=UTC)
    u = User(name="A", email="a@x", password_hash="x", role="attorney")
    session.add(u)
    session.flush()
    old = CaseFile(matter_number="M-1", title="old", user_id=u.id, created_at=now - timedelta(days=400))
    recent_run = CaseFile(matter_number="M-2", title="old matter, recent run", user_id=u.id,
                          created_at=now - timedelta(days=400))
    new = CaseFile(matter_number="M-3", title="new", user_id=u.id, created_at=now - timedelta(days=5))
    session.add_all([old, recent_run, new])
    session.flush()
    session.add(Document(case_id=old.id, file_name="a.pdf", redacted_text="x"))
    session.add(ResearchRun(case_id=old.id, created_by=u.id, thread_id="t-old", created_at=now - timedelta(days=399)))
    session.add(ResearchRun(case_id=recent_run.id, created_by=u.id, thread_id="t-recent", created_at=now - timedelta(days=10)))
    session.commit()

    result = purge_expired(session, 365, now=now, user_id=u.id)
    assert result["matters"] == 1 and result["runs"] == 1
    assert {c.matter_number for c in session.query(CaseFile).all()} == {"M-2", "M-3"}
    assert session.query(Document).count() == 0
    assert session.query(AuditLog).filter_by(action="retention.purged").one().detail["matter_numbers"] == ["M-1"]
