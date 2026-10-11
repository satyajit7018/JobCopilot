"""Company "about" and website: the company's own words, the right company, looked up once."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import company_info, company_logo
from app.discovery.companies import CAREER_PAGES, known_website

PAGE = """<html><head><title>Rialtic</title>
<meta property="og:description" content="Short og.">
<meta name='description' content='Rialtic helps healthcare payers improve &amp; automate payment accuracy with one platform.'>
</head><body>hi</body></html>"""


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "DATA_DIR", tmp_path)
    monkeypatch.setattr(company_info, "_is_public_host", lambda host: True)


def test_about_is_read_from_the_page_and_tidied():
    assert company_info.about_from_page(PAGE) == "Rialtic helps healthcare payers improve & automate payment accuracy with one platform."
    assert company_info.about_from_page("<html><meta name='description' content='Too short'></html>") is None
    long = company_info.clean_about("word " * 300)
    assert len(long) <= company_info.MAX_ABOUT_CHARS + 1 and long.endswith("…")
    assert company_info.clean_about("<b>Hello</b>   there, this is a   perfectly reasonable company summary.") == "Hello there, this is a perfectly reasonable company summary."


def test_listed_companies_use_their_own_website_not_a_namesake():
    assert known_website("Tide") == "tide.co" and known_website("sarvam ai") == "sarvam.ai" and known_website("Nobody") == ""
    assert all(page.website and "." in page.website for page in CAREER_PAGES)
    # Unlisted companies: the same name is not enough, the address must spell it too.
    assert company_logo.pick_domain("Perplexity", [{"name": "Perplexity", "domain": "perplexity1.com"}]) is None
    assert company_logo.pick_domain("Rialtic", [{"name": "Rialtic", "domain": "rialtic.io"}]) == "rialtic.io"
    assert company_logo.pick_domain("Piramal Finance Limited", [{"name": "Piramal Finance", "domain": "piramalfinance.com"}]) == "piramalfinance.com"
    assert company_logo.pick_domain("Sarvam AI", [{"name": "Sarvam", "domain": "sarvam.ai"}]) == "sarvam.ai"


def _fake_web(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(company_info.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))


def test_lookup_follows_the_companys_own_redirect_and_is_kept(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.host == "autocomplete.clearbit.com":
            return httpx.Response(200, json=[{"name": "Rialtic", "domain": "rialtic.io"}])
        if request.url.host == "rialtic.io":
            return httpx.Response(301, headers={"location": "https://www.rialtic.io/"})
        return httpx.Response(200, text=PAGE, headers={"content-type": "text/html; charset=utf-8"})

    _fake_web(monkeypatch, handler)
    info = asyncio.run(company_info.get_info("Rialtic"))
    assert info == {"about": "Rialtic helps healthcare payers improve & automate payment accuracy with one platform.", "website": "https://rialtic.io"}
    before = len(calls)
    assert asyncio.run(company_info.get_info("rialtic")) == info and len(calls) == before


def test_redirect_off_the_companys_site_is_not_followed_and_internal_hosts_are_never_read(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "autocomplete.clearbit.com":
            return httpx.Response(200, json=[{"name": "Rialtic", "domain": "rialtic.io"}])
        if request.url.host == "rialtic.io":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/"})
        raise AssertionError(f"should not fetch {request.url}")

    _fake_web(monkeypatch, handler)
    assert asyncio.run(company_info.get_info("Rialtic")) == {"about": None, "website": "https://rialtic.io"}

    monkeypatch.undo()
    assert company_info._is_public_host("localhost") is False and company_info._is_public_host("10.0.0.5") is False


def test_note_from_a_posting_is_kept_and_unknown_companies_are_empty(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    _fake_web(monkeypatch, handler)
    company_info.remember("ZOOP", "ZOOP builds identity verification APIs for banks and fintech companies.")
    company_info.remember("ZOOP", "A later, different note that should not replace the first one at all.")
    assert asyncio.run(company_info.get_info("Zoop")) == {"about": "ZOOP builds identity verification APIs for banks and fintech companies.", "website": None}
    assert asyncio.run(company_info.get_info("Nobody Heard Of")) == {"about": None, "website": None}
    assert asyncio.run(company_info.get_info("")) == {"about": None, "website": None}


def test_endpoint_needs_sign_in_and_survives_an_outage(auth_client: TestClient, client: TestClient, monkeypatch):
    async def down(name, want_about):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(company_info, "_lookup", down)
    res = auth_client.get("/api/company-info", params={"name": "Rialtic"})
    assert res.status_code == 200 and res.json() == {"about": None, "website": None}
    assert client.get("/api/company-info", params={"name": "Rialtic"}).status_code in (401, 403)
