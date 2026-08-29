"""
JobCopilot - Core Configuration & Local Path Setup
Local-first, privacy-respecting storage paths and system settings.
"""

import os
from pathlib import Path

# Local-first user directory: ~/.jobcopilot/
APP_DIR = Path(os.path.expanduser("~/.jobcopilot"))
APP_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DIR / "jobcopilot.db"
VAULT_ENC_PATH = APP_DIR / "vault.enc"
PROFILES_DIR = APP_DIR / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)

RESUMES_DIR = APP_DIR / "resumes"
RESUMES_DIR.mkdir(parents=True, exist_ok=True)

LOGS_DIR = APP_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Default Application Settings
DEFAULT_MATCH_THRESHOLD = 0.60
DEFAULT_DAILY_CAP = 30
DEFAULT_FRESHNESS_DAYS = 30
DEFAULT_BUSINESS_HOURS = {"start": "08:30", "end": "17:30"}
DEFAULT_SUBMISSION_MODE = "FULL_AUTO"  # or "REVIEW_MODE"

API_PORT = 8000
FRONTEND_PORT = 5173
CDP_PORT = 9222
