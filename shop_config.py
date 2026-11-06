"""Shared settings for Campus Customs (HW5). The ONLY place that names the databases and the model.

Both the MCP server (mcp_server/) and the FastAPI backend (backend/) import this module, so they
always read and write the same working copy: data/campus_customs_new.db.
data/campus_customs.db is the untouched original; it is only ever read to reset the working copy.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
ORIGINAL_DB_PATH = DATA_DIR / "campus_customs.db"      # original shop database: never modified
WORKING_DB_PATH = DATA_DIR / "campus_customs_new.db"   # working copy used by MCP server + backend
OUTPUT_DIR = PROJECT_DIR / "output"

# Load the nearest .env: hw5/, then the folders above (e.g. the shared class-folder .env).
for folder in (PROJECT_DIR, *PROJECT_DIR.parents):
    if (folder / ".env").is_file():
        load_dotenv(folder / ".env")
        break

# Every agent runs on gpt-6-luna through Portkey, and only that model.
REQUIRED_MODEL = "gpt-6-luna"
MODEL_NAME = os.getenv("OPENAI_MODEL", REQUIRED_MODEL)
if MODEL_NAME != REQUIRED_MODEL:
    raise RuntimeError(
        f"OPENAI_MODEL is set to {MODEL_NAME!r}; this project only allows {REQUIRED_MODEL!r} for every agent."
    )
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")


def portkey_api_key() -> str:
    """Return PORTKEY_API_KEY from the environment (never logged or printed)."""
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to .env (see .env.example).")
    return key


def connect(readonly: bool = False) -> sqlite3.Connection:
    """Open the working copy (read-only when asked). Fails loudly if it has not been created yet."""
    if not WORKING_DB_PATH.is_file():
        raise FileNotFoundError(
            f"{WORKING_DB_PATH} is missing. Copy {ORIGINAL_DB_PATH.name} to {WORKING_DB_PATH.name} first."
        )
    if readonly:
        con = sqlite3.connect(f"{WORKING_DB_PATH.as_uri()}?mode=ro", uri=True)
    else:
        con = sqlite3.connect(WORKING_DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def shop_today() -> date:
    """The shop's "today" is desk.date_today in the working DB, never the computer's clock."""
    with closing(connect(readonly=True)) as con:
        row = con.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def is_overdue(due_date: str, today: date | None = None) -> bool:
    """A bill is overdue when its due date is strictly before the shop's today."""
    return date.fromisoformat(due_date) < (today or shop_today())
