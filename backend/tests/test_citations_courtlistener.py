import os

import httpx
import pytest
from test_citations_support import mock_client

from stare.citations.courtlistener import CourtListenerClient, TokenBucket


def test_disabled_returns_none_everywhere(settings):
    c = CourtListenerClient(settings)  # conftest disables the API
    assert c.enabled is False
    assert c.lookup_citation("925", "F.3d", "1339") is None
    assert c.fetch_opinion_text(1) is None
    assert c.citing_opinions(1) is None


def test_anonymous_search_found_and_not_found(settings):
    c = mock_client(settings, found={"925 F.3d 1339": "Someone v. Else"})
    res = c.lookup_citation("925", "F. 3d", "1339")
    assert res and res[0]["case_name"] == "Someone v. Else" and res[0]["cluster_id"] == 77
    assert res[0]["url"].startswith("https://www.courtlistener.com/")
    assert c.lookup_citation("1", "F.3d", "2") == []
    assert all(r.url.path.endswith("/search/") for r in c.calls)


def test_search_requires_exact_cite_match(settings):
    def handler(req):
        return httpx.Response(200, json={"results": [{"cluster_id": 5, "caseName": "Fuzzy", "citation": ["925 F.3d 1340"]}]})
    c = mock_client(settings, handler)
    assert c.lookup_citation("925", "F.3d", "1339") == []


def test_token_uses_citation_lookup_post(settings):
    c = mock_client(settings, token="abc", found={"570 U.S. 338": "Nassar"})
    res = c.lookup_citation("570", "U.S.", "338")
    assert res[0]["case_name"] == "Nassar"
    assert c.calls[0].method == "POST" and c.calls[0].headers["authorization"] == "Token abc"
    assert c.lookup_citation("1", "U.S.", "1") == []  # 404 status entries -> not found


def test_disk_cache_avoids_second_request(settings):
    c = mock_client(settings, found={"925 F.3d 1339": "X v. Y"})
    c.lookup_citation("925", "F.3d", "1339")
    n = len(c.calls)
    again = c.lookup_citation("925", "F.3d", "1339")
    assert again and len(c.calls) == n and c.last_from_cache
    assert list((settings.cache_dir / "courtlistener").glob("*.json"))


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500),
    lambda r: httpx.Response(429),
    lambda r: httpx.Response(401),
    lambda r: httpx.Response(200, content=b"<html>not json"),
    lambda r: httpx.Response(200, json={"unexpected": True}),
])
def test_http_errors_mean_unavailable_not_exception(settings, handler):
    c = mock_client(settings, handler)
    assert c.lookup_citation("925", "F.3d", "1339") is None
    assert c.citing_opinions(1) is None


def test_timeout_is_unavailable(settings):
    def boom(req):
        raise httpx.ConnectTimeout("slow")
    c = mock_client(settings, boom)
    assert c.lookup_citation("925", "F.3d", "1339") is None
    assert c.fetch_opinion_text(3) is None


def test_failures_are_not_cached(settings):
    state = {"ok": False}
    def h(req):
        return httpx.Response(200, json={"results": []}) if state["ok"] else httpx.Response(503)
    c = mock_client(settings, h)
    assert c.lookup_citation("1", "F.3d", "1") is None
    state["ok"] = True
    assert c.lookup_citation("1", "F.3d", "1") == []


def test_fetch_opinion_text_and_citing(settings):
    def h(req):
        p = req.url.path
        if p.endswith("/clusters/9/"):
            return httpx.Response(200, json={"sub_opinions": ["https://cl.test/api/rest/v4/opinions/4/"]})
        if p.endswith("/opinions/4/"):
            return httpx.Response(200, json={"plain_text": "", "html_with_citations": "<p>Hello <b>world</b></p>"})
        if p.endswith("/search/"):
            assert req.url.params["q"] == "cites:(9)"
            return httpx.Response(200, json={"results": [{"cluster_id": 2, "caseName": "Later v. Case", "dateFiled": "2020-01-01",
                                                          "opinions": [{"snippet": "overruled by statute"}], "absolute_url": "/o/2/"}]})
        return httpx.Response(404)
    c = mock_client(settings, h)
    assert c.fetch_opinion_text(9) == "Hello world"
    rows = c.citing_opinions(9)
    assert rows[0]["case_name"] == "Later v. Case" and "overruled" in rows[0]["snippet"]


def test_token_bucket_limits_rate():
    now = [0.0]
    slept = []
    b = TokenBucket(2, clock=lambda: now[0], sleep=lambda s: (slept.append(s), now.__setitem__(0, now[0] + s)))
    assert b.acquire() and b.acquire()
    assert b.acquire(max_wait=40)  # waits for a refill (30 s per token)
    assert slept and abs(slept[0] - 30) < 1
    assert not b.acquire(max_wait=1)


def test_rate_limited_client_is_unavailable(settings):
    settings.courtlistener_rate_per_minute = 1
    c = mock_client(settings, lambda r: httpx.Response(200, json={"results": []}))
    c.bucket.sleep = lambda s: None
    assert c.lookup_citation("1", "F.3d", "1") == []
    assert c.lookup_citation("2", "F.3d", "2") is None  # would have to wait 60 s
    assert c.quota_left == 0


@pytest.mark.network
def test_live_lookup_smoke(settings):  # optional: needs internet; run with -m network
    if not os.environ.get("STARE_NETWORK_TESTS"):
        pytest.skip("set STARE_NETWORK_TESTS=1 to hit the live API")
    settings.courtlistener_enabled = True
    c = CourtListenerClient(settings)
    res = c.lookup_citation("570", "U.S.", "338")
    assert res is None or isinstance(res, list)


def test_circuit_breaker_stops_calling_a_failing_api(settings, monkeypatch):
    import httpx

    from stare.citations.courtlistener import CourtListenerClient

    monkeypatch.setattr(settings, "courtlistener_enabled", True)
    calls = []

    def handler(request):
        calls.append(request.url)
        raise httpx.ConnectTimeout("slow")

    now = [1000.0]
    client = CourtListenerClient(settings, transport=httpx.MockTransport(handler), clock=lambda: now[0], sleep=lambda s: None)
    for page in ("1", "2", "3", "4", "5"):
        assert client.lookup_citation("925", "F.3d", page) is None
    assert len(calls) == 3  # backed off after three consecutive failures
    now[0] += 301
    client.lookup_citation("925", "F.3d", "9")
    assert len(calls) == 4
