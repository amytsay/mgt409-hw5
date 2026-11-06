"""Backend settings: re-exports the project-wide shop_config (DB paths, model, Portkey) plus backend paths.

shop_config.py (hw5/) is the ONE place that names the working DB and the model, shared with the MCP server.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(PROJECT_DIR))

import shop_config  # noqa: E402

PROMPTS_DIR = BACKEND_DIR / "prompts"
MCP_SERVER_SCRIPT = PROJECT_DIR / "mcp_server" / "server.py"
AUDIT_PATH = shop_config.OUTPUT_DIR / "audit_trail.json"
MODEL_NAME = shop_config.MODEL_NAME          # always gpt-6-luna (shop_config refuses anything else)
PORTKEY_BASE_URL = shop_config.PORTKEY_BASE_URL
portkey_api_key = shop_config.portkey_api_key
