"""Local citation index: (volume, reporter, page) -> opinion, statute lookup, opinion text."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.citations.reporters import reporter_key
from stare.db.models import Citation, Opinion, StatuteSection
from stare.schemas import ExtractedCitation

_SUBSECTION = re.compile(r"(\([A-Za-z0-9]{1,4}\))+$")


def strip_subsection(section: str) -> str:
    """'2000e-3(a)(1)' -> '2000e-3'; '1630.2(o)' -> '1630.2'."""
    return _SUBSECTION.sub("", (section or "").strip()).replace("–", "-").replace("—", "-")


class CitationIndex:
    def __init__(self, session: Session):
        self.session = session

    def lookup(self, volume: str, reporter: str, page: str) -> list[Opinion]:
        """Opinions whose citation list contains volume/reporter/page. The reporter is compared in
        normalised form, so 'F. 3d' in the draft finds 'F.3d' in the index."""
        want = reporter_key(reporter)
        rows = self.session.scalars(
            select(Citation).where(Citation.volume == str(volume).strip(), Citation.page == str(page).strip())
        ).all()
        ids: list[int] = []
        for c in rows:
            if reporter_key(c.reporter) == want and c.opinion_id not in ids:
                ids.append(c.opinion_id)
        if not ids:
            return []
        found = {o.id: o for o in self.session.scalars(select(Opinion).where(Opinion.id.in_(ids)))}
        return [found[i] for i in ids if i in found]

    def lookup_statute(self, cite: ExtractedCitation) -> StatuteSection | None:
        if cite.kind not in ("statute", "regulation", "id", "short_form") or not cite.reporter:
            return None
        code = "CFR" if cite.reporter.replace(".", "").upper() == "CFR" else "USC"
        if cite.reporter.replace(".", "").upper() not in ("CFR", "USC", "USCA"):
            return None
        try:
            title = int(cite.volume or "")
        except ValueError:
            return None
        section = strip_subsection(cite.page or "")
        rows = self.session.scalars(
            select(StatuteSection).where(StatuteSection.code == code, StatuteSection.title == title)
        ).all()
        norm = lambda x: x.replace("–", "-").replace("—", "-").lower()
        for r in rows:
            if norm(strip_subsection(r.section)) == norm(section):
                return r
        return None

    def opinion_text(self, opinion_id: int) -> str:
        return self.session.scalar(select(Opinion.plain_text).where(Opinion.id == opinion_id)) or ""
