"""
JobCopilot - Company logos.

The server looks a company's logo up once and keeps it, so the browser only ever talks
to JobCopilot (no third party learns which jobs someone is looking at). A logo is only
used when the lookup returns a company with the same name; anything less certain falls
back to the coloured initial in the app, because a wrong logo is worse than none.
"""

import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Dict, Optional

import httpx

from app.core.config import DATA_DIR
from app.core.settings import settings
from app.discovery.companies import known_website

SUGGEST_URL = "https://autocomplete.clearbit.com/v1/companies/suggest"
ICON_URL = "https://www.google.com/s2/favicons"
TIMEOUT_SECONDS = 4.0
MAX_BYTES = 200_000
MISS_RETRY_SECONDS = 7 * 86_400
MAX_NAME_LENGTH = 80

_DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
_locks: Dict[str, asyncio.Lock] = {}


def normalise(name: str) -> str:
    """'InMobi (Corporate)' and 'inmobi' are the same company."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)", "", name.lower()))


def _cache_dir() -> Path:
    path = DATA_DIR / "company_logos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _paths(key: str):
    stem = hashlib.sha256(key.encode()).hexdigest()[:24]
    return _cache_dir() / f"{stem}.img", _cache_dir() / f"{stem}.miss"


_LEGAL_SUFFIX = re.compile(r"(privatelimited|pvtltd|limited|ltd|inc|llc|corp|corporation)$")


def pick_domain(name: str, suggestions: list) -> Optional[str]:
    """The first suggestion that is clearly this company, or nothing.

    Several companies can share a name, so the name alone isn't enough: the web address
    must spell it too ("Swiggy" and swiggy.com, "Sarvam AI" and sarvam.ai). A legal ending
    such as "Limited" is ignored.
    """
    key = normalise(name)
    names = {key, _LEGAL_SUFFIX.sub("", key) or key}
    for s in suggestions if isinstance(suggestions, list) else []:
        if not isinstance(s, dict):
            continue
        domain = str(s.get("domain") or "").strip().lower()
        if not _DOMAIN.match(domain):
            continue
        same_name = normalise(str(s.get("name") or "")) in names
        if normalise(domain) == key or (same_name and normalise(domain.split(".")[0]) in names):
            return domain
    return None


async def find_domain(client: httpx.AsyncClient, name: str) -> Optional[str]:
    """The company's website address: from our own list when we know it, else looked up."""
    known = known_website(name) or known_website(re.sub(r"\([^)]*\)", "", name))
    if known:
        return known
    found = await client.get(SUGGEST_URL, params={"query": re.sub(r"\([^)]*\)", "", name).strip()})
    return pick_domain(name, found.json()) if found.status_code == 200 else None


# Job sites whose postings carry the employer's logo; only these hosts are ever fetched.
POSTING_LOGO_PREFIXES = ("https://media.instahyre.com/",)


def _source_path(key: str) -> Path:
    return _cache_dir() / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.src"


def remember_posting_logo(name: str, url: str) -> None:
    """Keeps the logo address a job site published with this company's posting."""
    key = normalise(name or "")
    if not key or not str(url or "").startswith(POSTING_LOGO_PREFIXES) or len(url) > 500:
        return
    source = _source_path(key)
    if not source.exists():
        source.write_text(url)
        # We may have answered "no logo" before this posting turned up.
        _paths(key)[1].unlink(missing_ok=True)


def _image(res: httpx.Response) -> Optional[bytes]:
    data = res.content if res.status_code == 200 else b""
    return data if 0 < len(data) <= MAX_BYTES and media_type(data) else None


async def _fetch(name: str) -> Optional[bytes]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
        # A company we don't list ourselves: the logo from its own posting beats a name search.
        source = _source_path(normalise(name))
        if not known_website(name) and source.exists():
            url = source.read_text().strip()
            if url.startswith(POSTING_LOGO_PREFIXES):
                posted = _image(await client.get(url, follow_redirects=False))
                if posted:
                    return posted
        domain = await find_domain(client, name)
        if not domain:
            return None
        icon = await client.get(ICON_URL, params={"domain": domain, "sz": "128"})
        # An unknown site comes back as a 404 carrying a placeholder globe.
        if icon.status_code != 200 or not icon.headers.get("content-type", "").startswith("image/"):
            return None
        data = icon.content
        return data if 0 < len(data) <= MAX_BYTES and media_type(data) else None


async def get_logo(name: str) -> Optional[bytes]:
    """The company's logo image, or None when there isn't a trustworthy one."""
    key = normalise(name or "")
    if not key or len(name) > MAX_NAME_LENGTH or not settings.COMPANY_LOGOS_ENABLED:
        return None
    image, miss = _paths(key)
    if image.exists():
        return image.read_bytes()
    if miss.exists() and time.time() - miss.stat().st_mtime < MISS_RETRY_SECONDS:
        return None

    async with _locks.setdefault(key, asyncio.Lock()):
        if image.exists():
            return image.read_bytes()
        try:
            data = await _fetch(name)
        except (httpx.HTTPError, ValueError):
            # The lookup service is down or slow: say "none" now and try again next time.
            return None
        finally:
            _locks.pop(key, None)
        if data:
            image.write_bytes(data)
            miss.unlink(missing_ok=True)
        else:
            miss.touch()
        return data


def media_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"\x00\x00\x01\x00":
        return "image/x-icon"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return ""
