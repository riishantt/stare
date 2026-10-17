"""Caselaw Access Project static files as a free Gate 2 source (no account, no rate limit).

static.case.law publishes, for every volume of the official and regional reporters, a CasesMetadata.json
listing each case and the page it begins on. That answers "is there a case that begins at volume/
reporter/page, and what is it called?" exactly, for every published case up to CAP's coverage end. The
volume listing and case files are cached on disk, so each is downloaded at most once.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

CAP_BASE = "https://static.case.law"
# normalised reporter -> CAP slug (coverage ends: U.S. 2014, S. Ct. 2020, F.3d 2019, F. Supp. 3d 2019, F. App'x 2018)
SLUGS = {
    "U.S.": "us", "S. Ct.": "s-ct", "L. Ed. 2d": "l-ed-2d", "F.": "f", "F.2d": "f2d", "F.3d": "f3d",
    "F. Supp.": "f-supp", "F. Supp. 2d": "f-supp-2d", "F. Supp. 3d": "f-supp-3d", "F. App'x": "f-appx",
}


class CAPStaticClient:
    def __init__(self, settings, *, transport: httpx.BaseTransport | None = None, timeout: float = 8.0):
        self.enabled = bool(getattr(settings, "cap_lookup_enabled", True))
        self.cache = Path(settings.cache_dir) / "cap"
        self._transport = transport
        self._timeout = timeout
        self._http: httpx.Client | None = None

    def _get_json(self, url: str):
        f = self.cache / (hashlib.sha256(url.encode()).hexdigest()[:40] + ".json")
        if f.exists():
            try:
                return json.loads(f.read_text())
            except ValueError:
                pass
        if self._http is None:
            self._http = httpx.Client(transport=self._transport, timeout=self._timeout,
                                      headers={"User-Agent": "stare-capstone/0.1"})
        try:
            r = self._http.get(url)
        except Exception as e:  # timeouts, DNS, connection errors: unavailable, never raise into the firewall
            log.warning("CAP static request failed: %s", e)
            return None
        if r.status_code == 404:
            data = {"__missing__": True}
        elif r.status_code >= 400:
            return None
        else:
            try:
                data = r.json()
            except ValueError:
                return None
        self.cache.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))
        return data

    def covers(self, reporter: str | None) -> bool:
        return self.enabled and (reporter or "") in SLUGS

    def lookup(self, volume: str, reporter: str, page: str) -> list[dict] | None:
        """Cases that begin at the cited page. [] = CAP has the volume and no case begins there;
        None = not covered (reporter, volume or network unavailable)."""
        if not self.covers(reporter) or not volume.isdigit() or not page.isdigit():
            return None
        slug = SLUGS[reporter]
        meta = self._get_json(f"{CAP_BASE}/{slug}/{volume}/CasesMetadata.json")
        if not isinstance(meta, list):
            return None
        return [
            {
                "case_name": m.get("name_abbreviation") or m.get("name") or "",
                "date_filed": m.get("decision_date"),
                "path": f"{slug}/{volume}/cases/{m.get('file_name')}.json",
                "url": f"{CAP_BASE}/{slug}/{volume}/cases/{m.get('file_name')}.json",
            }
            for m in meta
            if str(m.get("first_page", "")).lstrip("0") == page.lstrip("0")
        ]

    def opinion_text(self, path: str) -> str | None:
        """Opinion text with separate opinions marked, as stored for the local corpus."""
        from stare.ingest.cap import case_text

        case = self._get_json(f"{CAP_BASE}/{path}")
        if not isinstance(case, dict) or case.get("__missing__") or "casebody" not in case:
            return None
        return case_text(case)
