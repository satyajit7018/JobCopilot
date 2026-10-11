"""Company logos: only shown when the lookup is sure, kept on the server, and never fetched twice."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core import company_logo

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@pytest.fixture(autouse=True)
def _own_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(company_logo, "DATA_DIR", tmp_path)


def test_only_a_company_with_the_same_name_is_trusted():
    hits = [
        {"name": "Swiggy Wala", "domain": "swiggywala.com"},
        {"name": "Swiggy", "domain": "not a domain"},
        {"name": "Swiggy", "domain": "swiggy.com"},
    ]
    assert company_logo.pick_domain("Swiggy", hits) == "swiggy.com"
    assert company_logo.pick_domain("InMobi (Corporate)", [{"name": "Inmobi", "domain": "inmobi.com"}]) == "inmobi.com"
    assert company_logo.pick_domain("Harbor Analytics", [{"name": "Harbor", "domain": "harbor.com"}]) is None
    assert company_logo.pick_domain("Swiggy", {"error": "nope"}) is None


def test_logo_is_served_then_reused_without_another_lookup(client: TestClient, monkeypatch):
    calls = []

    async def fake(name):
        calls.append(name)
        return PNG

    monkeypatch.setattr(company_logo, "_fetch", fake)
    first = client.get("/api/company-logo", params={"name": "Swiggy"})
    assert first.status_code == 200 and first.content == PNG
    assert first.headers["content-type"] == "image/png" and "max-age" in first.headers["cache-control"]
    assert client.get("/api/company-logo", params={"name": "swiggy"}).content == PNG
    assert calls == ["Swiggy"]


def test_unknown_company_is_an_empty_answer_and_is_remembered(client: TestClient, monkeypatch):
    calls = []

    async def fake(name):
        calls.append(name)
        return None

    monkeypatch.setattr(company_logo, "_fetch", fake)
    for _ in range(2):
        res = client.get("/api/company-logo", params={"name": "Harbor Analytics"})
        assert res.status_code == 204 and res.content == b""
    assert calls == ["Harbor Analytics"]


def test_a_failed_lookup_is_retried_and_bad_names_never_look_anything_up(client: TestClient, monkeypatch):
    calls = []

    async def down(name):
        calls.append(name)
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(company_logo, "_fetch", down)
    assert client.get("/api/company-logo", params={"name": "Zepto"}).status_code == 204
    assert client.get("/api/company-logo", params={"name": "Zepto"}).status_code == 204
    assert calls == ["Zepto", "Zepto"]
    for bad in ("", "!!!", "x" * 81):
        assert client.get("/api/company-logo", params={"name": bad}).status_code == 204
    assert len(calls) == 2


def test_lookup_takes_the_matching_company_and_rejects_placeholders(monkeypatch):
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "autocomplete.clearbit.com":
            return httpx.Response(200, json=[{"name": "Groww", "domain": "groww.in"}])
        if request.url.params["domain"] == "groww.in":
            return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
        return httpx.Response(404, content=PNG, headers={"content-type": "image/png"})

    real = httpx.AsyncClient
    monkeypatch.setattr(company_logo.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    assert asyncio.run(company_logo._fetch("Groww")) == PNG
    assert asyncio.run(company_logo._fetch("Someone Else")) is None


def test_switch_off_and_image_types(monkeypatch):
    import asyncio

    monkeypatch.setattr(company_logo.settings, "COMPANY_LOGOS_ENABLED", False)
    assert asyncio.run(company_logo.get_logo("Swiggy")) is None
    assert company_logo.media_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert company_logo.media_type(b"<svg") == ""
