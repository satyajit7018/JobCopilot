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
    B = "/api/auth"
    PW = "CorrectHorse!Battery9"
    def reg(email):
        r = c.post(B + "/register", json={"email": email, "password": PW, "full_name": email})
        assert r.status_code == 200, r.text
        return r.json()
    def H(tok):
        return {"Authorization": "Bearer " + tok}
    def premium(u):
        # Automatic applying is a Premium feature; without this the plan gate answers 402
        # before the code under test is reached.
        from app.core.database import db
        db.update_user_role(u["user_id"], "PRO")
        return u
    def no_browser():
        # These checks must never drive a real browser, whatever is installed here.
        from app.bot import runner
        runner.HAS_PLAYWRIGHT = False
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
        c.post("/api/jobs/log-call", headers=H(a["access_token"]), json={
            "company": "Acme", "role_title": "SDE", "status": "INTERVIEW",
            "call_notes": "SECRET-NOTES", "meeting_link": "https://meet/x"})
        c.post("/api/interview/notify-invitation", headers=H(a["access_token"]), json={
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
        c.post("/api/interview/notify-invitation", headers=H(a["access_token"]), json={
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


# P0-2b (legacy UI templates escaping server data) was retired with that UI: the React
# app renders text through JSX, which escapes by default, and never uses innerHTML.


@check("P0-3 unauthenticated inbound email webhook")
def _():
    """
    a = reg("alice@a.com")
    j = c.post("/api/jobs/log-call", headers=H(a["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post("/api/email/inbound-webhook", json={
        "user_id": a["user_id"], "sender": "hr@acme.com", "recipient": "x@y",
        "subject": "Your application at Acme",
        "body_text": "Unfortunately we have decided not to move forward with your application at Acme."})
    jobs = c.get("/api/jobs", headers=H(a["access_token"])).json()
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


@check("P1-10 logout revokes refresh token")
def _():
    """
    u = reg("v@corp.com")
    c.post(B + "/logout", headers=H(u["access_token"]))
    r = c.post(B + "/refresh", json={"refresh_token": u["refresh_token"]})
    result(r.status_code == 401, r.status_code)
    """


@check("P1-1 async apply does not report fake SUCCESS")
def _():
    """
    no_browser()
    u = premium(reg("a@a.com"))
    j = c.post("/api/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post(f"/api/bot/apply-async/{j['job_id']}", headers=H(u["access_token"]))
    if r.status_code != 202:
        result(False, f"not accepted for a Premium user: {r.status_code} {r.text[:100]}"); raise SystemExit
    st = None
    for _ in range(40):
        task = c.get(f"/api/tasks/{r.json()['task_id']}", headers=H(u["access_token"])).json()
        st = task.get("task", {}).get("status")
        if st not in (None, "PENDING", "QUEUED", "STARTED", "RUNNING", "IN_PROGRESS"):
            break
        time.sleep(0.25)
    result(st != "SUCCESS", f"with no browser available the task ended as {st}")
    """


@check("P1-2 invalid submission mode rejected")
def _():
    """
    no_browser()
    u = premium(reg("a@a.com"))
    j = c.post("/api/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post(f"/api/bot/apply/{j['job_id']}?mode=dry_run", headers=H(u["access_token"]))
    result(r.status_code in (400, 422), f"{r.status_code} {r.text[:100]}")
    """


@check("P1-4 resolve-held does not fake a submission")
def _():
    """
    from app.core.database import db
    from app.core.models import HITLEvent
    import uuid
    no_browser()
    u = premium(reg("a@a.com"))
    j = c.post("/api/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    fields = HITLEvent.model_fields if hasattr(HITLEvent, "model_fields") else HITLEvent.__fields__
    kw = dict(event_id="evt_" + uuid.uuid4().hex[:8], job_id=j["job_id"], company="Acme", role_title="SDE",
              question_text="Notice period?", input_type="text")
    kw = {k: v for k, v in kw.items() if k in fields}
    if "user_id" in fields: kw["user_id"] = u["user_id"]
    db.save_hitl_event(HITLEvent(**kw), user_id=u["user_id"])
    c.post("/api/hitl/resolve-held", headers=H(u["access_token"]),
           json={"event_id": kw["event_id"], "user_answer": "30 days", "save_to_vault": False})
    job = db.get_job_by_id(j["job_id"], user_id=u["user_id"])
    st = str(getattr(job.status, "value", job.status))
    result(st != "SUBMITTED", st)
    """


@check("A-1 real sending is switched off by default")
def _():
    """
    from app.core.database import db
    from app.core.models import ConsentType, UserConsent
    no_browser()
    u = premium(reg("a@a.com"))
    db.record_user_consent(UserConsent(user_id=u["user_id"], consent_type=ConsentType.AUTONOMOUS_SUBMISSION, consented=True))
    j = c.post("/api/jobs/log-call", headers=H(u["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    r = c.post(f"/api/jobs/apply-async/{j['job_id']}?mode=LIVE", headers=H(u["access_token"]))
    result(r.status_code == 403, f"{r.status_code} {r.text[:100]}")
    """


@check("A-2 forms never get placeholders, canned essays or defaults")
def _():
    """
    from app.bot.form import answer_for
    from app.core.models import CandidateProfile
    p = CandidateProfile(user_id="usr_x", full_name="T", email="t@t.test", phone="", location="")
    answers = [answer_for(q, p, company="Acme") for q in (
        "What is your expected salary?", "What is your notice period?", "Are you legally authorized to work here?",
        "Why do you want to work at our company?", "Share a link to a technical project you built.",
        "How many years of experience do you have with Kubernetes?")]
    result(all(a is None for a in answers), answers)
    """


@check("A-3 a saved answer stays with its owner")
def _():
    """
    from app.bot.form import answer_for
    from app.core.database import db
    from app.core.models import CandidateProfile, HITLEvent
    import uuid
    a, b = premium(reg("a@a.com")), premium(reg("b@b.com"))
    j = c.post("/api/jobs/log-call", headers=H(a["access_token"]), json={
        "company": "Acme", "role_title": "SDE", "status": "INTERVIEW", "call_notes": "n", "meeting_link": ""}).json()
    evt = HITLEvent(event_id="evt_" + uuid.uuid4().hex[:8], user_id=a["user_id"], job_id=j["job_id"], company="Acme",
                    role_title="SDE", question_text="Do you hold a security clearance?", input_type="text")
    db.save_hitl_event(evt, user_id=a["user_id"])
    c.post("/api/hitl/resolve-held", headers=H(a["access_token"]),
           json={"event_id": evt.event_id, "user_answer": "Yes, level 2", "save_to_vault": True})
    q = "Do you hold a security clearance?"
    mine = answer_for(q, CandidateProfile(user_id=a["user_id"], full_name="A", email="a@a.com", phone="", location=""))
    theirs = answer_for(q, CandidateProfile(user_id=b["user_id"], full_name="B", email="b@b.com", phone="", location=""))
    shared = [e for e in db.get_vault_entries("default") if e.question_pattern == q]
    result(mine == "Yes, level 2" and theirs is None and not shared, f"mine={mine} theirs={theirs} shared={len(shared)}")
    """


@check("A-4 saved answers: encrypted at rest, never used for a similar question, private to their owner")
def _():
    """
    from app.bot.form import answer_for
    from app.core.database import db
    from app.core.models import CandidateProfile
    a, b = reg("a@a.com"), reg("b@b.com")
    r = c.put("/api/answers", headers=H(a["access_token"]), json={"question": "Do you hold a security clearance?", "answer": "Yes, level 2"})
    qa = r.json()["id"]
    with db.get_connection() as conn:
        raw = conn.execute("SELECT answer_template FROM vault WHERE qa_id = ?", (qa,)).fetchone()[0]
    lookalike = answer_for("Have you ever held a clearance?", CandidateProfile(user_id=a["user_id"], full_name="A", email="a@a.com", phone="", location=""))
    other = [c.patch(f"/api/answers/{qa}", headers=H(b["access_token"]), json={"answer": "x"}).status_code,
             c.delete(f"/api/answers/{qa}", headers=H(b["access_token"])).status_code]
    result("level 2" not in raw and lookalike is None and other == [404, 404], f"plain={'level 2' in raw} lookalike={lookalike} other={other}")
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
