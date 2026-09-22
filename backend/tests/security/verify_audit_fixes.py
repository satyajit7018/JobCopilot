"""
Audit regression harness.

Runs each exploit from the 2026-09-22 audit against the real app and reports
FIXED (hole closed) or VULNERABLE (hole still open). Each check runs in its own
subprocess so settings/env and the in-memory singletons never leak between checks.

Usage (from backend/):  python tests/security/verify_audit_fixes.py
Exit code is 0 only when every check reports FIXED.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap

BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PRELUDE = textwrap.dedent("""
    import json, time, hmac, hashlib, os, sys, warnings, logging
    warnings.filterwarnings("ignore")
    logging.disable(logging.CRITICAL)
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    B = "/api/v1/auth"
    PW = "CorrectHorse!Battery9"
    def reg(email):
        r = c.post(B + "/register", json={"email": email, "password": PW, "full_name": email})
        assert r.status_code == 200, r.text
        return r.json()
    def H(tok):
        return {"Authorization": "Bearer " + tok}
    def result(fixed, detail=""):
        print("RESULT:" + json.dumps({"fixed": bool(fixed), "detail": str(detail)[:300]}))
""")

CHECKS = {}


def check(name, env=None):
    def deco(fn):
        CHECKS[name] = (fn.__doc__, env or {})
        return fn
    return deco


@check("P0-1 websocket cross-tenant leak")
def _():
    """
    a, b = reg("alice@a.com"), reg("bob@b.com")
    leaked = []
    with c.websocket_connect("/ws?token=" + b["access_token"]) as ws:
        c.post("/api/v1/jobs/log-call", headers=H(a["access_token"]), json={
            "company": "Acme", "role_title": "SDE", "status": "INTERVIEW",
            "call_notes": "SECRET-NOTES", "meeting_link": "https://meet/x"})
        c.post("/api/v1/interview/notify-invitation", headers=H(a["access_token"]), json={
            "company": "SECRET-CO", "role_title": "SDE", "job_id": "x", "meeting_url": "https://m"})
        # Bob sends a ping; the first message he gets back must be his own PONG, not Alice's data.
        ws.send_text("ping")
        for _ in range(3):
            msg = ws.receive_text()
            if "SECRET" in msg:
                leaked.append(msg)
            if '"PONG"' in msg:
                break
    result(not leaked, leaked[:1])
    """


@check("P0-2 stored XSS payload reaches another user")
def _():
    """
    a, b = reg("mallory@m.com"), reg("bob@b.com")
    payload = '<img src=x onerror="alert(1)">'
    got = None
    with c.websocket_connect("/ws?token=" + b["access_token"]) as ws:
        c.post("/api/v1/interview/notify-invitation", headers=H(a["access_token"]), json={
            "company": payload, "role_title": "SDE", "job_id": "x", "meeting_url": "https://m"})
        ws.send_text("ping")
        for _ in range(3):
            msg = ws.receive_text()
            if "onerror" in msg:
                got = msg
            if '"PONG"' in msg:
                break
    result(got is None, got)
    """


@check("P0-2b frontend HTML templates escape server data")
def _():
    """
    import re, glob
    os.chdir(os.path.join(os.getcwd(), "..", "frontend", "js"))
    # Expressions reviewed by hand and confirmed static, numeric, pre-escaped, or constant-mapped.
    # Anything NOT in this list that lands in an HTML template must go through escapeHTML().
    REVIEWED_SAFE = set(['app.js|actionsHTML', 'app.js|avatar.bg', 'app.js|avatar.icon', 'app.js|circumference', 'app.js|colKey', 'app.js|company', 'app.js|glowColor', 'app.js|icon', 'app.js|jobId', 'app.js|location', 'app.js|nextBatch', 'app.js|platform', 'app.js|platformBadgeClass', 'app.js|radius', 'app.js|remaining', 'app.js|renderMatchGaugeSVG(matchPct)', 'app.js|renderStageProgressLine(job.status)', 'app.js|strokeColor', 'app.js|strokeDashoffset', 'app.js|title', 'modules/command-palette.js|it.icon', 'modules/command-palette.js|it.label', 'modules/inbound-email.js|badgeClass', 'modules/inbound-email.js|boxId', 'modules/negotiation.js|currVal', "modules/outreach.js|isHit ? 'concept-badge-hit' : 'concept-badge-miss'", "modules/outreach.js|isHit ? '✅' : '⚠️'", "modules/portal-onboarding.js|isConn ? 'connected' : ''", "modules/portal-onboarding.js|isConn ? 'connected' : 'ready'", "modules/portal-onboarding.js|isConn ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.04)'", "modules/portal-onboarding.js|isConn ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-subtle)'", "modules/portal-onboarding.js|isConn ? 'var(--accent-emerald)' : 'var(--text-muted)'", "modules/portal-onboarding.js|isConn ? '✓ Connected' : 'Ready to Connect'", 'modules/portal-onboarding.js|p.desc', 'modules/portal-onboarding.js|p.icon', 'modules/portal-onboarding.js|p.id', 'modules/portal-onboarding.js|p.name', "modules/saas-admin.js|!state.currentOrgId ? 'active' : ''", "modules/saas-admin.js|isSelected ? 'active' : ''", 'modules/saas-admin.js|roleBadgeClass', "modules/saas-admin.js|u.is_active ? 'Active' : 'Disabled'", "modules/saas-admin.js|u.is_active ? 'var(--accent-emerald)' : 'var(--accent-rose)'"])
    NUMERIC = re.compile(r"(toFixed|Math\\.|\\.length\\b|Index\\b|\\bidx\\b|\\bi\\b|^\\s*(pct|score|scoreVal|percent|count|total|width|height|delay|n|num|now|textClass)\\s*$)")
    bad = []
    for f in ["app.js"] + sorted(glob.glob("modules/*.js")):
        s = open(f).read()
        for m in re.finditer(r"`((?:[^`\\\\]|\\\\.)*)`", s, re.S):
            body = m.group(1)
            if "<" not in body or "${" not in body:
                continue
            for e in re.findall(r"\\$\\{((?:[^{}]|\\{[^{}]*\\})*)\\}", body):
                e = e.strip()
                if "escapeHTML(" in e or NUMERIC.search(e) or (f + "|" + e) in REVIEWED_SAFE:
                    continue
                bad.append(f + ":" + str(s[:m.start()].count(chr(10)) + 1) + ":" + e)
    result(not bad, bad)
    """


@check("P0-3 unauthenticated inbound email webhook")
def _():
    """
    a = reg("alice@a.com")
    j = c.post("/api/v1/jobs/log-call", headers=H(a["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post("/api/v1/email/inbound-webhook", json={
        "user_id": a["user_id"], "sender": "hr@acme.com", "recipient": "x@y",
        "subject": "Your application at Acme",
        "body_text": "Unfortunately we have decided not to move forward with your application at Acme."})
    jobs = c.get("/api/v1/jobs", headers=H(a["access_token"])).json()
    jobs = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    status = [x["status"] for x in jobs if x["company"] == "Acme"]
    result(r.status_code in (401, 403) and status == ["INTERVIEW"], f"{r.status_code} {status}")
    """


@check("P0-3b webhook secret required in production config")
def _():
    """
    from app.core.settings import Settings
    try:
        Settings(ENV="production", JWT_SECRET="x" * 40, JOBCOPILOT_MASTER_KEY="k" * 44,
                 GOOGLE_OAUTH_CLIENT_ID="cid.apps.googleusercontent.com", INBOUND_EMAIL_WEBHOOK_SECRET=None)
        result(False, "production settings accepted without INBOUND_EMAIL_WEBHOOK_SECRET")
    except Exception as e:
        result("INBOUND_EMAIL_WEBHOOK_SECRET" in str(e), e)
    """


@check("P0-4a SSO bare-email login when ENV only comes from settings", env={"ENV": ""})
def _():
    """
    # Simulate a deploy that sets ENV=production through settings (.env file), not os.environ.
    from app.core.settings import settings
    object.__setattr__(settings, "ENV", "production")
    a = reg("victim@corp.com") if False else None
    r = c.post(B + "/google-sso", json={"email": "victim@corp.com"})
    result(r.status_code in (400, 401, 403), r.status_code)
    """


@check("P0-4b SSO accepts unverified Google email")
def _():
    """
    import google.oauth2.id_token as idt
    idt.verify_oauth2_token = lambda *a, **k: {"iss": "accounts.google.com", "aud": "cid",
                                               "email": "victim@corp.com", "email_verified": False}
    os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "cid"
    reg("victim@corp.com")
    r = c.post(B + "/google-sso", json={"id_token": "fake", "email": "victim@corp.com"})
    result(r.status_code in (400, 401, 403), r.status_code)
    """


@check("P0-4c SSO skips MFA")
def _():
    """
    import pyotp
    import google.oauth2.id_token as idt
    idt.verify_oauth2_token = lambda *a, **k: {"iss": "accounts.google.com", "aud": "cid",
                                               "email": "v@corp.com", "email_verified": True}
    os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "cid"
    u = reg("v@corp.com")
    s = c.post(B + "/mfa/setup", headers=H(u["access_token"])).json()
    c.post(B + "/mfa/verify", headers=H(u["access_token"]), json={"code": pyotp.TOTP(s["secret"]).now()})
    r = c.post(B + "/google-sso", json={"id_token": "fake"})
    body = r.json()
    result(r.status_code == 200 and body.get("mfa_required") is True and not body.get("access_token"),
           {k: v for k, v in body.items() if "token" not in k})
    """


@check("P0-4d SSO ignores email-less token and uses client email")
def _():
    """
    import google.oauth2.id_token as idt
    idt.verify_oauth2_token = lambda *a, **k: {"iss": "accounts.google.com", "aud": "cid", "email_verified": True}
    os.environ["GOOGLE_OAUTH_CLIENT_ID"] = "cid"
    reg("victim@corp.com")
    r = c.post(B + "/google-sso", json={"id_token": "fake", "email": "victim@corp.com"})
    result(r.status_code in (400, 401), r.status_code)
    """


@check("P0-5a vault decrypts across instances with same master key")
def _():
    """
    import subprocess, tempfile
    code = ("import sys;from app.core.credential_vault import CredentialVault;"
            "v=CredentialVault();"
            "print(v.encrypt_envelope(b'pw') if sys.argv[1]=='e' else v.decrypt_envelope(open(sys.argv[2]).read().strip()))")
    da, db_ = tempfile.mkdtemp(), tempfile.mkdtemp()
    env = dict(os.environ, JOBCOPILOT_MASTER_KEY="shared-master-key-for-test-0123456789")
    ct = subprocess.run([sys.executable, "-c", code, "e"], env=dict(env, JOBCOPILOT_DATA_DIR=da),
                        capture_output=True, text=True).stdout.strip().splitlines()[-1]
    f = os.path.join(da, "ct.txt"); open(f, "w").write(ct)
    out = subprocess.run([sys.executable, "-c", code, "d", f], env=dict(env, JOBCOPILOT_DATA_DIR=db_),
                         capture_output=True, text=True)
    result("b'pw'" in out.stdout, (out.stdout + out.stderr)[-200:])
    """


@check("P0-5b k8s pod spec sets a writable JOBCOPILOT_DATA_DIR")
def _():
    """
    import glob, re
    k8s = os.path.join(os.getcwd(), "..", "infra", "k8s")
    text = "".join(open(p).read() for p in glob.glob(os.path.join(k8s, "*.yaml")))
    has_dir = re.search(r"JOBCOPILOT_DATA_DIR:\\s*\\"?(/[^\\"\\s]+)", text)
    mounted = bool(has_dir) and (has_dir.group(1).startswith("/tmp") or ("mountPath: " + has_dir.group(1)) in text)
    result(bool(has_dir) and mounted, has_dir.group(1) if has_dir else "not set")
    """


@check("P0-6 signed Stripe webhook does not crash", env={"STRIPE_WEBHOOK_SECRET": "whsec_test"})
def _():
    """
    u = reg("payer@p.com")
    ev = {"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "object": "checkout.session", "mode": "subscription", "subscription": "sub_1",
        "customer": "cus_1", "metadata": {"user_id": u["user_id"], "tier": "PRO"}}}}
    body = json.dumps(ev); t = str(int(time.time()))
    sig = hmac.new(b"whsec_test", f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    r = c.post("/api/v1/billing/webhook", content=body,
               headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})
    result(r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    """


@check("P1-6 Stripe cancellation downgrades user", env={"STRIPE_WEBHOOK_SECRET": "whsec_test"})
def _():
    """
    u = reg("payer@p.com")
    def send(ev):
        body = json.dumps(ev); t = str(int(time.time()))
        sig = hmac.new(b"whsec_test", f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
        return c.post("/api/v1/billing/webhook", content=body,
                      headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})
    send({"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "object": "checkout.session", "mode": "subscription", "subscription": "sub_1",
        "customer": "cus_1", "metadata": {"user_id": u["user_id"], "tier": "PRO"}}}})
    mid = c.get(B + "/me", headers=H(u["access_token"])).json().get("role")
    # Real Stripe behaviour: the Subscription only carries subscription_data.metadata. We send what the
    # fixed checkout would have attached, AND rely on the stored customer id as the primary lookup.
    send({"id": "evt_2", "object": "event", "type": "customer.subscription.deleted", "data": {"object": {
        "id": "sub_1", "object": "subscription", "customer": "cus_1", "status": "canceled", "metadata": {}}}})
    end = c.get(B + "/me", headers=H(u["access_token"])).json().get("role")
    result(mid == "PRO" and end == "FREE", f"after checkout={mid} after cancel={end}")
    """


@check("P1-5 Stripe webhook does not overwrite ADMIN role", env={"STRIPE_WEBHOOK_SECRET": "whsec_test"})
def _():
    """
    from app.core.database import db
    u = reg("boss@p.com")
    db.update_user_role(u["user_id"], "ADMIN")
    ev = {"id": "evt_1", "object": "event", "type": "checkout.session.completed", "data": {"object": {
        "id": "cs_1", "object": "checkout.session", "mode": "subscription", "subscription": "sub_1",
        "customer": "cus_9", "metadata": {"user_id": u["user_id"], "tier": "PRO"}}}}
    body = json.dumps(ev); t = str(int(time.time()))
    sig = hmac.new(b"whsec_test", f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    c.post("/api/v1/billing/webhook", content=body,
           headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})
    role = db.get_user_by_id(u["user_id"]).role
    result(str(getattr(role, "value", role)) == "ADMIN", role)
    """


@check("P1-10 logout revokes refresh token")
def _():
    """
    u = reg("v@corp.com")
    c.post(B + "/logout", headers=H(u["access_token"]))
    r = c.post(B + "/refresh", json={"refresh_token": u["refresh_token"]})
    result(r.status_code == 401, r.status_code)
    """


@check("P1-11 password reset revokes existing sessions")
def _():
    """
    from app.api.auth import create_jwt_token
    from datetime import timedelta
    u = reg("v@corp.com")
    tok = create_jwt_token({"sub": u["user_id"], "email": "v@corp.com", "type": "reset_password"}, timedelta(minutes=15))
    r = c.post(B + "/reset-password", json={"token": tok, "new_password": "AnotherLongPassw0rd!"})
    old_access = c.get(B + "/me", headers=H(u["access_token"])).status_code
    old_refresh = c.post(B + "/refresh", json={"refresh_token": u["refresh_token"]}).status_code
    result(r.status_code == 200 and old_access == 401 and old_refresh == 401,
           f"reset={r.status_code} access={old_access} refresh={old_refresh}")
    """


@check("P1-1 async apply does not report fake SUCCESS")
def _():
    """
    u = reg("a@a.com")
    j = c.post("/api/v1/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post(f"/api/v1/bot/apply-async/{j['job_id']}", headers=H(u["access_token"]))
    if r.status_code >= 400:
        result(True, f"refused {r.status_code}"); raise SystemExit
    task = c.get(f"/api/v1/tasks/{r.json()['task_id']}", headers=H(u["access_token"])).json()
    st = task.get("task", {}).get("status")
    result(st != "SUCCESS", st)
    """


@check("P1-2 invalid submission mode rejected")
def _():
    """
    u = reg("a@a.com")
    j = c.post("/api/v1/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post(f"/api/v1/bot/apply/{j['job_id']}?mode=dry_run", headers=H(u["access_token"]))
    result(r.status_code in (400, 422), f"{r.status_code} {r.text[:100]}")
    """


@check("P1-4 resolve-held does not fake a submission")
def _():
    """
    from app.core.database import db
    from app.core.models import HITLEvent
    import uuid
    u = reg("a@a.com")
    j = c.post("/api/v1/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    fields = HITLEvent.model_fields if hasattr(HITLEvent, "model_fields") else HITLEvent.__fields__
    kw = dict(event_id="evt_" + uuid.uuid4().hex[:8], job_id=j["job_id"], company="Acme", role_title="SDE",
              question_text="Notice period?", input_type="text")
    kw = {k: v for k, v in kw.items() if k in fields}
    if "user_id" in fields: kw["user_id"] = u["user_id"]
    db.save_hitl_event(HITLEvent(**kw), user_id=u["user_id"])
    c.post("/api/v1/hitl/resolve-held", headers=H(u["access_token"]),
           json={"event_id": kw["event_id"], "user_answer": "30 days", "save_to_vault": False})
    job = db.get_job_by_id(j["job_id"], user_id=u["user_id"])
    st = str(getattr(job.status, "value", job.status))
    result(st != "SUBMITTED", st)
    """


@check("P1-12/13 metrics require auth and health hides exceptions", env={"METRICS_TOKEN": "scrape-secret"})
def _():
    """
    from app.core.settings import settings
    anon = c.get("/metrics").status_code
    wrong = c.get("/metrics", headers={"Authorization": "Bearer nope"}).status_code
    right = c.get("/metrics", headers={"Authorization": "Bearer scrape-secret"}).status_code
    object.__setattr__(settings, "METRICS_TOKEN", None)
    object.__setattr__(settings, "ENV", "production")
    prod_no_token = c.get("/metrics").status_code
    object.__setattr__(settings, "ENV", "development")
    import app.main as mainmod
    orig = mainmod.get_db
    def boom():
        raise RuntimeError("SECRET_INTERNAL_PATH /var/lib/pg/table_users")
    mainmod.get_db = boom
    h = c.get("/health").text
    mainmod.get_db = orig
    ok = anon == 401 and wrong == 401 and right == 200 and prod_no_token == 404 and "SECRET_INTERNAL_PATH" not in h
    result(ok, f"anon={anon} wrong={wrong} right={right} prod_no_token={prod_no_token} leak={'SECRET' in h}")
    """


@check("P1-15 org admin cannot invite an OWNER")
def _():
    """
    owner, adm, victim = reg("o@o.com"), reg("adm@o.com"), reg("new@o.com")
    org = c.post("/api/v1/orgs", headers=H(owner["access_token"]), json={"name": "Acme Org"}).json()
    oid = org.get("org_id") or org.get("id")
    c.post(f"/api/v1/orgs/{oid}/members", headers=H(owner["access_token"]), json={"email": "adm@o.com", "role": "ADMIN"})
    r = c.post(f"/api/v1/orgs/{oid}/members", headers=H(adm["access_token"]), json={"email": "new@o.com", "role": "OWNER"})
    result(r.status_code == 403, f"{r.status_code} {r.text[:100]}")
    """


def run_one(name):
    body, env_over = CHECKS[name]
    code = PRELUDE + textwrap.dedent(body)
    data_dir = tempfile.mkdtemp(prefix="jc_audit_")
    env = dict(os.environ, JOBCOPILOT_DATA_DIR=data_dir, PYTHONPATH=BACKEND)
    env.pop("INBOUND_EMAIL_WEBHOOK_SECRET", None)
    env.pop("STRIPE_WEBHOOK_SECRET", None)
    for k, v in env_over.items():
        if v == "":
            env.pop(k, None)
        else:
            env[k] = v
    p = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=180)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT:"):
            return json.loads(line[7:])
    return {"fixed": False, "detail": "CHECK ERRORED: " + (p.stderr.strip().splitlines() or ["?"])[-1][:250]}


if __name__ == "__main__":
    only = sys.argv[1:]
    failures = 0
    for name in CHECKS:
        if only and not any(o in name for o in only):
            continue
        r = run_one(name)
        tag = "FIXED     " if r["fixed"] else "VULNERABLE"
        failures += 0 if r["fixed"] else 1
        print(f"[{tag}] {name}  ::  {r['detail']}")
    print(f"\n{failures} open issue(s)")
    sys.exit(1 if failures else 0)
