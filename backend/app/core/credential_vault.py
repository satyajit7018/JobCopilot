"""
JobCopilot - Argon2id & AES-256-GCM Cryptographic Credential & PII Vault
Envelope Encryption (DEK/KEK) with KMS Abstraction, Master Key Rotation,
and OS Keychain / Headless Fallback Integration.
"""

import os
import json
import base64
from typing import Dict, Optional, Any, List, Tuple
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
from cryptography.hazmat.primitives import hashes  # type: ignore
from app.core.config import VAULT_ENC_PATH, APP_DIR

try:
    import keyring  # type: ignore
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False

try:
    from argon2.low_level import hash_secret_raw, Type  # type: ignore
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False


# =============================================================================
# KMS Provider Interface & Local Implementation
# =============================================================================
class KMSProvider:
    """Abstract Key Management Service provider interface."""

    def get_key(self, version: Optional[str] = None) -> Tuple[str, str]:
        """Returns (version_id, key_str)."""
        raise NotImplementedError

    def rotate(self, new_key: Optional[str] = None) -> Tuple[str, str]:
        """Generates or sets a new master key version. Returns (new_version, new_key)."""
        raise NotImplementedError

    def list_versions(self) -> List[str]:
        """Lists available key versions."""
        raise NotImplementedError


class LocalKMSProvider(KMSProvider):
    """
    Local KMS provider managing versioned Master Keys (KEKs).
    Stores key metadata securely in OS Keychain or in protected local key store.
    """

    KEYRING_SERVICE = "JobCopilot_KMS"
    KEYSTORE_FILE = APP_DIR / ".kms_keystore.json"

    def __init__(self):
        self._keys: Dict[str, str] = {}
        self._current_version: str = "v1"
        self._load_keys()

    def _load_keys(self):
        """Loads versioned keys from environment, keystore file, or keyring."""
        # 1. Check keystore file
        if self.KEYSTORE_FILE.exists():
            try:
                with open(self.KEYSTORE_FILE, "r") as f:
                    data = json.load(f)
                    self._keys = data.get("keys", {})
                    self._current_version = data.get("current_version", "v1")
            except Exception:
                pass

        # 2. Check environment variable for initial seed
        env_key = os.getenv("JOBCOPILOT_MASTER_KEY")
        if env_key and "v1" not in self._keys:
            self._keys["v1"] = env_key

        # 3. Check OS Keyring for v1 if empty
        if not self._keys and HAS_KEYRING:
            try:
                stored_key = keyring.get_password("JobCopilot", "master_key")
                if stored_key:
                    self._keys["v1"] = stored_key
            except Exception:
                pass

        # 4. If still empty, initialize v1 key
        if not self._keys:
            v1_key = base64.b64encode(os.urandom(32)).decode("utf-8")
            self._keys["v1"] = v1_key
            self._current_version = "v1"
            self._save_keys()

    def _save_keys(self):
        """Persists keys to local storage file with restricted permissions."""
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "current_version": self._current_version,
                "keys": self._keys
            }
            with open(self.KEYSTORE_FILE, "w") as f:
                json.dump(payload, f)
            try:
                os.chmod(self.KEYSTORE_FILE, 0o600)
            except Exception:
                pass
        except Exception:
            pass

    def get_key(self, version: Optional[str] = None) -> Tuple[str, str]:
        ver = version or self._current_version
        if ver in self._keys:
            return ver, self._keys[ver]
        # Fallback to current version or any available key
        if self._current_version in self._keys:
            return self._current_version, self._keys[self._current_version]
        fallback_key = list(self._keys.values())[0] if self._keys else base64.b64encode(os.urandom(32)).decode("utf-8")
        return ver, fallback_key

    def rotate(self, new_key: Optional[str] = None) -> Tuple[str, str]:
        """Rotates to next master key version (e.g. v1 -> v2)."""
        curr_ver_num = 1
        try:
            curr_ver_num = int(self._current_version.replace("v", ""))
        except Exception:
            curr_ver_num = len(self._keys)
        next_ver = f"v{curr_ver_num + 1}"
        generated_key = new_key or base64.b64encode(os.urandom(32)).decode("utf-8")
        self._keys[next_ver] = generated_key
        self._current_version = next_ver
        self._save_keys()

        # Also mirror to OS Keyring if available
        if HAS_KEYRING:
            try:
                keyring.set_password(self.KEYRING_SERVICE, next_ver, generated_key)
                keyring.set_password("JobCopilot", "master_key", generated_key)
            except Exception:
                pass
        return next_ver, generated_key

    def list_versions(self) -> List[str]:
        return list(self._keys.keys())


