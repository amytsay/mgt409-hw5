"""Safety guardrails for the agent team: loop and token limits, data masking, and output checks."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic_ai import UsageLimits

# ---------- loop + token limits (per TICKET: every agent on the ticket shares one usage counter) ----------
TICKET_LIMITS = UsageLimits(
    request_limit=40,          # model calls across all agents on one ticket
    tool_calls_limit=60,       # MCP + delegate tool calls across all agents on one ticket
    total_tokens_limit=300_000,
)
MAX_AGENT_RUNS = 10            # agent runs per ticket (Boss + every delegated run)
MAX_DEPTH = 3                  # Boss (0) -> specialist (1) -> specialist (2) -> specialist (3)
MAX_DELEGATIONS_PER_RUN = 4    # delegate() calls any single agent run may make
MAX_STEPS_PER_AGENT = 16       # agent-loop steps (model calls + tool rounds) per agent run
TICKET_TIMEOUT_S = 300         # wall-clock cap for one ticket
OUTPUT_RETRIES = 2             # times an agent may fix an answer that fails a check

BOSS_DISCOUNT_LIMIT_PCT = 15.0

# ---------- masking ----------
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CARD_OR_BANK = re.compile(r"\b\d(?:[ -]?\d){8,18}\b")   # card, bank account or routing numbers (9-19 digits)
_PHONE = re.compile(r"\(?\b\d{3}\)?[ .-]?\d{3}[ .-]\d{4}\b")


def initials(name: str) -> str:
    return " ".join(f"{p[0]}." for p in name.split() if p)


def mask_text(text: str, private_names: tuple[str, ...] = ()) -> str:
    """Mask private data before it is written anywhere (audit trail, logs)."""
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    text = _CARD_OR_BANK.sub(lambda m: "[acct ****" + re.sub(r"\D", "", m.group())[-4:] + "]", text)
    for name in private_names:   # full names first, then first names (see team.private_names_for)
        if name:
            text = re.sub(rf"\b{re.escape(name)}\b", initials(name), text, flags=re.IGNORECASE)
    return text


def short(value: Any, private_names: tuple[str, ...] = (), limit: int = 600) -> str:
    """Masked, length-capped string form of any value for the audit trail."""
    s = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    s = mask_text(s, private_names)
    return s if len(s) <= limit else s[:limit] + f"... [+{len(s) - limit} chars]"


# ---------- grounding: numbers must come from MCP tool results ----------
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_DOLLARS = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")


def norm(x: float | str) -> str:
    v = round(float(str(x).replace(",", "")), 2)
    return f"{v:.2f}".rstrip("0").rstrip(".")


def numbers_in(value: Any) -> set[str]:
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    out = set()
    for m in _NUM.findall(s):
        try:
            out.add(norm(m))
        except ValueError:
            pass
    return out


def unseen_dollar_amounts(text: str, seen: set[str]) -> list[str]:
    return [m for m in _DOLLARS.findall(text or "") if norm(m) not in seen]


# ---------- customer-facing privacy ----------
_INTERNAL = re.compile(
    r"\b(cash|balance|checking|bank|invoices?|landlord|rent|unit cost|margin|profit|vendors?|"
    r"Bulldog Print|Elm City|QuickShip|payments? data)\b", re.IGNORECASE)


def customer_message_problems(text: str | None, seen: set[str]) -> list[str]:
    """Reasons a customer-facing message is not allowed to go out (empty list = OK)."""
    if not text:
        return []
    problems = []
    hits = sorted({m.group(0).lower() for m in _INTERNAL.finditer(text)})
    if hits:
        problems.append(f"mentions internal-only information ({', '.join(hits)}); customers see products, sizes, "
                        "prices, timing and next steps only")
    if _EMAIL.search(text) or _CARD_OR_BANK.search(text):
        problems.append("contains an email address or account/card number")
    bad = unseen_dollar_amounts(text, seen)
    if bad:
        problems.append(f"quotes ${', $'.join(bad)}, which no MCP tool returned this run; quote only tool numbers")
    return problems
