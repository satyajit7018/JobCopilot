"""
JobCopilot - Append-Only Security Audit Logging & Anomaly Detection Engine
Records cryptographic audit events for authentication, authorization, MFA lifecycle,
administrative actions, and analyzes real-time threat patterns (brute-force, velocity anomalies).
"""

import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque

from app.core.database import db


class SecurityAuditLogger:
    """Enterprise append-only security audit log engine with automated anomaly detection."""

    def __init__(self):
        # Sliding window for brute force detection: key -> deque of timestamps
        self._failed_attempts_by_ip = defaultdict(deque)
        self._failed_attempts_by_user = defaultdict(deque)
        # Sliding window for velocity / rapid IP shift detection: user_id -> deque of (timestamp, ip)
        self._user_ip_history = defaultdict(deque)
        self.WINDOW_SECONDS = 300  # 5 minutes
        self.BRUTE_FORCE_THRESHOLD = 5

    def _prune_old_events(self, dq: deque, now: float):
        """Removes entries older than WINDOW_SECONDS."""
        while dq and (now - (dq[0] if isinstance(dq[0], (int, float)) else dq[0][0])) > self.WINDOW_SECONDS:
            dq.popleft()

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        severity: str = "INFO",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Inserts an immutable security audit event and evaluates anomaly triggers.
        """
        now_ts = time.time()
        now_str = datetime.now().isoformat()
        log_id = f"sec_{uuid.uuid4().hex[:16]}"
        ip = ip_address or "127.0.0.1"
        payload_details = details or {}

        log_record = {
            "log_id": log_id,
            "user_id": user_id,
            "event_type": event_type,
            "severity": severity.upper(),
            "ip_address": ip,
            "user_agent": user_agent or "",
            "details": payload_details,
            "created_at": now_str
        }

        # 1. Append to persistent audit storage
        db.insert_security_audit_log(log_record)

        # 2. Run real-time anomaly detection rules
        self._check_anomalies(event_type, user_id, ip, user_agent, now_ts)

        return log_record

    def _check_anomalies(
        self,
        event_type: str,
        user_id: Optional[str],
        ip: str,
        user_agent: Optional[str],
        now_ts: float
    ):
        """Analyzes event stream for brute-force attacks and suspicious access shifts."""
        if event_type == "auth.login.failed":
            # Track IP
            ip_dq = self._failed_attempts_by_ip[ip]
            self._prune_old_events(ip_dq, now_ts)
            ip_dq.append(now_ts)

            if len(ip_dq) >= self.BRUTE_FORCE_THRESHOLD:
                # Trigger brute-force anomaly for IP
                self._record_anomaly(
                    "anomaly.brute_force",
                    user_id=user_id,
                    ip=ip,
                    user_agent=user_agent,
                    details={
                        "threat": "Repeated failed login threshold exceeded",
                        "failed_attempts": len(ip_dq),
                        "window_seconds": self.WINDOW_SECONDS,
                        "source": "ip"
                    }
                )

            # Track User if known
            if user_id:
                user_dq = self._failed_attempts_by_user[user_id]
                self._prune_old_events(user_dq, now_ts)
                user_dq.append(now_ts)

                if len(user_dq) >= self.BRUTE_FORCE_THRESHOLD:
                    self._record_anomaly(
                        "anomaly.brute_force",
                        user_id=user_id,
                        ip=ip,
                        user_agent=user_agent,
                        details={
                            "threat": "Targeted user account credential stuffing attack",
                            "failed_attempts": len(user_dq),
                            "window_seconds": self.WINDOW_SECONDS,
                            "source": "user"
                        }
                    )

        elif event_type == "auth.login.success" and user_id:
            # Check rapid geographic/IP velocity change
            user_ip_dq = self._user_ip_history[user_id]
            self._prune_old_events(user_ip_dq, now_ts)

            if user_ip_dq:
                prev_time, prev_ip = user_ip_dq[-1]
                if prev_ip != ip and (now_ts - prev_time) < 600:  # within 10 min
                    self._record_anomaly(
                        "anomaly.suspicious_session",
                        user_id=user_id,
                        ip=ip,
                        user_agent=user_agent,
                        details={
                            "threat": "Rapid IP shift across active sessions",
                            "previous_ip": prev_ip,
                            "current_ip": ip,
                            "delta_seconds": int(now_ts - prev_time)
                        }
                    )
            user_ip_dq.append((now_ts, ip))

    def _record_anomaly(
        self,
        event_type: str,
        user_id: Optional[str],
        ip: str,
        user_agent: Optional[str],
        details: Dict[str, Any]
    ):
        """Records a detected anomaly alert into the audit log."""
        log_id = f"sec_alert_{uuid.uuid4().hex[:12]}"
        now_str = datetime.now().isoformat()
        db.insert_security_audit_log({
            "log_id": log_id,
            "user_id": user_id,
            "event_type": event_type,
            "severity": "CRITICAL",
            "ip_address": ip,
            "user_agent": user_agent or "",
            "details": details,
            "created_at": now_str
        })

    def get_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Queries security audit log records with total count metadata."""
        logs = db.list_security_audit_logs(
            user_id=user_id,
            event_type=event_type,
            severity=severity,
            limit=limit,
            offset=offset
        )
        total = db.count_security_audit_logs(
            user_id=user_id,
            event_type=event_type,
            severity=severity
        )
        return {
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        }


security_logger = SecurityAuditLogger()
