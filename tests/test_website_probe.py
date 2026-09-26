import socket

import pytest

from lib.response_cache import ResponseCache
from lib.website_probe import probe_url, extract_evidence


@pytest.fixture(autouse=True)
def zero_rate_limit(monkeypatch):
    monkeypatch.setattr("lib.http_utils.DEFAULT_RATE_LIMIT_DELAY", 0)


def resolver_for(*good_hosts):
    def _resolve(host, port):
        if host in good_hosts:
            return [("fake",)]
        raise socket.gaierror("nxdomain")
    return _resolve


HTML = """<html><head><title>Meath Arts Centre</title>
<meta name="description" content="Arts venue in Trim">
<meta property="og:site_name" content="MAC"></head>
<body><script>var x=1;</script><h1>Welcome</h1><p>Programme</p>
<footer>Meath Arts Centre DAC, CRO 123456</footer></body></html>"""


def test_nxdomain_without_fetch(requests_mock):
    r = probe_url("https://invented.ie/", resolver=resolver_for())
    assert r["outcome"] == "nxdomain" and r["evidence"] is None
    assert requests_mock.call_count == 0


def test_www_fallback_when_bare_host_missing(requests_mock):
    requests_mock.get("https://www.x.ie/", text=HTML, headers={"Content-Type": "text/html"})
    r = probe_url("https://x.ie/", resolver=resolver_for("www.x.ie"))
    assert r["outcome"] == "ok"
    assert r["final_url"] == "https://www.x.ie/"


def test_ok_extracts_evidence(requests_mock):
    requests_mock.get("https://mac.ie/", text=HTML, headers={"Content-Type": "text/html"})
    r = probe_url("https://mac.ie/", resolver=resolver_for("mac.ie"))
    assert r["outcome"] == "ok" and r["status_code"] == 200
    ev = r["evidence"]
    assert ev["title"] == "Meath Arts Centre"
    assert ev["meta_description"] == "Arts venue in Trim"
    assert ev["site_name"] == "MAC"
    assert ev["h1"] == "Welcome"
    assert "CRO 123456" in ev["footer_text"]
    assert "var x" not in ev["text_head"]


def test_waf_challenge_is_blocked(requests_mock):
    requests_mock.get("https://w.ie/", status_code=403, text="<html>Just a moment...</html>",
                      headers={"Content-Type": "text/html"})
    assert probe_url("https://w.ie/", resolver=resolver_for("w.ie"))["outcome"] == "blocked"


def test_plain_403_is_blocked(requests_mock):
    requests_mock.get("https://b.ie/", status_code=403, text="<html>no</html>",
                      headers={"Content-Type": "text/html"})
    assert probe_url("https://b.ie/", resolver=resolver_for("b.ie"))["outcome"] == "blocked"


def test_404_is_dead(requests_mock):
    requests_mock.get("https://d.ie/", status_code=404, text="gone")
    r = probe_url("https://d.ie/", resolver=resolver_for("d.ie"))
    assert r["outcome"] == "dead" and r["status_code"] == 404


def test_connection_error_is_dead(requests_mock):
    import requests
    requests_mock.get("https://c.ie/", exc=requests.exceptions.ConnectionError("refused"))
    assert probe_url("https://c.ie/", resolver=resolver_for("c.ie"))["outcome"] == "dead"


def test_parked_domain(requests_mock):
    requests_mock.get("https://p.ie/", text="<html><h1>This domain is for sale</h1></html>",
                      headers={"Content-Type": "text/html"})
    assert probe_url("https://p.ie/", resolver=resolver_for("p.ie"))["outcome"] == "parked"


def test_gov_ie_stub_is_followed(requests_mock):
    stub = ('<html><body><p>There is a separate website for this organisation.</p>'
            '<a href="https://real.ie/">real.ie</a></body></html>')
    requests_mock.get("https://www.gov.ie/en/organisation/x/", text=stub,
                      headers={"Content-Type": "text/html"})
    requests_mock.get("https://real.ie/", text=HTML, headers={"Content-Type": "text/html"})
    r = probe_url("https://www.gov.ie/en/organisation/x/", resolver=resolver_for("www.gov.ie", "real.ie"))
    assert r["outcome"] == "ok" and r["final_url"] == "https://real.ie/"
    assert r["url"] == "https://www.gov.ie/en/organisation/x/"


def test_cache_hit_skips_network(tmp_path, requests_mock):
    requests_mock.get("https://mac.ie/", text=HTML, headers={"Content-Type": "text/html"})
    cache = ResponseCache(tmp_path)
    probe_url("https://mac.ie/", resolver=resolver_for("mac.ie"), cache=cache)
    probe_url("https://mac.ie/", resolver=resolver_for("mac.ie"), cache=cache)
    assert requests_mock.call_count == 1


def test_extract_evidence_empty_html():
    ev = extract_evidence("")
    assert ev == {"title": "", "meta_description": "", "site_name": "", "h1": "",
                  "text_head": "", "footer_text": ""}
