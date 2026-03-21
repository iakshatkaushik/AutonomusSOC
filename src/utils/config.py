"""Configuration management — loads from .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Database — swap this one URL to move from SQLite to PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'processed' / 'autonomussoc.db'}")

# Data paths
RAW_DATA_DIR = PROJECT_ROOT / os.getenv("RAW_DATA_DIR", "data/raw/r4.2")
ANSWERS_DIR = PROJECT_ROOT / os.getenv("ANSWERS_DIR", "data/raw/answers")
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Ensure processed dir exists
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
