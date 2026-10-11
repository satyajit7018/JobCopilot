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
    assert info == {"about": "Rialtic helps healthcare payers improve & automate payment accuracy with one platform.", "website": "https://rialtic.io", "source": "website"}
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
    assert asyncio.run(company_info.get_info("Rialtic")) == {"about": None, "website": "https://rialtic.io", "source": None}

    monkeypatch.undo()
    assert company_info._is_public_host("localhost") is False and company_info._is_public_host("10.0.0.5") is False


def test_note_from_a_posting_is_kept_and_unknown_companies_are_empty(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    _fake_web(monkeypatch, handler)
    company_info.remember("ZOOP", "ZOOP builds identity verification APIs for banks and fintech companies.")
    company_info.remember("ZOOP", "A later, different note that should not replace the first one at all.")
    assert asyncio.run(company_info.get_info("Zoop")) == {"about": "ZOOP builds identity verification APIs for banks and fintech companies.", "website": None, "source": "posting"}
    assert asyncio.run(company_info.get_info("Nobody Heard Of")) == {"about": None, "website": None, "source": None}
    assert asyncio.run(company_info.get_info("")) == {"about": None, "website": None, "source": None}


def test_endpoint_needs_sign_in_and_survives_an_outage(auth_client: TestClient, client: TestClient, monkeypatch):
    async def down(name, want_about):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(company_info, "_lookup", down)
    res = auth_client.get("/api/company-info", params={"name": "Rialtic"})
    assert res.status_code == 200 and res.json() == {"about": None, "website": None, "source": None}
    assert client.get("/api/company-info", params={"name": "Rialtic"}).status_code in (401, 403)


STRIPE = ("Note: interns please use another link. Who we are About Stripe Stripe is a financial infrastructure platform for businesses. "
          "Millions of companies use Stripe to accept payments. About the team The Payments team builds things. You will write code.")
SUPABASE = "ABOUT SUPABASE\n\nSupabase is the Postgres development platform, built by developers for developers. We provide a complete backend solution including Database, Auth and Storage.\n\n\nABOUT THE ROLE\n\nWe are hiring an engineer."


def test_about_us_is_lifted_from_a_posting_word_for_word():
    about = company_info.about_from_posting
    assert about("Stripe", STRIPE) == "Stripe is a financial infrastructure platform for businesses. Millions of companies use Stripe to accept payments."
    assert about("Supabase", SUPABASE) == "Supabase is the Postgres development platform, built by developers for developers. We provide a complete backend solution including Database, Auth and Storage."
    assert about("Tide", "A BOUT TIDE At Tide, we help SMEs save time and money in the running of their businesses. The role: you will build.").startswith("At Tide, we help SMEs")
    assert about("FamPay", "About Fam (previously FamPay)\n\nFam is India's first payments app for everyone above 11. FamApp helps make online and offline payments.").startswith("Fam is India")
    assert about("Notion", "About Us: Notion is the collaborative AI workspace where teams think together https://youtu.be/x. We build one place for work.") == "Notion is the collaborative AI workspace where teams think together. We build one place for work."


def test_role_text_is_never_passed_off_as_about_the_company():
    about = company_info.about_from_posting
    assert about("Perplexity", "Perplexity is seeking a DevOps engineer to join our small team. You will be responsible for infrastructure.") is None
    assert about("MongoDB", "MongoDB Professional Services (PS) works with customers of all shapes and sizes on exciting use cases.") is None
    assert about("Mindtickle", "Software Engineer, Business Systems. Location: Pune. Build and run the integrations that connect Mindtickle's systems.") is None
    assert about("Acme", "") is None and about("", STRIPE) is None


def test_posting_fills_in_only_when_the_website_gave_nothing(auth_client: TestClient, monkeypatch):
    import uuid
    from app.core.database import db
    from app.core.models import ApplicationStatus, JobListing

    async def nothing(name, want_about):
        return {"website": None, "about": None}

    monkeypatch.setattr(company_info, "_lookup", nothing)
    user_id = auth_client.get("/api/auth/me").json()["user_id"]
    company = f"Quillfield{uuid.uuid4().hex[:6]}"
    job = JobListing(
        job_id=f"job_{uuid.uuid4().hex[:12]}", user_id=user_id, fingerprint=uuid.uuid4().hex, platform="Y Combinator",
        company=company, title="Engineer", location="Remote", url="https://example.test/j",
        description=f"About us: {company} is a small team building accounting tools for bakeries across India. The role: you will write code.",
        match_score=0.7, status=ApplicationStatus.DISCOVERED,
    )
    assert db.save_job(job, user_id=user_id)
    assert auth_client.get("/api/company-info", params={"name": company}).json()["about"] is None
    # A job id for a different company is ignored.
    assert auth_client.get("/api/company-info", params={"name": "Someone Else Entirely", "job_id": job.job_id}).json()["about"] is None
    res = auth_client.get("/api/company-info", params={"name": company, "job_id": job.job_id}).json()
    assert res == {"about": f"{company} is a small team building accounting tools for bakeries across India.", "website": None, "source": "posting"}
