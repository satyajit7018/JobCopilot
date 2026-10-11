"""
JobCopilot - A short "about" and website link for a company.

Nothing here is written by us. The text is the company's own: either the summary on its
home page, or the note the job site published with the posting. The website is only given
when the lookup returns a company with exactly this name (same rule as logos). Each company
is looked up once and kept, so the browser never contacts another site for it.
"""

import asyncio
import hashlib
import html
import ipaddress
import json
import re
import socket
import time
from typing import Any, Dict, Optional

import httpx

from app.core import company_logo
from app.core.settings import settings

TIMEOUT_SECONDS = 5.0
MAX_PAGE_BYTES = 300_000
MAX_ABOUT_CHARS = 420
MIN_ABOUT_CHARS = 40
RETRY_SECONDS = 7 * 86_400
HEADERS = {"User-Agent": "JobCopilot/1.0 (job search assistant)", "Accept": "text/html"}

_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z:-]+)\s*=\s*("([^"]*)"|'([^']*)')""")
_locks: Dict[str, asyncio.Lock] = {}


def _path(key: str):
    return company_logo._cache_dir() / f"{hashlib.sha256(key.encode()).hexdigest()[:24]}.info.json"


def _load(key: str) -> Dict[str, Any]:
    try:
        data = json.loads(_path(key).read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(key: str, record: Dict[str, Any]) -> None:
    _path(key).write_text(json.dumps(record))


def clean_about(text: str) -> Optional[str]:
    """Plain text of a sensible length, or None when it's too thin to be worth showing."""
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(text or ""))).strip()
    if len(plain) < MIN_ABOUT_CHARS:
        return None
    if len(plain) > MAX_ABOUT_CHARS:
        plain = plain[:MAX_ABOUT_CHARS].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return plain


def about_from_page(page: str) -> Optional[str]:
    """The home page's own summary of the company (its description tag)."""
    found: Dict[str, str] = {}
    for tag in _META.findall(page or ""):
        attrs = {m[0].lower(): (m[2] or m[3]) for m in _ATTR.findall(tag)}
        kind = (attrs.get("name") or attrs.get("property") or "").lower()
        if kind in ("description", "og:description") and attrs.get("content"):
            found.setdefault(kind, attrs["content"])
    return clean_about(found.get("description", "")) or clean_about(found.get("og:description", ""))


def _is_public_host(host: str) -> bool:
    """Only ever fetch from the public internet, never an internal address."""
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)}
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)


async def _lookup(name: str, want_about: bool) -> Dict[str, Optional[str]]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=HEADERS) as client:
        domain = await company_logo.find_domain(client, name)
        if not domain:
            return {"website": None, "about": None}
        website = f"https://{domain}"
        about = None
        if want_about and await asyncio.to_thread(_is_public_host, domain):
            url = website
            for _ in range(3):  # follow redirects by hand, staying on the company's own site
                page = await client.get(url)
                target = page.headers.get("location", "")
                if page.status_code in (301, 302, 303, 307, 308) and target:
                    nxt = httpx.URL(url).join(target)
                    host = nxt.host or ""
                    if nxt.scheme != "https" or not (host == domain or host.endswith("." + domain)):
                        break
                    url = str(nxt)
                    continue
                if page.status_code == 200 and "html" in page.headers.get("content-type", ""):
                    about = about_from_page(page.text[:MAX_PAGE_BYTES])
                break
        return {"website": website, "about": about}


def remember(name: str, about: str) -> None:
    """Keeps a company note that came with a posting (first one wins)."""
    key = company_logo.normalise(name or "")
    text = clean_about(about)
    if not key or not text:
        return
    record = _load(key)
    if not record.get("about"):
        record.update({"about": text, "about_source": "posting"})
        _save(key, record)


async def get_info(name: str) -> Dict[str, Optional[str]]:
    """{"about", "website"} for a company; either may be None."""
    key = company_logo.normalise(name or "")
    empty: Dict[str, Optional[str]] = {"about": None, "website": None}
    if not key or len(name) > company_logo.MAX_NAME_LENGTH:
        return empty
    record = _load(key)
    fresh = time.time() - float(record.get("looked_up") or 0) < RETRY_SECONDS
    if settings.COMPANY_LOGOS_ENABLED and not (record.get("website") or fresh):
        async with _locks.setdefault(key, asyncio.Lock()):
            try:
                found = await _lookup(name, want_about=not record.get("about"))
                record = _load(key)
                record["website"] = found["website"]
                if found["about"] and not record.get("about"):
                    record.update({"about": found["about"], "about_source": "website"})
                record["looked_up"] = time.time()
                _save(key, record)
            except (httpx.HTTPError, ValueError, OSError):
                pass  # lookup unavailable right now: answer with what we have, retry next time
            finally:
                _locks.pop(key, None)
    return {"about": record.get("about"), "website": record.get("website")}
