"""
JobCopilot - SaaS Phase 2 Integration Tests
Tests Object Storage abstraction, Proxy Rotator, Async Task Queue, and Multi-Tenant WebSocket Gateway.
"""

import sys
from pathlib import Path

# Add backend directory and venv site-packages to path
backend_dir = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(backend_dir))
venv_site_packages = backend_dir / "venv" / "lib" / "python3.9" / "site-packages"
if venv_site_packages.exists():
    sys.path.insert(0, str(venv_site_packages))

import pytest
import asyncio
from app.core.object_storage import ObjectStorageAdapter, storage
from app.bot.proxy_rotator import ProxyRotator
from app.tasks.celery_app import local_task_runner
from app.tasks.apply_task import enqueue_apply_job
from app.api.ws_gateway import MultiTenantWebSocketGateway


class TestSaaSPhase2:

    def test_object_storage_lifecycle(self, tmp_path):
        """Verifies local/cloud object storage upload, retrieval, and pre-signed links."""
        adapter = ObjectStorageAdapter(backend="local")
        adapter.local_base_dir = tmp_path

        user_id = "user_saas_42"
        resume_content = b"%PDF-1.4 Mock Resume Bytes For Satyajit"

        # 1. Upload Resume
        saved_path = adapter.upload_resume(user_id, "resume_v1.pdf", resume_content)
        assert Path(saved_path).exists()

        # 2. Retrieve Content
        fetched = adapter.get_resume_content(user_id, "resume_v1.pdf")
        assert fetched == resume_content

        # 3. Presigned Download URL
        url = adapter.get_presigned_url(user_id, "resume_v1.pdf", expires_in=600)
        assert f"user_id={user_id}" in url
        assert "resume_v1.pdf" in url

        # 4. Upload Screenshot
        screenshot_bytes = b"\x89PNG\r\n\x1a\nMockPNGBytes"
        ss_path = adapter.upload_screenshot(user_id, "job_999", screenshot_bytes)
        assert Path(ss_path).exists()

    def test_proxy_rotator_modes(self):
        """Verifies proxy configuration generation across providers."""
        # Direct mode
        direct_rotator = ProxyRotator(provider="direct")
        assert direct_rotator.get_proxy_config() is None

        # Bright Data mode
        bd_rotator = ProxyRotator(provider="brightdata")
        bd_cfg = bd_rotator.get_proxy_config(session_id="test_session")
        assert bd_cfg is not None
        assert "http://" in bd_cfg["server"]
        assert "session-test_session" in bd_cfg["username"]

        # Oxylabs mode
        oxy_rotator = ProxyRotator(provider="oxylabs")
        oxy_cfg = oxy_rotator.get_proxy_config()
        assert oxy_cfg is not None
        assert "customer-" in oxy_cfg["username"]

    def test_async_task_runner(self):
        """Verifies enqueueing and completion of async tasks."""
        def mock_worker_fn(x, y):
            return x * y + 10

        task_id = local_task_runner.enqueue("calc_task", mock_worker_fn, 5, 6)
        assert task_id is not None

        status = local_task_runner.get_task_status(task_id)
        assert status is not None
        assert status["result"] == 40
        assert status["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_multi_tenant_ws_gateway(self):
        """Verifies multi-tenant isolation in WebSocket messaging."""
        gateway = MultiTenantWebSocketGateway()

        class MockWebSocket:
            def __init__(self):
                self.messages = []
                self.is_connected = False

            async def accept(self):
                self.is_connected = True

            async def send_text(self, text):
                self.messages.append(text)

        ws_user_a = MockWebSocket()
        ws_user_b = MockWebSocket()

        await gateway.connect(ws_user_a, user_id="user_A")
        await gateway.connect(ws_user_b, user_id="user_B")

        # Send strictly to User A
        await gateway.send_to_user("user_A", {"type": "HITL_PROMPT", "question": "Are you open to relocate?"})
        assert len(ws_user_a.messages) == 1
        assert "Are you open to relocate?" in ws_user_a.messages[0]
        assert len(ws_user_b.messages) == 0

        # Broadcast to all
        await gateway.broadcast({"type": "SYSTEM_ANNOUNCEMENT", "text": "Platform Maintenance in 10m"})
        assert len(ws_user_a.messages) == 2
        assert len(ws_user_b.messages) == 1

        # Disconnect User A
        gateway.disconnect(ws_user_a, user_id="user_A")
        assert ws_user_a not in gateway.user_sockets.get("user_A", [])
