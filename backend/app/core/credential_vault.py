"""
JobCopilot - AES-256 Encrypted Credential Vault
Stores sensitive logins and tokens locally encrypted with a master key.
"""

import os
import json
import base64
from typing import Dict, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from app.core.config import VAULT_ENC_PATH


class CredentialVault:
    def __init__(self, vault_path=VAULT_ENC_PATH):
        self.vault_path = vault_path
        self.salt = b"jobcopilot_local_salt_2026"

    def _derive_key(self, master_password: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
        )
        return kdf.derive(master_password.encode('utf-8'))

    def save_secrets(self, secrets: Dict[str, str], master_password: str = "default_local_master_key"):
        key = self._derive_key(master_password)
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        plaintext = json.dumps(secrets).encode('utf-8')
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        payload = {"nonce": base64.b64encode(nonce).decode('utf-8'), "ciphertext": base64.b64encode(ciphertext).decode('utf-8')}
        with open(self.vault_path, "w") as f:
            json.dump(payload, f)

    def load_secrets(self, master_password: str = "default_local_master_key") -> Dict[str, str]:
        if not self.vault_path.exists():
            return {}
        try:
            with open(self.vault_path, "r") as f:
                payload = json.load(f)
            key = self._derive_key(master_password)
            aesgcm = AESGCM(key)
            nonce = base64.b64decode(payload["nonce"])
            ciphertext = base64.b64decode(payload["ciphertext"])
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode('utf-8'))
        except Exception:
            return {}


cred_vault = CredentialVault()
