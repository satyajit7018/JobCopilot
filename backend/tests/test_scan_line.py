"""The app's "Checked N postings X ago" line uses real figures from the last shared read."""

import asyncio

from fastapi.testclient import TestClient

from app.discovery.orchestrator import DiscoveryOrchestrator, discovery_orchestrator


def test_status_reports_the_last_shared_read(auth_client: TestClient, monkeypatch):
    async def three(self, companies):
        return [
            {"company": f"Co{i}", "title": "Engineer", "location": "Pune", "description": "x", "url": f"https://example.test/{i}", "platform": "Greenhouse"}
            for i in range(3)
        ]

    monkeypatch.setattr(DiscoveryOrchestrator, "_fetch_all_raw_leads", three)
    asyncio.run(discovery_orchestrator.get_leads())

    from app.core.cache import cache_manager
    user_id = auth_client.get("/api/auth/me").json()["user_id"]
    asyncio.run(cache_manager.invalidate_namespace(user_id, "discovery"))

    status = auth_client.get("/api/discovery/status").json()
    assert status["last_read"]["postings"] == 3
    assert status["last_read"]["at"].startswith("20")
