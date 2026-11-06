"""Append-only audit trail: output/audit_trail.json (JSON Lines, one record per line).

Every agent-loop step on every ticket run is recorded:
    run_start     ticket, type, model, limits
    agent_start   which agent, depth, delegation chain, task
    model_text    text the model wrote (masked, length-capped)
    tool_call     MCP or delegate tool name + args
    tool_result   what the tool returned (masked, length-capped)
    retry         a tool or output check failed and the model was asked to fix it
    delegation    who handed what to whom (or why a delegation was refused)
    agent_output  the agent's structured answer (AgentReport / TicketResolution)
    agent_end     tokens and requests used so far, steps taken
    limit_hit / error / run_end   why the run stopped, totals, duration

Append-only: the file is only ever opened in "a" mode; nothing truncates, rewrites or deletes it.
Tamper-evident: each record carries prev_hash and hash = sha256(prev_hash + record JSON); `python audit.py verify`
re-checks the chain. Private data is masked before writing (customer names -> initials, emails, card/bank
numbers, phone numbers); payment accounts arrive already masked from the MCP server.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import settings
from guardrails import short

_lock = threading.Lock()

# Most fields are capped at 600 characters; an agent's final structured answer is kept whole so an auditor
# (and the dashboard's event feed) can read every fact, payment request and customer reply it produced.
FIELD_LIMITS = {"output": 12000}


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        return "genesis"
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 65536))
        lines = [ln for ln in f.read().decode("utf-8", "replace").splitlines() if ln.strip()]
    try:
        return json.loads(lines[-1]).get("hash", "genesis")
    except (IndexError, json.JSONDecodeError):
        return "genesis"


class AuditTrail:
    def __init__(self, path: Path = settings.AUDIT_PATH, private_names: tuple[str, ...] = ()):
        self.path = path
        self.private_names = private_names
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, *, run_id: str, ticket_id: int, agent: str | None = None, **fields: Any) -> None:
        body = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "ticket_id": ticket_id,
            "agent": agent,
            "event": event,
        }
        for k, v in fields.items():
            body[k] = (v if isinstance(v, (int, float, bool)) or v is None
                       else short(v, self.private_names, FIELD_LIMITS.get(k, 600)))
        with _lock:
            prev = _last_hash(self.path)
            body["prev_hash"] = prev
            body["hash"] = _hash(prev, body)
            with self.path.open("a", encoding="utf-8") as f:   # append only, never "w"
                f.write(json.dumps(body, ensure_ascii=False) + "\n")


def verify(path: Path = settings.AUDIT_PATH) -> tuple[int, list[int]]:
    """Re-check the hash chain. Returns (records, line numbers that fail)."""
    bad, prev, n = [], "genesis", 0
    if not path.is_file():
        return 0, []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        n += 1
        rec = json.loads(line)
        h = rec.pop("hash", None)
        if rec.get("prev_hash") != prev or _hash(prev, rec) != h:
            bad.append(i)
        prev = h
    return n, bad


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        n, bad = verify()
        print(f"{n} records; chain {'OK' if not bad else 'BROKEN at lines ' + str(bad)}")
    else:
        lines = settings.AUDIT_PATH.read_text(encoding="utf-8").splitlines() if settings.AUDIT_PATH.is_file() else []
        for ln in lines[-int(sys.argv[2] if len(sys.argv) > 2 else 20):]:
            print(ln)
