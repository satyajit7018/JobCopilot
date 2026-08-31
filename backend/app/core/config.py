"""
JobCopilot - Core Configuration & Local Path Setup
Backward-compatible re-exports backed by the centralized typed Settings engine.
"""

from pathlib import Path
from app.core.settings import settings

# Paths re-exported from settings
APP_DIR = settings.app_dir
DB_PATH = settings.db_path
VAULT_ENC_PATH = settings.vault_enc_path
PROFILES_DIR = settings.profiles_dir
RESUMES_DIR = settings.resumes_dir
DATA_DIR = settings.app_dir
BACKUPS_DIR = settings.backups_dir

# Default Application Settings
DEFAULT_MATCH_THRESHOLD = 0.60
DEFAULT_DAILY_CAP = 30
DEFAULT_FRESHNESS_DAYS = 30
DEFAULT_BUSINESS_HOURS = {"start": "08:30", "end": "17:30"}
DEFAULT_SUBMISSION_MODE = "FULL_AUTO"

API_PORT = settings.API_PORT
FRONTEND_PORT = settings.FRONTEND_PORT
CDP_PORT = settings.CDP_PORT
