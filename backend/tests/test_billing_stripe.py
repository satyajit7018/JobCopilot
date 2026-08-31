"""
JobCopilot - Stripe Billing & Subscription Checkout Test Suite
Validates checkout session creation, customer portal URL generation, and error handling.
"""

import uuid
import pytest
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import db
from app.core.models import User, UserRole
from app.api.auth import create_jwt_token


@pytest.fixture
def auth_header():
    user_id = f"usr_bill_{uuid.uuid4().hex[:6]}"
    email = f"{user_id}@jobcopilot.test"
    user = User(user_id=user_id, email=email, password_hash="test", role=UserRole.FREE)
    db.create_user(user)
    token = create_jwt_token({"sub": user_id, "email": email, "role": "FREE", "type": "access"}, timedelta(minutes=30))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_billing_plan_endpoint(auth_header):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_header) as ac:
        res = await ac.get("/api/billing/plan")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["plan"]["tier"] == "FREE"


@pytest.mark.asyncio
async def test_create_checkout_session(auth_header):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_header) as ac:
        res = await ac.post("/api/billing/checkout", json={"tier": "PRO"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["tier"] == "PRO"
        assert "checkout_url" in data
        assert "https://checkout.stripe.com" in data["checkout_url"]


@pytest.mark.asyncio
async def test_create_customer_portal_session(auth_header):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_header) as ac:
        res = await ac.post("/api/billing/portal", json={})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "portal_url" in data
        assert "stripe.com" in data["portal_url"]