# =============================================================================
# Credential Vault with Envelope Encryption
# =============================================================================
class CredentialVault:
    """
    Enterprise Encrypted Vault with Envelope Encryption (DEK encrypted under KEK),
    Key Rotation Procedure, and Argon2id / AES-256-GCM.
    """

    KEYRING_SERVICE = "JobCopilot"
    KEYRING_USERNAME = "master_key"

    def __init__(self, vault_path: Path = VAULT_ENC_PATH, kms_provider: Optional[KMSProvider] = None):
        self.vault_path = Path(vault_path)
        self.salt_path = APP_DIR / "vault.salt"
        self._key_cache: Dict[str, bytes] = {}
        self.kms = kms_provider or LocalKMSProvider()
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
        """Retrieves active master key from KMS provider."""
        _, key = self.kms.get_key()
        return key

    def _derive_key(self, master_password: str) -> bytes:
        """Derives a 256-bit key using Argon2id (or PBKDF2 as fallback) with memory caching."""
        if master_password in self._key_cache:
            return self._key_cache[master_password]

        password_bytes = master_password.encode('utf-8')
        derived: Optional[bytes] = None

        if HAS_ARGON2:
            try:
                derived = hash_secret_raw(
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

        if not derived:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=100000,
            )
            derived = kdf.derive(password_bytes)

        self._key_cache[master_password] = derived
        return derived

    # =========================================================================
    # Envelope Encryption Engine
    # =========================================================================
    def encrypt_envelope(self, plaintext_bytes: bytes, key_version: Optional[str] = None) -> str:
        """
        Envelope Encryption:
        1. Generate 256-bit ephemeral Data Encryption Key (DEK).
        2. Encrypt plaintext with DEK via AES-256-GCM.
        3. Encrypt DEK with Master Key (KEK) via AES-256-GCM.
        Returns formatted string: env:<version>:<wrapped_dek_b64>:<dek_nonce_b64>:<data_nonce_b64>:<data_ciphertext_b64>
        """
        ver, master_key = self.kms.get_key(key_version)
        kek = self._derive_key(master_key)

        # 1. Ephemeral DEK (32 bytes)
        dek = os.urandom(32)

        # 2. Encrypt plaintext with DEK
        aes_data = AESGCM(dek)
        data_nonce = os.urandom(12)
        data_ciphertext = aes_data.encrypt(data_nonce, plaintext_bytes, None)

        # 3. Encrypt DEK with KEK
        aes_kek = AESGCM(kek)
        dek_nonce = os.urandom(12)
        wrapped_dek = aes_kek.encrypt(dek_nonce, dek, None)

        return (
            f"env:{ver}:"
            f"{base64.b64encode(wrapped_dek).decode('utf-8')}:"
            f"{base64.b64encode(dek_nonce).decode('utf-8')}:"
            f"{base64.b64encode(data_nonce).decode('utf-8')}:"
            f"{base64.b64encode(data_ciphertext).decode('utf-8')}"
        )

    def decrypt_envelope(self, envelope_string: str) -> bytes:
        """
        Decrypts an envelope-encrypted payload.
        Unwraps the DEK using the corresponding KEK version, then decrypts data.
        """
        parts = envelope_string.split(":")
        if len(parts) != 6 or parts[0] != "env":
            raise ValueError("Invalid envelope encryption format.")

        _, ver, wrapped_dek_b64, dek_nonce_b64, data_nonce_b64, data_ciphertext_b64 = parts

        _, master_key = self.kms.get_key(ver)
        kek = self._derive_key(master_key)

        # 1. Unwrap DEK
        aes_kek = AESGCM(kek)
        dek_nonce = base64.b64decode(dek_nonce_b64)
        wrapped_dek = base64.b64decode(wrapped_dek_b64)
        dek = aes_kek.decrypt(dek_nonce, wrapped_dek, None)

        # 2. Decrypt data ciphertext
        aes_data = AESGCM(dek)
        data_nonce = base64.b64decode(data_nonce_b64)
        data_ciphertext = base64.b64decode(data_ciphertext_b64)
        return aes_data.decrypt(data_nonce, data_ciphertext, None)

    # --- PII Field-Level Encryption with Envelope Encryption ---
    def encrypt_field(self, value: str, master_password: Optional[str] = None) -> str:
        """Encrypts a string field using envelope encryption (or custom password fallback)."""
        if not value:
            return ""
        if master_password:
            # Explicit password fallback using standard AES-GCM
            payload = self.encrypt_data(value, master_password)
            return f"enc:{payload['nonce']}:{payload['ciphertext']}"

        return self.encrypt_envelope(value.encode('utf-8'))

    def decrypt_field(self, enc_string: str, master_password: Optional[str] = None) -> str:
        """
        Transparently decrypts both modern envelope ('env:') and legacy ('enc:') fields.
        """
        if not enc_string:
            return enc_string

        # Envelope encryption
        if enc_string.startswith("env:"):
            try:
                decrypted_bytes = self.decrypt_envelope(enc_string)
                return decrypted_bytes.decode('utf-8')
            except Exception:
                return "[ENCRYPTED]"

        # Legacy direct encryption
        if enc_string.startswith("enc:"):
            parts = enc_string.split(":")
            if len(parts) != 3:
                return enc_string
            payload = {"nonce": parts[1], "ciphertext": parts[2]}
            try:
                return str(self.decrypt_data(payload, master_password))
            except Exception:
                return "[ENCRYPTED]"

        return enc_string

    def encrypt(self, value: str, master_password: Optional[str] = None) -> str:
        """Alias for encrypt_field"""
        return self.encrypt_field(value, master_password)

    def decrypt(self, enc_string: str, master_password: Optional[str] = None) -> str:
        """Alias for decrypt_field"""
        return self.decrypt_field(enc_string, master_password)

    # --- Direct JSON AES-256-GCM Data Encryption (Legacy & Internal Vault) ---
    def encrypt_data(self, data: Any, master_password: Optional[str] = None) -> Dict[str, str]:
        """Encrypts arbitrary JSON data with AES-256-GCM."""
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

    # =========================================================================
    # Master Key Rotation Procedure
    # =========================================================================
    def rotate_master_key(self, new_master_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes Master Key Rotation:
        1. Generates/activates new version in KMS provider.
        2. Decrypts vault.enc secrets under old key and re-encrypts under new active key.
        3. Returns rotation summary metadata.
        """
        old_version = getattr(self.kms, "_current_version", "v1")
        old_secrets = self.load_secrets()

        new_version, active_key = self.kms.rotate(new_master_key)
        self._key_cache.clear()

        # Re-save vault secrets with newly active key
        if old_secrets:
            self.save_secrets(old_secrets)

        return {
            "status": "success",
            "previous_version": old_version,
            "active_version": new_version,
            "message": f"Master key successfully rotated from {old_version} to {new_version}"
        }

    def reencrypt_field_to_current_version(self, enc_string: str) -> str:
        """Re-encrypts a field under the current active master key version."""
        if not enc_string:
            return enc_string
        plaintext = self.decrypt_field(enc_string)
        if plaintext == "[ENCRYPTED]":
            return enc_string
        return self.encrypt_field(plaintext)

    # --- Secrets File Management ---
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

    def store_credential(self, service: str, cred_data: Any, master_password: Optional[str] = None):
        secrets = self.load_secrets(master_password)
        secrets[service] = cred_data
        self.save_secrets(secrets, master_password)

    def get_credential(self, service: str, master_password: Optional[str] = None) -> Optional[Any]:
        secrets = self.load_secrets(master_password)
        return secrets.get(service)

    def save_platform_session(self, platform: str, session_data: Dict[str, Any], master_password: Optional[str] = None):
        secrets = self.load_secrets(master_password)
        if "platform_sessions" not in secrets:
            secrets["platform_sessions"] = {}
        secrets["platform_sessions"][platform.lower()] = session_data
        self.save_secrets(secrets, master_password)

    def load_platform_session(self, platform: str, master_password: Optional[str] = None) -> Optional[Dict[str, Any]]:
        secrets = self.load_secrets(master_password)
        return secrets.get("platform_sessions", {}).get(platform.lower())


cred_vault = CredentialVault()
