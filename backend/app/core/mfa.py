"""
JobCopilot - Multi-Factor Authentication (MFA / TOTP) Engine
RFC 6238 Time-Based One-Time Password generation, URI provisioning,
cryptographic verification, and single-use backup recovery code management.
"""

import time
import hmac
import hashlib
import struct
import base64
import secrets
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

try:
    import pyotp
    HAS_PYOTP = True
except ImportError:
    pyotp = None
    HAS_PYOTP = False


class MFAEngine:
    """Enterprise MFA/TOTP engine compliant with RFC 6238."""

    ISSUER_NAME = "JobCopilot"
    STEP_SECONDS = 30
    DIGITS = 6

    @classmethod
    def generate_secret(cls) -> str:
        """Generates a cryptographically secure 32-character Base32 TOTP secret."""
        if HAS_PYOTP and pyotp:
            return pyotp.random_base32(32)
        random_bytes = secrets.token_bytes(20)
        return base64.b32encode(random_bytes).decode('utf-8').replace('=', '')

    @classmethod
    def generate_provisioning_uri(cls, secret: str, email: str, issuer: Optional[str] = None) -> str:
        """Generates standard otpauth:// provisioning URI for authenticator apps (Google/Microsoft Auth)."""
        iss = issuer or cls.ISSUER_NAME
        if HAS_PYOTP and pyotp:
            totp = pyotp.TOTP(secret, issuer=iss)
            return totp.provisioning_uri(name=email, issuer_name=iss)

        # RFC standard URI formatting
        from urllib.parse import quote
        label = f"{quote(iss)}:{quote(email)}"
        return f"otpauth://totp/{label}?secret={secret}&issuer={quote(iss)}&algorithm=SHA1&digits={cls.DIGITS}&period={cls.STEP_SECONDS}"

    @classmethod
    def _fallback_generate_totp(cls, secret: str, for_time: int) -> str:
        """Pure-Python RFC 6238 HOTP/TOTP computation fallback."""
        try:
            # Pad Base32 secret if necessary
            clean_secret = secret.strip().upper()
            padding = (8 - len(clean_secret) % 8) % 8
            key = base64.b32decode(clean_secret + '=' * padding)
        except Exception:
            key = secret.encode('utf-8')

        counter = int(for_time // cls.STEP_SECONDS)
        counter_bytes = struct.pack(">Q", counter)
        h = hmac.new(key, counter_bytes, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        code_int = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
        code_str = str(code_int % (10 ** cls.DIGITS)).zfill(cls.DIGITS)
        return code_str

    @classmethod
    def verify_totp(cls, secret: str, code: str, valid_window: int = 1) -> bool:
        """
        Verifies a 6-digit TOTP code against the secret within a drift window (±30s by default).
        """
        clean_code = str(code).strip().replace(" ", "")
        if len(clean_code) != cls.DIGITS or not clean_code.isdigit():
            return False

        if HAS_PYOTP and pyotp:
            try:
                totp = pyotp.TOTP(secret)
                if totp.verify(clean_code, valid_window=valid_window):
                    return True
            except Exception:
                pass

        # Verification via fallback window
        current_t = int(time.time())
        for step in range(-valid_window, valid_window + 1):
            t = current_t + (step * cls.STEP_SECONDS)
            expected_code = cls._fallback_generate_totp(secret, t)
            if hmac.compare_digest(expected_code, clean_code):
                return True

        return False

    @classmethod
    def generate_current_totp(cls, secret: str) -> str:
        """Generates current valid 6-digit TOTP for verification testing."""
        if HAS_PYOTP and pyotp:
            return pyotp.TOTP(secret).now()
        return cls._fallback_generate_totp(secret, int(time.time()))

    @classmethod
    def generate_backup_codes(cls, count: int = 8) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Generates N single-use backup recovery codes.
        Returns:
            plaintext_codes: List[str] (presented once to user to store offline)
            hashed_storage: List[Dict[str, Any]] (persisted securely in database)
        """
        plaintext_codes: List[str] = []
        hashed_storage: List[Dict[str, Any]] = []

        for _ in range(count):
            # Format: 10 alphanumeric characters formatted as XXXXX-XXXXX
            part1 = secrets.token_hex(3).upper()[:5]
            part2 = secrets.token_hex(3).upper()[:5]
            code = f"{part1}-{part2}"
            plaintext_codes.append(code)

            code_hash = hashlib.sha256(code.encode('utf-8')).hexdigest()
            hashed_storage.append({
                "hash": code_hash,
                "used": False,
                "used_at": None
            })

        return plaintext_codes, hashed_storage

    @classmethod
    def verify_and_consume_backup_code(
        cls,
        backup_codes: List[Dict[str, Any]],
        input_code: str
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Validates input against stored hashed recovery codes.
        If valid and unused, consumes the code and returns (True, updated_codes_list).
        """
        clean_input = input_code.strip().upper()
        input_hash = hashlib.sha256(clean_input.encode('utf-8')).hexdigest()

        updated_codes = []
        consumed = False

        for entry in backup_codes:
            code_hash = entry.get("hash")
            is_used = entry.get("used", False)

            if not consumed and not is_used and hmac.compare_digest(code_hash, input_hash):
                consumed = True
                updated_codes.append({
                    "hash": code_hash,
                    "used": True,
                    "used_at": datetime.now().isoformat()
                })
            else:
                updated_codes.append(entry)

        return consumed, updated_codes


mfa_engine = MFAEngine()
