"""CourtListener client (Gate 2 fallback, Gate 4 cited-by). Free API, rate limited, disk cached.

Every method returns None when the API is unavailable (disabled, rate-limited, offline, HTTP error,
bad JSON). It never raises into the firewall (NFR-06). An empty list means the API answered "not found".
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from stare.citations.reporters import normalize_reporter, reporter_key

log = logging.getLogger(__name__)

_TAGS = re.compile(r"<[^>]+>")


class TokenBucket:
    def __init__(self, rate_per_minute: int, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.capacity = float(max(rate_per_minute, 1))
        self.rate = self.capacity / 60.0
        self.tokens = self.capacity
        self.clock, self.sleep = clock, sleep
        self.last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now

    def acquire(self, max_wait: float = 5.0) -> bool:
        """Take one token, waiting up to max_wait seconds. False when the wait would be longer."""
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            wait = (1 - self.tokens) / self.rate
            if wait > max_wait:
                return False
            self.sleep(wait)
            self._refill()
            self.tokens = max(self.tokens - 1, 0.0)
            return True

    @property
    def left(self) -> int:
        with self._lock:
            self._refill()
            return int(self.tokens)


class CourtListenerClient:
    def __init__(self, settings, *, transport: httpx.BaseTransport | None = None, timeout: float = 8.0,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.settings = settings
        self.enabled: bool = bool(settings.courtlistener_enabled)
        self.base = settings.courtlistener_base_url.rstrip("/")
        self.token: str = settings.courtlistener_token or ""
        self.cache_path = Path(settings.cache_dir) / "courtlistener"
        self.bucket = TokenBucket(settings.courtlistener_rate_per_minute, clock=clock, sleep=sleep)
        self.last_from_cache = False
        self.last_authoritative = True
        self._transport = transport
        self._timeout = timeout
        self._http: httpx.Client | None = None
        self._clock = clock
        self._failures = 0
        self._down_until = 0.0

    @property
    def quota_left(self) -> int:
        return self.bucket.left

    # -- plumbing -----------------------------------------------------------------------------
    def _client(self) -> httpx.Client:
        if self._http is None:
            headers = {"User-Agent": "stare-capstone/0.1"}
            if self.token:
                headers["Authorization"] = f"Token {self.token}"
            self._http = httpx.Client(transport=self._transport, timeout=self._timeout, headers=headers)
        return self._http

    def _cache_file(self, kind: str, payload: Any) -> Path:
        h = hashlib.sha256(json.dumps([kind, payload], sort_keys=True, default=str).encode()).hexdigest()[:40]
        return self.cache_path / f"{h}.json"

    def _cached(self, f: Path) -> Any | None:
        try:
            if f.exists():
                return json.loads(f.read_text())["data"]
        except Exception:  # corrupt cache entry: ignore
            return None
        return None

    def _store(self, f: Path, data: Any) -> None:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({"data": data}))
        except OSError:
            pass

    def _request(self, method: str, url: str, **kw) -> Any | None:
        """JSON body or None (unavailable). Never raises. After three consecutive failures the client
        backs off for five minutes so a slow or unreachable API can never stall a research run (NFR-06)."""
        if self._clock() < self._down_until:
            return None
        body = self._do_request(method, url, **kw)
        if body is None:
            self._failures += 1
            if self._failures >= 3:
                log.warning("CourtListener unavailable; using the local index only for the next 5 minutes")
                self._down_until = self._clock() + 300
                self._failures = 0
        else:
            self._failures = 0
        return body

    def _do_request(self, method: str, url: str, **kw) -> Any | None:
        if not self.bucket.acquire(max_wait=getattr(self.settings, "courtlistener_max_wait_s", 5.0)):
            log.warning("CourtListener rate limit reached; treating as unavailable")
            return None
        try:
            r = self._client().request(method, url, **kw)
        except Exception as e:  # timeouts, DNS, connection errors
            log.warning("CourtListener request failed: %s", e)
            return None
        if r.status_code >= 400:
            log.warning("CourtListener HTTP %s for %s", r.status_code, url)
            return None
        try:
            return r.json()
        except Exception:
            return None

    # -- Gate 2 ---------------------------------------------------------------------------------
    def lookup_citation(self, volume: str, reporter: str, page: str) -> list[dict] | None:
        """Clusters at volume/reporter/page: [{cluster_id, case_name, citation, date_filed, court, url}].
        None = API unavailable; [] = the API answered and found nothing."""
        self.last_from_cache = False
        if not self.enabled:
            return None
        cite = f"{volume} {normalize_reporter(reporter)} {page}"
        # Only the token-authenticated citation-lookup API is authoritative about non-existence; the anonymous
        # search index can miss real (especially recent) opinions.
        self.last_authoritative = bool(self.token)
        f = self._cache_file("lookup", [volume, reporter_key(reporter), page, bool(self.token)])
        hit = self._cached(f)
        if hit is not None:
            self.last_from_cache = True
            return hit
        if self.token:
            data = self._request("POST", f"{self.base}/citation-lookup/", data={"text": cite})
            out = self._parse_lookup(data, volume, reporter, page) if data is not None else None
        else:
            data = self._request(
                "GET", f"{self.base}/search/", params={"type": "o", "q": f'citation:("{cite}")', "page_size": 10}
            )
            out = self._parse_search(data, volume, reporter, page) if data is not None else None
        if out is not None:
            self._store(f, out)
        return out

    @staticmethod
    def _matches(cites: list[str], volume: str, reporter: str, page: str) -> bool:
        want = (str(volume), reporter_key(reporter), str(page))
        for c in cites:
            m = re.match(r"\s*(\d+)\s+(.+?)\s+(\d[\w\-*]*)\s*$", c or "")
            if m and (m.group(1), reporter_key(m.group(2)), m.group(3)) == want:
                return True
        return False

    def _parse_lookup(self, data: Any, volume, reporter, page) -> list[dict] | None:
        if not isinstance(data, list):
            return None
        out: list[dict] = []
        for item in data:
            if not isinstance(item, dict) or item.get("status") == 404:
                continue
            for cl in item.get("clusters") or []:
                cites = [self._cite_str(c) for c in cl.get("citations") or []]
                out.append(
                    {
                        "cluster_id": cl.get("id"),
                        "case_name": cl.get("case_name") or cl.get("caseName") or "",
                        "citation": [c for c in cites if c],
                        "date_filed": cl.get("date_filed"),
                        "court": cl.get("court") or "",
                        "url": self._abs(cl.get("absolute_url")),
                    }
                )
        return out

    @staticmethod
    def _cite_str(c: Any) -> str:
        if isinstance(c, str):
            return c
        if isinstance(c, dict):
            return f"{c.get('volume', '')} {c.get('reporter', '')} {c.get('page', '')}".strip()
        return ""

    @staticmethod
    def _abs(u: str | None) -> str | None:
        if not u:
            return None
        return u if u.startswith("http") else f"https://www.courtlistener.com{u}"

    def _parse_search(self, data: Any, volume, reporter, page) -> list[dict] | None:
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        out = []
        for r in data["results"]:
            cites = [c for c in (r.get("citation") or []) if isinstance(c, str)]
            if not self._matches(cites, volume, reporter, page):  # the search is fuzzy; require the exact cite
                continue
            out.append(
                {
                    "cluster_id": r.get("cluster_id") or r.get("id"),
                    "case_name": r.get("caseName") or r.get("case_name") or "",
                    "citation": cites,
                    "date_filed": r.get("dateFiled"),
                    "court": r.get("court_id") or r.get("court") or "",
                    "url": self._abs(r.get("absolute_url")),
                }
            )
        return out

    # -- text -------------------------------------------------------------------------------------
    def fetch_opinion_text(self, cluster_id: int) -> str | None:
        if not self.enabled:
            return None
        f = self._cache_file("text", cluster_id)
        hit = self._cached(f)
        if hit is not None:
            return hit or None
        cl = self._request("GET", f"{self.base}/clusters/{cluster_id}/")
        if not isinstance(cl, dict):
            return None
        parts: list[str] = []
        for sub in cl.get("sub_opinions") or []:
            url = sub if isinstance(sub, str) else (sub or {}).get("resource_uri", "")
            if not url:
                continue
            op = self._request("GET", url if url.startswith("http") else f"{self.base}{url}")
            if not isinstance(op, dict):
                return None
            txt = op.get("plain_text") or ""
            if not txt:
                html = op.get("html_with_citations") or op.get("html") or op.get("html_lawbox") or ""
                txt = re.sub(r"\s+", " ", _TAGS.sub(" ", html)).strip()
            if txt:
                parts.append(txt)
        text = "\n\n".join(parts)
        if not text:
            return None
        self._store(f, text)
        return text

    # -- Gate 4 -----------------------------------------------------------------------------------
    def citing_opinions(self, cluster_id: int, limit: int = 50) -> list[dict] | None:
        if not self.enabled:
            return None
        f = self._cache_file("cites", [cluster_id, limit])
        hit = self._cached(f)
        if hit is not None:
            return hit
        data = self._request(
            "GET", f"{self.base}/search/",
            params={"type": "o", "q": f"cites:({cluster_id})", "page_size": min(limit, 100)},
        )
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return None
        out = [
            {
                "cluster_id": r.get("cluster_id") or r.get("id"),
                "case_name": r.get("caseName") or "",
                "date_filed": r.get("dateFiled"),
                "snippet": " ".join((o.get("snippet") or "") for o in (r.get("opinions") or [])),
                "url": self._abs(r.get("absolute_url")),
            }
            for r in data["results"][:limit]
        ]
        self._store(f, out)
        return out
