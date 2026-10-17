"""Document upload: extract -> redact -> store ONLY redacted text (NFR-03)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from stare.api.auth import CurrentUser, require_roles
from stare.api.deps import get_db, get_settings_dep
from stare.api.routers import misc
from stare.api.routers.matters import document_out
from stare.api.schemas_api import DocumentOut, DocumentPatch
from stare.config import Settings
from stare.db.models import CaseFile, Document
from stare.graph.service import audit

router = APIRouter(tags=["documents"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_WRITERS = ("attorney", "paralegal")


@router.post("/matters/{matter_id}/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    matter_id: int,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(require_roles(*_WRITERS)),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
):
    if db.get(CaseFile, matter_id) is None:
        raise LookupError(f"matter {matter_id} not found")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than the 20 MB limit")
    name = Path(file.filename or "upload").name[:300]

    from stare.intake.pdf_reader import extract_document

    try:
        extracted = extract_document(data, name)
    except ValueError as exc:  # DocumentReadError
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="The file could not be read as a PDF, DOCX or TXT document") from exc

    redaction = misc.get_redactor().redact(extracted.text)
    if settings.keep_raw_uploads:  # off by default: raw client files are never written to disk
        dest = settings.upload_dir / str(matter_id)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / f"{uuid.uuid4().hex}{Path(name).suffix.lower()}").write_bytes(data)
    del data

    doc = Document(
        case_id=matter_id, file_name=name, page_count=extracted.page_count or len(extracted.pages),
        ocr_used=extracted.ocr_used, redacted_text=redaction.text,
        redaction_entities=[e.model_dump() for e in redaction.entities], redaction_engine=redaction.engine,
    )
    db.add(doc)
    db.flush()
    audit(db, user.id, "document.uploaded", "document", doc.id, matter_id=matter_id, pages=doc.page_count,
          ocr_used=doc.ocr_used, redactions=len(redaction.entities), chars=len(redaction.text),
          engine=redaction.engine)
    db.commit()
    return document_out(doc)


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def edit_document(document_id: int, body: DocumentPatch, user: CurrentUser = Depends(require_roles(*_WRITERS)),
                  db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise LookupError(f"document {document_id} not found")
    # a hand-corrected text may reintroduce identifiers, so it passes through the redactor again
    known = {e.get("placeholder", ""): e.get("entity_type", "") for e in doc.redaction_entities or []}
    redaction = misc.get_redactor().redact_edited(body.redacted_text, known)
    before = len(doc.redacted_text)
    old_entities = len(doc.redaction_entities or [])
    doc.redacted_text = redaction.text
    doc.redaction_entities = [e.model_dump() for e in redaction.entities]
    doc.redaction_engine = redaction.engine
    doc.reviewed_by = user.id
    doc.reviewed_at = datetime.now(UTC)
    audit(db, user.id, "document.redaction_edited", "document", doc.id, matter_id=doc.case_id, chars_before=before,
          chars_after=len(doc.redacted_text), redactions_before=old_entities, redactions_after=len(redaction.entities))
    db.commit()
    return document_out(doc)
