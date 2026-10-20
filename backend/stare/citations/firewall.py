"""Citation Firewall: every citation is unverified until it passes the gates (CONTRACTS section 4)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from stare.citations.cap_static import CAPStaticClient
from stare.citations.courtlistener import CourtListenerClient
from stare.citations.gates import (
    OpinionRef,
    gate_exists,
    gate_extract,
    gate_quote_match,
    good_law_findings,
    is_law,
    not_checked,
)
from stare.citations.index import CitationIndex
from stare.citations.parser import extract_citations, sentence_starts
from stare.citations.quote import QUOTE_SEP
from stare.config import Settings, get_settings
from stare.schemas import Authority, CitationCheck, ExtractedCitation, GateResult

_REMOVED = ("blocked", "unresolved")


def _skip(n: int, name: str, why: str) -> GateResult:
    return GateResult(gate=n, name=name, outcome="skip", detail=why)  # type: ignore[arg-type]


class CitationFirewall:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        settings: Settings | None = None,
        client: CourtListenerClient | None = None,
    ):
        self.session_factory = session_factory
        self.settings = settings or get_settings()
        self.client = client if client is not None else CourtListenerClient(self.settings)
        self.cap = CAPStaticClient(self.settings)

    # -- single citation -----------------------------------------------------------------------
    def verify_citation(self, cite: ExtractedCitation) -> CitationCheck:
        check = CitationCheck(citation=cite)
        g1 = gate_extract(cite)
        check.gates.append(g1)
        if g1.outcome == "fail":
            check.status, check.reason = "unresolved", g1.detail
            check.gates += [_skip(2, "exists", "not run"), _skip(3, "quote_match", "not run"), _skip(4, "good_law", "not run")]
            return check

        with self.session_factory() as session:
            index = CitationIndex(session)
            g2, ref = gate_exists(cite, index, self.client, self.settings, self.cap)
            check.gates.append(g2)
            if g2.outcome in ("fail", "unresolved"):
                check.status = "blocked" if g2.outcome == "fail" else "unresolved"
                check.reason = g2.detail
                check.gates += [_skip(3, "quote_match", "not run"), _skip(4, "good_law", "not run")]
                return check
            assert ref is not None
            check.opinion_id, check.matched_case_name, check.source, check.url = (
                ref.opinion_id, ref.case_name, ref.source, ref.url,
            )

            # Gate 3
            text = ""
            if (cite.quote or "").strip() or cite.later_quote.strip():
                text = self._text(ref, index, is_law(cite))
            g3 = gate_quote_match(cite.quote, text, self.settings)
            if cite.later_quote.strip():
                g3, check.unsupported_quote_spans = self._later_quotes(cite, text, g3)
            check.gates.append(g3)

            # Gate 4 (cases only)
            if is_law(cite):
                g4 = _skip(4, "good_law", "statutes are checked against the current code, not for case treatment")
            elif g3.outcome == "fail":
                g4 = _skip(4, "good_law", "not run")
            elif ref.opinion_id is None and ref.cluster_id is None:
                # e.g. a CAP match: no curated treatment list or citation network covers it, so not verified
                g4 = not_checked("the opinion is not in the local citation network; check later treatment before relying on it")
            else:
                findings, scanned, checked = good_law_findings(ref.opinion_id, session, self.client, ref.cluster_id)
                check.treatment = findings
                if findings:
                    g4 = GateResult(gate=4, name="good_law", outcome="warn", detail="; ".join(findings))
                elif not checked:
                    g4 = not_checked("CourtListener's cited-by search is unavailable; check later treatment before relying on it")
                else:
                    g4 = GateResult(gate=4, name="good_law", outcome="pass", detail=f"no negative treatment found ({scanned} citing opinions scanned)")
            check.gates.append(g4)

        check.status, check.reason = self._status([g2, g3, g4], cite)
        return check

    def _text(self, ref: OpinionRef, index: CitationIndex, law: bool) -> str:
        if law and ref.section_id is not None:
            from stare.db.models import StatuteSection

            sec = index.session.get(StatuteSection, ref.section_id)
            return sec.text if sec else ""
        if ref.opinion_id is not None:
            return index.opinion_text(ref.opinion_id)
        if ref.cap_path:
            return self.cap.opinion_text(ref.cap_path) or ""
        if ref.cluster_id is not None and self.client is not None:
            return self.client.fetch_opinion_text(ref.cluster_id) or ""
        return ""

    def _later_quotes(self, cite: ExtractedCitation, text: str, g3: GateResult) -> tuple[GateResult, list[tuple[int, int]]]:
        """Quotations in a later sentence belong to this citation only by position, so one the opinion does not
        contain is removed from the text (its spans are returned) and the citation is warned, not blocked."""
        parts = cite.later_quote.split(QUOTE_SEP)
        results = [gate_quote_match(q, text, self.settings) for q in parts]
        bad = [span for span, r in zip(cite.later_quote_spans, results, strict=False) if r.outcome != "pass"]
        if g3.outcome == "fail":
            return g3, bad
        if bad:
            detail = (f"{len(bad)} quotation(s) in a following sentence, linked to this citation by position, are not in "
                      "this opinion and were removed; check which authority they come from")
            return GateResult(gate=3, name="quote_match", outcome="warn", detail=detail), bad
        if g3.outcome == "skip":
            return results[0], []
        return g3, []

    @staticmethod
    def _status(gates: list[GateResult], cite: ExtractedCitation) -> tuple[str, str]:
        g2, g3, g4 = gates
        if g3.outcome == "fail":
            return "blocked", g3.detail
        if g3.outcome == "unresolved":
            return "unresolved", g3.detail
        # Gate 4 unresolved = later treatment not checked: exportable for the attorney to review, never "verified"
        warns = [g for g in (g2, g3, g4) if g.outcome == "warn" or (g is g4 and g.outcome == "unresolved")]
        if warns:
            return "warning", " | ".join(f"{g.name}: {g.detail}" for g in warns)
        parts = [g2.detail] + ([g3.detail] if g3.outcome == "pass" else []) + ["no negative treatment found"] * (g4.outcome == "pass")
        return "verified", "; ".join(parts)

    # -- text and authorities --------------------------------------------------------------------
    def verify_text(self, text: str) -> list[CitationCheck]:
        return [self.verify_citation(c) for c in extract_citations(text)]

    def verify_authority(self, a: Authority) -> CitationCheck:
        parsed = [c for c in extract_citations(a.citation) if c.kind in ("case", "statute", "regulation")]
        if parsed:
            cite = parsed[0].model_copy()
        else:
            cite = ExtractedCitation(raw=a.citation, cite=a.citation, kind=a.kind)
        if a.case_name:
            cite.case_name = a.case_name
        if a.year and not cite.year:
            cite.year = a.year
        if a.court_name and not cite.court_hint:
            cite.court_hint = a.court_name
        cite.quote = a.quote or ""
        cite.raw = a.citation
        return self.verify_citation(cite)

    def filter_text(self, text: str, checks: list[CitationCheck]) -> tuple[str, list[str]]:
        """Remove every sentence that contains a blocked or unresolved citation, or a quotation attached to one
        (a quotation may sit in the sentence after its citation, and must not stay behind unchecked)."""
        bad = [c for c in checks if c.status in _REMOVED and c.citation.span[1] <= len(text)]
        quotes = [c for c in checks if c.status not in _REMOVED and c.unsupported_quote_spans]
        if not bad and not quotes:
            return text, []
        # a full stop inside a quotation does not end the sentence; the one just before the closing mark does
        protected = [c.citation.span for c in checks] + [(qs, qe - 2) for c in checks for qs, qe in c.citation.quote_spans]
        starts = sentence_starts(text, protected) + [len(text)]
        drop: set[int] = set()
        for c in bad:
            for pos in [c.citation.span[0]] + [qs for qs, _ in c.citation.quote_spans if qs < len(text)]:
                drop.add(max(i for i, s in enumerate(starts[:-1]) if s <= pos))
        for c in quotes:  # only the unsupported quotation's sentence goes; the citation's own sentence stays
            for qs, _ in c.unsupported_quote_spans:
                if qs < len(text):
                    drop.add(max(i for i, s in enumerate(starts[:-1]) if s <= qs))
        out, last = [], 0
        for k in sorted(drop):
            s, e = starts[k], starts[k + 1]
            tail = re.search(r"\s*\n\s*$", text[s:e])
            if tail and "\n" in tail.group(0):
                e = s + tail.start()  # keep the paragraph break
            out.append(text[last:s])
            last = e
        out.append(text[last:])
        clean = "".join(out)
        clean = re.sub(r"[ \t]+(\n|$)", r"\1", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        removed = list(dict.fromkeys([c.citation.raw for c in bad] + [f"a quotation attributed to {c.citation.raw}" for c in quotes]))
        return clean.strip() if not text.endswith("\n") else clean.strip() + "\n", removed


@dataclass
class FirewallReport:
    checks: list[CitationCheck] = field(default_factory=list)

    @classmethod
    def from_checks(cls, checks: list[CitationCheck]) -> FirewallReport:
        return cls(list(checks))

    @property
    def counts(self) -> dict[str, int]:
        c = Counter(ch.status for ch in self.checks)
        return {k: c.get(k, 0) for k in ("verified", "warning", "blocked", "unresolved")}

    @property
    def total(self) -> int:
        return len(self.checks)

    @property
    def exportable(self) -> bool:
        return all(c.exportable for c in self.checks)

    def summary(self) -> str:
        c = self.counts
        parts = [f"{c['verified']} verified"]
        for k in ("warning", "blocked", "unresolved"):
            if c[k]:
                parts.append(f"{c[k]} {k}")
        return f"{self.total} checked: " + ", ".join(parts)

    def removed(self) -> list[tuple[str, str]]:
        """(citation, reason) for every blocked or unresolved citation."""
        return [(c.citation.raw, c.reason) for c in self.checks if c.status in _REMOVED]

    def warnings(self) -> list[tuple[str, str]]:
        return [(c.citation.raw, c.reason) for c in self.checks if c.status == "warning"]
