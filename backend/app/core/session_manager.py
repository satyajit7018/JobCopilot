"""
JobCopilot - Session & Device Management Subsystem
Tracks active user sessions, parses device fingerprints from User-Agents,
provides remote session revocation linked to JWT blacklist, and session heartbeat.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from app.core.database import db


def parse_device_name(user_agent: Optional[str]) -> str:
    """Extracts a human-readable OS and Browser summary from the User-Agent header."""
    if not user_agent or not user_agent.strip():
        return "Unknown Device"

    ua = user_agent.lower()

    # Determine OS / Platform
    platform = "Desktop"
    if "iphone" in ua or "ipad" in ua:
        platform = "iOS Device"
    elif "android" in ua:
        platform = "Android Mobile"
    elif "macintosh" in ua or "mac os" in ua:
        platform = "macOS"
    elif "windows" in ua:
        platform = "Windows PC"
    elif "linux" in ua:
        platform = "Linux PC"

    # Determine Browser
    browser = "Browser"
    if "edg/" in ua or "edge" in ua:
        browser = "Edge"
    elif "chrome" in ua and "safari" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "postman" in ua:
        browser = "Postman Client"
    elif "python" in ua:
        browser = "API Client"

    return f"{platform} ({browser})"


class SessionManager:
    """Manages active user login sessions, device metadata, and instant revocation."""

    @classmethod
    def create_session(
        cls,
        user_id: str,
        token_jti: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates a new active session record upon successful authentication."""
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        device_name = parse_device_name(user_agent)
        now_str = datetime.now().isoformat()

        session_record = {
            "session_id": session_id,
            "user_id": user_id,
            "token_jti": token_jti,
            "ip_address": ip_address or "127.0.0.1",
            "user_agent": user_agent or "",
            "device_name": device_name,
            "created_at": now_str,
            "last_active": now_str,
            "is_active": True
        }
        db.create_session(session_record)
        return session_record

    @classmethod
    def list_active_sessions(
        cls,
        user_id: str,
        current_jti: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists active sessions for a user, highlighting the current session."""
        sessions = db.list_user_sessions(user_id, active_only=True)
        results = []
        for s in sessions:
            is_current = bool(current_jti and s.get("token_jti") == current_jti)
            results.append({
                "session_id": s["session_id"],
                "device_name": s.get("device_name", "Unknown Device"),
                "ip_address": s.get("ip_address"),
                "created_at": s.get("created_at"),
                "last_active": s.get("last_active"),
                "is_current": is_current
            })
        return results

    @classmethod
    def revoke_session(cls, session_id: str, user_id: str) -> bool:
        """
        Revokes an individual session and immediately blacklists its associated JWT token.
        """
        session = db.get_session(session_id)
        if not session or session.get("user_id") != user_id:
            return False

        # Blacklist JWT token JTI so it cannot be used
        token_jti = session.get("token_jti")
        if token_jti:
            far_future_exp = str(int((datetime.now() + timedelta(days=30)).timestamp()))
            db.revoke_token(token_jti, user_id, far_future_exp)

        return db.revoke_session(session_id, user_id)

    @classmethod
    def revoke_all_sessions(cls, user_id: str, except_jti: Optional[str] = None) -> int:
        """
        Revokes all active sessions for a user (optionally preserving the current active session).
        """
        active_sessions = db.list_user_sessions(user_id, active_only=True)
        revoked_count = 0
        far_future_exp = str(int((datetime.now() + timedelta(days=30)).timestamp()))

        for s in active_sessions:
            jti = s.get("token_jti")
            if except_jti and jti == except_jti:
                continue
            if jti:
                db.revoke_token(jti, user_id, far_future_exp)
            db.revoke_session(s["session_id"], user_id)
            revoked_count += 1

        return revoked_count

    @classmethod
    def touch_session(cls, token_jti: str) -> bool:
        """Updates last_active timestamp for an active session."""
        if not token_jti:
            return False
        return db.update_session_activity(token_jti)


session_manager = SessionManager()
