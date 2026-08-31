"""
JobCopilot - Residential & Datacenter Proxy Rotator
Manages rotating proxy IP addresses for stealth browser automation sessions,
supporting Direct Connection, Bright Data, Oxylabs, and custom SOCKS5/HTTP pools.
"""

import os
import random
from typing import Optional, Dict, Any, List

from app.core.settings import settings


class ProxyRotator:
    """Provides rotation and configuration for Playwright browser contexts."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or os.environ.get("PROXY_PROVIDER", "direct").lower()
        self.proxy_pool = self._load_proxy_pool()

    def _load_proxy_pool(self) -> List[str]:
        raw_list = os.environ.get("PROXY_LIST", "")
        if raw_list:
            return [p.strip() for p in raw_list.split(",") if p.strip()]
        return []

    def get_proxy_config(self, session_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Returns Playwright-compatible proxy dictionary:
        {"server": "http://...", "username": "...", "password": "..."}
        or None for direct connections.
        """
        if self.provider == "direct" and not self.proxy_pool:
            return None

        if self.provider == "brightdata":
            host = os.environ.get("BRIGHTDATA_HOST", "brd.superproxy.io:22225")
            user = os.environ.get("BRIGHTDATA_USER", "lum-customer-hl_default-zone-residential")
            password = os.environ.get("BRIGHTDATA_PASSWORD", settings.PROXY_PASSWORD)
            session = session_id or str(random.randint(10000, 99999))
            return {
                "server": f"http://{host}",
                "username": f"{user}-session-{session}",
                "password": password
            }

        if self.provider == "oxylabs":
            host = os.environ.get("OXYLABS_HOST", "pr.oxylabs.io:7777")
            user = os.environ.get("OXYLABS_USER", "customer-user")
            password = os.environ.get("OXYLABS_PASSWORD", settings.PROXY_PASSWORD)
            return {
                "server": f"http://{host}",
                "username": f"customer-{user}-cc-us",
                "password": password
            }

        if self.proxy_pool:
            chosen = random.choice(self.proxy_pool)
            return {"server": chosen}

        return None


# Global Proxy Singleton
proxy_rotator = ProxyRotator()
