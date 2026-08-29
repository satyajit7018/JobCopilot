"""
JobCopilot - Argon2id & AES-256-GCM Cryptographic Credential & PII Vault
Local-first, secure storage for passwords, API keys, platform session cookies,
and sensitive candidate PII with OS Keychain integration.
"""

import os
import json
import base64
import keyring
from typing import Dict, Optional, Any
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from app.core.config import VAULT_ENC_PATH, APP_DIR

try:
    from argon2.low_level import hash_secret_raw, Type
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False


class CredentialVault:
    """State-of-the-art encrypted credential vault using Argon2id and AES-256-GCM."""

    KEYRING_SERVICE = "JobCopilot"
    KEYRING_USERNAME = "master_key"

    def __init__(self, vault_path: Path = VAULT_ENC_PATH):
        self.vault_path = Path(vault_path)
        self.salt_path = APP_DIR / "vault.salt"
        self._init_salt()

    def _init_salt(self):
        """Initializes or loads a unique 32-byte cryptographic salt."""
        if not self.salt_path.exists():
            salt = os.urandom(32)
            with open(self.salt_path, "wb") as f:
                f.write(salt)
            self.salt = salt
        else:
            with open(self.salt_path, "rb") as f:
                self.salt = f.read()

    def get_or_create_master_key(self) -> str:
        """Retrieves master key from OS Keychain or creates a secure random 32-byte key."""
        try:
            stored_key = keyring.get_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME)
            if stored_key:
                return stored_key
            new_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            keyring.set_password(self.KEYRING_SERVICE, self.KEYRING_USERNAME, new_key)
            return new_key
        except Exception:
            # Fallback to local machine identifier if keyring is unavailable in headless CI
            fallback_file = APP_DIR / ".master.key"
            if fallback_file.exists():
                with open(fallback_file, "r") as f:
                    return f.read().strip()
            new_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            with open(fallback_file, "w") as f:
                f.write(new_key)
            return new_key

    def _derive_key(self, master_password: str) -> bytes:
        """Derives a 256-bit key using Argon2id (or PBKDF2 as fallback)."""
        password_bytes = master_password.encode('utf-8')
        if HAS_ARGON2:
            try:
                # Argon2id: 64MB memory, 3 iterations, 4 parallelism
                return hash_secret_raw(
                    secret=password_bytes,
                    salt=self.salt,
                    time_cost=3,
                    memory_cost=65536,
                    parallelism=4,
                    hash_len=32,
                    type=Type.ID
                )
            except Exception:
                pass

        # PBKDF2 Fallback (100,000 iterations)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return kdf.derive(password_bytes)

    def encrypt_data(self, data: Any, master_password: Optional[str] = None) -> Dict[str, str]:
        """Encrypts arbitrary JSON-serializable data with AES-256-GCM."""
        pwd = master_password or self.get_or_create_master_key()
        key = self._derive_key(pwd)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(data).encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        return {
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8')
        }

    def decrypt_data(self, payload: Dict[str, str], master_password: Optional[str] = None) -> Any:
        """Decrypts an AES-256-GCM payload."""
        pwd = master_password or self.get_or_create_master_key()
        key = self._derive_key(pwd)
        aesgcm = AESGCM(key)
        nonce = base64.b64decode(payload["nonce"])
        ciphertext = base64.b64decode(payload["ciphertext"])
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode('utf-8'))

    # --- PII Field-Level Encryption ---
    def encrypt_field(self, value: str, master_password: Optional[str] = None) -> str:
        """Encrypts a single string field (e.g. phone number, salary) into a base64 string."""
        if not value:
            return ""
        payload = self.encrypt_data(value, master_password)
        return f"enc:{payload['nonce']}:{payload['ciphertext']}"

    def decrypt_field(self, enc_string: str, master_password: Optional[str] = None) -> str:
        """Decrypts a base64 field string."""
        if not enc_string or not enc_string.startswith("enc:"):
            return enc_string
        parts = enc_string.split(":")
        if len(parts) != 3:
            return enc_string
        payload = {"nonce": parts[1], "ciphertext": parts[2]}
        try:
            return str(self.decrypt_data(payload, master_password))
        except Exception:
            return "[ENCRYPTED]"

    # --- Full Secrets & Cookies Management ---
    def save_secrets(self, secrets: Dict[str, Any], master_password: Optional[str] = None):
        """Saves secrets dictionary to encrypted file."""
        payload = self.encrypt_data(secrets, master_password)
        with open(self.vault_path, "w") as f:
            json.dump(payload, f)

    def load_secrets(self, master_password: Optional[str] = None) -> Dict[str, Any]:
        """Loads and decrypts secrets dictionary."""
        if not self.vault_path.exists():
            return {}
        try:
            with open(self.vault_path, "r") as f:
                payload = json.load(f)
            return self.decrypt_data(payload, master_password)
        except Exception:
            return {}

    def save_platform_session(self, platform: str, session_data: Dict[str, Any], master_password: Optional[str] = None):
        """Saves platform cookies and storage state."""
        secrets = self.load_secrets(master_password)
        if "platform_sessions" not in secrets:
            secrets["platform_sessions"] = {}
        secrets["platform_sessions"][platform.lower()] = session_data
        self.save_secrets(secrets, master_password)

    def load_platform_session(self, platform: str, master_password: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Loads platform cookies and storage state."""
        secrets = self.load_secrets(master_password)
        return secrets.get("platform_sessions", {}).get(platform.lower())


cred_vault = CredentialVault()
