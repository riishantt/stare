"""Statutes and regulations: Title VII, ADA Title I, ADEA (U.S. Code) and 29 C.F.R. parts 1601, 1625, 1630.

U.S. Code sections come from law.cornell.edu (uscode.house.gov as fallback); C.F.R. parts from the eCFR API.
Downloads are cached under `data/statutes/raw/` so a fresh clone builds offline.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from sqlalchemy import select
from sqlalchemy.orm import Session

from stare.config import REPO_DIR
from stare.db.models import StatuteSection

RAW_DIR = REPO_DIR / "data" / "statutes" / "raw"
ECFR_DATE = "2026-10-01"
USER_AGENT = "STARE-capstone/0.1 (academic research; free public data)"

# (title, section) lists; sections absent from the Code are skipped when the source returns 404.
TITLE_VII = [("42", "2000e")] + [("42", f"2000e-{i}") for i in range(1, 18)] + [
    ("42", "2000e-16a"), ("42", "2000e-16b"), ("42", "2000e-16c"),
    ("42", "1981"),  # equal rights under the law (race claims often pleaded with Title VII)
    ("42", "1981a"),  # damages in cases of intentional discrimination: Title VII / ADA caps
]
ADA = [("42", str(n)) for n in range(12101, 12118)] + [("42", "12203")]  # + Title V anti-retaliation
ADEA = [("29", str(n)) for n in range(621, 635)] + [("29", "633a")]
USC_SECTIONS = [(t, s, "title_vii") for t, s in TITLE_VII] + [(t, s, "ada") for t, s in ADA] + [
    (t, s, "adea") for t, s in ADEA
]
CFR_PARTS = [("29", "1601", "title_vii"), ("29", "1614", "title_vii"), ("29", "1625", "adea"), ("29", "1630", "ada")]


@dataclass
class ParsedSection:
    code: str  # USC | CFR
    title: int
    section: str
    heading: str
    text: str
    statute: str
    url: str

    @property
    def citation(self) -> str:
        if self.code == "USC":
            return f"{self.title} U.S.C. § {self.section}"
        if self.section.endswith("app"):
            return f"{self.title} C.F.R. pt. {self.section.split()[0]}, app."
        return f"{self.title} C.F.R. § {self.section}"


def _clean(s: str) -> str:
    s = re.sub(r"[ \t\r\f\v\xa0]+", " ", s)
    s = re.sub(r" ?\n ?", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


# ---- U.S. Code (LII html) ------------------------------------------------------------------------

_LEVELS = {"subsection", "paragraph", "subparagraph", "clause", "subclause", "item", "subitem"}


def trim_lii_html(html: str) -> str:
    """Keep only the heading and statute text from a law.cornell.edu section page (small cache file)."""
    soup = BeautifulSoup(html, "lxml")
    h1, tab = soup.select_one("h1"), soup.select_one("#tab_default_1")
    if not h1 or not tab:
        raise ValueError("not a LII section page")
    return f"<h1>{h1.get_text(' ', strip=True)}</h1>\n{tab}"


def parse_usc_html(html: str) -> tuple[str, str]:
    """-> (heading, text) for one U.S. Code section: one paragraph per subdivision, label on its own line."""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1").get_text(" ", strip=True)
    m = re.match(r"\d+ U\.S\. Code § ?[\w\-]+ ?[-–—]? ?(.*)", h1)
    heading = (m.group(1) if m else h1).strip()
    tab = soup.select_one("#tab_default_1")
    for d in tab.select(",".join(f"div.{c}" for c in sorted(_LEVELS))):
        d.insert(0, NavigableString("\x00"))
        num = d.find("span", class_="num", recursive=False)
        if num:
            num.append(NavigableString(" "))
        head = d.find("span", class_="heading", recursive=False)
        if head:
            head.append(NavigableString("\n"))
    for el in tab.select("p, .chapeau, .continuation, .content"):
        el.insert(0, NavigableString("\n"))
    raw = tab.get_text("")
    paras = []
    for block in raw.split("\x00"):
        lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in block.split("\n")]
        lines = [ln for ln in lines if ln]
        merged: list[str] = []
        for ln in lines:
            if merged and re.fullmatch(r"(?:\([A-Za-z0-9]+\) ?)+", merged[-1]):
                merged[-1] = f"{merged[-1].strip()} {ln}"
            else:
                merged.append(ln)
        if merged:
            paras.append("\n".join(merged))
    text = "\n\n".join(paras)
    text = re.sub(r" ([,.;:)])", r"\1", text).replace("( ", "(")
    return heading, _clean(text)


def usc_url(title: str, section: str) -> str:
    return f"https://www.law.cornell.edu/uscode/text/{title}/{section}"


def fetch_usc_section(title: str, section: str) -> str | None:
    r = httpx.get(usc_url(title, section), timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    return trim_lii_html(r.text) if r.status_code == 200 else None


# ---- eCFR ---------------------------------------------------------------------------------------


def ecfr_url(title: str, part: str, date: str = ECFR_DATE) -> str:
    return f"https://www.ecfr.gov/api/versioner/v1/full/{date}/title-{title}.xml?part={part}"


def fetch_ecfr_part(title: str, part: str) -> str | None:
    r = httpx.get(ecfr_url(title, part), timeout=120, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    return r.text if r.status_code == 200 else None


def _ecfr_text(node: Tag) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            continue
        if child.name in ("HEAD", "CITA", "AUTH", "SOURCE", "GPOTABLE", "GPH", "SECAUTH", "EDNOTE"):
            continue
        if child.name in ("EXTRACT", "NOTE", "FLUSH", "DIV9", "DIV8") or child.find(["P", "FP"]):
            sub = _ecfr_text(child)
            if sub:
                parts.append(sub)
        else:
            t = re.sub(r"\s+", " ", child.get_text(" ")).strip()
            t = re.sub(r" ([,.;:)])", r"\1", t)
            if t:
                parts.append(t)
    return "\n\n".join(parts)


def parse_ecfr_xml(xml: str, *, title: int, part: str, statute: str) -> list[ParsedSection]:
    soup = BeautifulSoup(xml, "xml")
    out: list[ParsedSection] = []
    url = f"https://www.ecfr.gov/current/title-{title}/part-{part}"
    for div in soup.find_all(["DIV8", "DIV9"]):
        head = re.sub(r"\s+", " ", (div.find("HEAD").get_text(" ") if div.find("HEAD") else "")).strip()
        text = _clean(_ecfr_text(div))
        if not text or re.search(r"\[Reserved\]|\[Removed", head):
            continue
        if div.name == "DIV8":
            m = re.match(r"§\s*([\d.]+)\s*(.*)", head)
            if not m:
                continue
            sec, heading = m.group(1).rstrip("."), m.group(2).strip().rstrip(".")
            out.append(ParsedSection("CFR", title, sec, heading, text, statute, f"{url}/section-{sec}"))
        elif div.get("TYPE") == "APPENDIX" and div.get("N", "").lower().startswith("appendix"):
            out.append(ParsedSection("CFR", title, f"{part} app", head.rstrip("."), text, statute, url))
    return out


# ---- pipeline -----------------------------------------------------------------------------------


def fetch_statutes(raw_dir: Path | None = None, *, say: Callable[[str], None] = lambda s: None,
                   refetch: bool = False) -> dict[str, int]:
    """Download missing statute/regulation sources into the raw cache. Returns counts of fetched/missing."""
    raw_dir = raw_dir or RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)
    got = missing = 0
    for title, section, _ in USC_SECTIONS:
        f = raw_dir / f"usc-{title}-{section}.html"
        if f.exists() and not refetch:
            continue
        marker = raw_dir / f"usc-{title}-{section}.absent"
        if marker.exists() and not refetch:
            continue
        html = fetch_usc_section(title, section)
        time.sleep(0.5)
        if html is None:
            marker.write_text("")
            missing += 1
            say(f"absent {title} U.S.C. {section}")
        else:
            f.write_text(html)
            got += 1
            say(f"ok     {title} U.S.C. {section}")
    for title, part, _ in CFR_PARTS:
        f = raw_dir / f"cfr-{title}-{part}.xml"
        if f.exists() and not refetch:
            continue
        xml = fetch_ecfr_part(title, part)
        if xml is None:
            missing += 1
            say(f"MISS {title} C.F.R. {part}")
        else:
            f.write_text(xml)
            got += 1
            say(f"ok   {title} C.F.R. part {part}")
    return {"fetched": got, "missing": missing}


def load_cached_sections(raw_dir: Path | None = None) -> list[ParsedSection]:
    raw_dir = raw_dir or RAW_DIR
    sections: list[ParsedSection] = []
    for title, section, statute in USC_SECTIONS:
        f = raw_dir / f"usc-{title}-{section}.html"
        if not f.exists():
            continue
        heading, text = parse_usc_html(f.read_text())
        if text and not re.match(r"(repealed|omitted|transferred)", heading, re.IGNORECASE):
            sections.append(ParsedSection("USC", int(title), section, heading, text, statute, usc_url(title, section)))
    for title, part, statute in CFR_PARTS:
        f = raw_dir / f"cfr-{title}-{part}.xml"
        if f.exists():
            sections.extend(parse_ecfr_xml(f.read_text(), title=int(title), part=part, statute=statute))
    return sections


def import_statutes(session: Session, *, offline: bool = True, raw_dir: Path | None = None,
                    say: Callable[[str], None] = lambda s: None) -> int:
    """Insert or update StatuteSection rows from the raw cache (fetching missing files first when online)."""
    if not offline:
        fetch_statutes(raw_dir, say=say)
    n = 0
    for sec in load_cached_sections(raw_dir):
        row = session.scalar(select(StatuteSection).where(StatuteSection.citation == sec.citation))
        if row is None:
            row = StatuteSection(citation=sec.citation)
            session.add(row)
        row.code, row.title, row.section = sec.code, sec.title, sec.section
        row.heading, row.statute, row.text, row.url = sec.heading[:500], sec.statute, sec.text, sec.url
        row.source = "uscode" if sec.code == "USC" else "ecfr"
        n += 1
    session.commit()
    return n
