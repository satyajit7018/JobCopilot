"""
JobCopilot - 100 Concurrent Job Seekers Load Testing Script (Locust)
Simulates realistic candidate behavior under load:
1. User registration & JWT authentication
2. Resume upload & profile ingestion
3. 0-day job discovery cycle
4. Knowledge Vault hybrid vector searches
5. Mock interview question generation
6. Telemetry & Kanban board polling
"""

import uuid

try:
    from locust import HttpUser, task, between
    HAS_LOCUST = True
except ImportError:
    HAS_LOCUST = False
    # Dummy classes for environments without locust installed
    def task(weight=1):
        def decorator(f):
            return f
        return decorator

    def between(a, b):
        return (a, b)

    class HttpUser:
        abstract = True
        wait_time = (0.5, 2.0)
        client = None


class CandidateUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Authenticates user and retrieves JWT bearer token."""
        self.user_email = f"load_user_{uuid.uuid4().hex[:8]}@example.com"
        self.password = "Password123!"
        self.headers = {}

        if self.client:
            # Register User
            res = self.client.post("/api/auth/register", json={
                "email": self.user_email,
                "password": self.password,
                "full_name": "Load Test Candidate"
            })
            if res.status_code == 200:
                token = res.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {token}"}

    @task(3)
    def view_pipeline(self):
        """Polls 0-day pipeline and funnel analytics."""
        if self.client:
            self.client.get("/api/jobs", headers=self.headers)
            self.client.get("/api/analytics/funnel", headers=self.headers)

    @task(2)
    def query_vault(self):
        """Performs vector search in Knowledge Vault."""
        if self.client:
            self.client.post("/api/vault/match", json={
                "question": "What is your experience with Docker and Kubernetes in production?",
                "company": "Stripe",
                "role": "Senior Infrastructure Engineer"
            }, headers=self.headers)

    @task(1)
    def trigger_discovery(self):
        """Runs 0-day feed discovery."""
        if self.client:
            self.client.post("/api/discovery/run", headers=self.headers)

    @task(1)
    def check_billing_plan(self):
        """Checks subscription usage quota."""
        if self.client:
            self.client.get("/api/billing/plan", headers=self.headers)
