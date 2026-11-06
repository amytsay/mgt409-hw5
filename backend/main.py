"""Campus Customs backend (HW5 Problem 7): the FastAPI routes the React dashboard calls.

Run from backend/:
    uvicorn main:app --reload --port 8000
Then open http://localhost:8000 (route list) or http://localhost:8000/docs (try every route in the browser).

Routes
    GET  /api/health                         server up, model, shop today, which run is in progress
    GET  /api/tickets                        all 3 tickets with status (open / resolved) and last run
    GET  /api/tickets/{id}                   one ticket with its linked rows
    POST /api/tickets/{id}/run               run the agent team on a ticket (background; ?wait=true to block)
    GET  /api/runs  ·  GET /api/runs/{id}    run state and result (resolution, delegations, usage)
    GET  /api/events                         recent agent events from the audit trail (what agents said, tools used)
    GET  /api/approvals                      payments / purchases the agents prepared, waiting for a human
    POST /api/approvals/{id}/approve         human clicks Approve: the ONLY route that moves cash
    POST /api/approvals/{id}/reject          human clicks Reject: nothing is paid
    GET  /api/cash                           checking balance from cash_accounts, unpaid bills, recent payments
    POST /api/reset                          copy the original DB over the working DB for a fresh run

Data rules
- Every shop fact these routes return comes from the campus-customs MCP server (same tools the agents use).
  The single exception is the human approval write (approvals.py), which agents can't reach.
- The audit trail (output/audit_trail.json) is only appended to. Approvals and resets are recorded there too.
- Client names are masked to initials and payment accounts are masked (****king) in every response.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import settings  # first: puts hw5/ on sys.path, silences banners

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic import BaseModel, Field

import approvals
import guardrails as g
import shop_config
from audit import AuditTrail
from team import private_names_for, run_ticket

QUEUE_PATH = shop_config.OUTPUT_DIR / "approval_queue.json"   # pending human decisions (not the audit trail)
AUDIT = AuditTrail()


# ---------- a dedicated event loop for MCP + agents ----------

class ShopWorker:
    """Runs the MCP client and the agent team on their own event-loop thread.

    On Windows that loop is a ProactorEventLoop, which can start the MCP server subprocess even when
    `uvicorn --reload` runs the app on a SelectorEventLoop (which can't start subprocesses).
    """

    def __init__(self) -> None:
        self.loop = asyncio.ProactorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, name="shop-worker", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def call(self, coro):
        return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, self.loop))

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)


class ShopMCP:
    """The backend's own connection to the campus-customs MCP server (read routes + approval re-checks)."""

    def __init__(self, worker: ShopWorker) -> None:
        self.worker = worker
        self.client: Client | None = None

    def _new_client(self) -> Client:
        return Client(PythonStdioTransport(script_path=str(settings.MCP_SERVER_SCRIPT),
                                           python_cmd=sys.executable, cwd=str(settings.PROJECT_DIR)))

    async def _call(self, tool: str, args: dict) -> Any:
        if self.client is None or not self.client.is_connected():
            self.client = self._new_client()
            await self.client.__aenter__()
        res = await self.client.call_tool(tool, args, raise_on_error=False)
        if res.is_error:
            raise RuntimeError(f"MCP tool {tool} failed: {res.content[0].text if res.content else 'unknown error'}")
        if isinstance(res.structured_content, dict):
            sc = res.structured_content
            return sc["result"] if set(sc) == {"result"} else sc
        return json.loads(res.content[0].text)

    async def call(self, tool: str, **args: Any) -> Any:
        return await self.worker.call(self._call(tool, args))

    async def _close(self) -> None:
        if self.client is not None and self.client.is_connected():
            await self.client.__aexit__(None, None, None)
        self.client = None

    async def close(self) -> None:
        await self.worker.call(self._close())


worker: ShopWorker | None = None
mcp: ShopMCP | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global worker, mcp
    worker = ShopWorker()
    mcp = ShopMCP(worker)
    try:
        yield
    finally:
        try:
            await asyncio.wait_for(mcp.close(), 10)
        except Exception:  # noqa: BLE001 - shutting down anyway
            pass
        worker.stop()


app = FastAPI(
    title="Campus Customs desk API",
    description="Backend for the Campus Customs dashboard. Agents prepare; only a human approval moves cash.",
    version="1.0",
    lifespan=lifespan,
)
VITE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]   # the dashboard (npm run dev in frontend/)

app.add_middleware(  # let the browser page served by Vite call these routes
    CORSMiddleware,
    allow_origins=VITE_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",   # also Vite's fallback ports / vite preview
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------- helpers ----------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _initials(name: str) -> str:
    return " ".join(f"{p[0]}." for p in name.split() if p)


def _mask_ticket(t: dict) -> dict:
    """Customer and student-org names become initials; business counterparties (the landlord) stay."""
    t = dict(t)
    if private_names_for(t):
        t["requester"] = _initials(t["requester"])
    return t


async def _ticket_or_404(ticket_id: int) -> dict:
    data = await mcp.call("get_ticket", ticket_id=ticket_id)
    if "error" in data:
        raise HTTPException(404, data["error"])
    return data


# ---------- approval queue (output/approval_queue.json) ----------

_queue_lock = threading.Lock()
_PURCHASE = re.compile(r"(\d+)\s*(?:x|×|units? of)\s*(CC-[A-Z]+-[A-Z]+)\s+(?:size\s+)?([A-Z]{1,3})\b", re.I)


def _load_queue() -> list[dict]:
    if not QUEUE_PATH.is_file():
        return []
    return json.loads(QUEUE_PATH.read_text(encoding="utf-8") or "[]")


def _save_queue(items: list[dict]) -> None:
    QUEUE_PATH.write_text(json.dumps(items, indent=2), encoding="utf-8")


def _queue_id(p: dict) -> tuple[str, dict]:
    if p["kind"] != "purchase":
        return f"{p['kind']}-{p['ref_id']}", {}
    m = _PURCHASE.search(p.get("description") or "")
    if not m:
        return f"purchase-{p['ref_id']}-{g.norm(p['amount'])}", {"sku": None, "size": None, "qty": None}
    qty, sku, size = int(m.group(1)), m.group(2).upper(), m.group(3).upper()
    return f"purchase-{p['ref_id']}-{sku}-{size}-{qty}", {"sku": sku, "size": size, "qty": qty}


def _enqueue(result: dict) -> int:
    """Queue every payment the Boss put in the resolution (or the specialists' drafts if the run stopped early)."""
    res = result.get("resolution")
    if res:
        requests, source = res.get("payment_requests", []), "boss_resolution"
    else:
        requests, source = [p for r in result.get("reports", []) for p in r.get("payment_requests", [])], "specialist_report"
    added = 0
    with _queue_lock:
        items = _load_queue()
        by_id = {i["id"]: i for i in items}
        for p in requests:
            qid, extra = _queue_id(p)
            if qid in by_id and by_id[qid]["status"] != "pending":
                continue  # already approved or rejected: never re-queue a decided payment
            entry = {
                "id": qid, "status": "pending", "kind": p["kind"], "ref_id": p["ref_id"], "payee": p["payee"],
                "amount": p["amount"], "description": p.get("description"), "due_date": p.get("due_date"),
                "overdue": p.get("overdue", False), "low_cash_flag": p.get("low_cash_flag", False),
                "priority": p.get("priority", "normal"), "reason": p.get("reason"), **extra,
                "ticket_id": result["ticket_id"], "run_id": result["run_id"], "source": source, "queued_at": _now(),
            }
            if qid in by_id:
                old = by_id[qid]
                if old.get("ticket_id") != entry["ticket_id"]:
                    # Same bill flagged again by another ticket: it stays one queue item (no double payment),
                    # keeps the ticket that first raised it, and records the other ticket.
                    also = set(old.get("also_requested_by", [])) | {entry["ticket_id"]}
                    for k in ("ticket_id", "run_id", "queued_at", "reason"):
                        entry[k] = old.get(k, entry[k])
                    entry["also_requested_by"] = sorted(also)
                old.update(entry)
            else:
                items.append(entry)
                by_id[qid] = entry
                added += 1
        _save_queue(items)
    return added


# ---------- runs ----------

RUNS: dict[int, dict] = {}
_active: dict[str, Any] = {"ticket_id": None}
_tasks: set[asyncio.Task] = set()


async def _run_job(ticket_id: int) -> None:
    state = RUNS[ticket_id]
    try:
        result = await worker.call(run_ticket(ticket_id))
        queued = _enqueue(result)
        # The dashboard is a screen anyone nearby can see: customer names become initials there too.
        ticket = (await mcp.call("get_ticket", ticket_id=ticket_id))["ticket"]
        result = json.loads(g.mask_text(json.dumps(result, default=str), private_names_for(ticket)))
        state.update(status="done", finished_at=_now(), result=result, queued_for_approval=queued,
                     run_id=result["run_id"], stop_reason=result["stop_reason"],
                     final_status=(result.get("resolution") or {}).get("status"))
    except Exception as e:  # noqa: BLE001 - reported to the dashboard
        state.update(status="error", finished_at=_now(), error=f"{type(e).__name__}: {e}")
    finally:
        state["duration_s"] = round(time.monotonic() - state.pop("_t0", time.monotonic()), 1)
        _active["ticket_id"] = None


def _public_run(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("_")}


# ---------- routes ----------

@app.get("/", include_in_schema=False)
async def index() -> dict:
    return {"app": "Campus Customs desk API", "docs": "/docs",
            "routes": sorted({f"{', '.join(sorted(r.methods - {'HEAD'}))} {r.path}" for r in app.routes
                              if getattr(r, "include_in_schema", False)})}


@app.get("/api/health", summary="Server status")
async def health() -> dict:
    tickets = await mcp.call("list_tickets", status="all")
    return {"ok": True, "model": settings.MODEL_NAME, "shop_today": tickets["today"],
            "database": shop_config.WORKING_DB_PATH.name, "running_ticket": _active["ticket_id"]}


@app.get("/api/tickets", summary="All tickets and whether each is open or resolved")
async def list_tickets() -> dict:
    data = await mcp.call("list_tickets", status="all")
    tickets = []
    for t in data["tickets"]:
        run = RUNS.get(t["id"])
        tickets.append({**_mask_ticket(t),
                        "last_run": {k: run.get(k) for k in ("status", "run_id", "stop_reason", "final_status",
                                                              "started_at", "finished_at")} if run else None})
    return {"today": data["today"], "tickets": tickets,
            "counts": {s: sum(t["status"] == s for t in tickets) for s in ("open", "resolved")}}


@app.get("/api/tickets/{ticket_id}", summary="One ticket with its linked inventory, pricing, lease and invoice")
async def get_ticket(ticket_id: int) -> dict:
    data = await _ticket_or_404(ticket_id)
    return {**data, "ticket": _mask_ticket(data["ticket"])}


@app.post("/api/tickets/{ticket_id}/run", status_code=202, summary="Run the agent team on one ticket")
async def run_team(ticket_id: int, wait: bool = Query(False, description="Block until the run finishes")) -> dict:
    await _ticket_or_404(ticket_id)
    if _active["ticket_id"] is not None:
        raise HTTPException(409, f"The team is already working ticket {_active['ticket_id']}. Wait for it to finish.")
    _active["ticket_id"] = ticket_id
    RUNS[ticket_id] = {"ticket_id": ticket_id, "status": "running", "started_at": _now(), "_t0": time.monotonic()}
    task = asyncio.create_task(_run_job(ticket_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    if wait:
        await task
    return _public_run(RUNS[ticket_id])


@app.get("/api/runs", summary="State of every run since the server started")
async def list_runs() -> dict:
    return {"running_ticket": _active["ticket_id"],
            "runs": [{k: v for k, v in _public_run(s).items() if k != "result"} for s in RUNS.values()]}


@app.get("/api/runs/{ticket_id}", summary="Latest run for a ticket: status, resolution, delegations, usage")
async def get_run(ticket_id: int) -> dict:
    if ticket_id not in RUNS:
        raise HTTPException(404, f"No run for ticket {ticket_id} since the server started.")
    return _public_run(RUNS[ticket_id])


_EVENT_TYPES = {"run_start", "agent_start", "delegation", "tool_call", "tool_result", "model_text", "retry",
                "agent_output", "limit_hit", "error", "run_end", "human_approval", "human_rejection", "db_reset"}


def _event_text(r: dict) -> str:
    e = r["event"]
    if e == "run_start":
        return f"Run started on ticket {r['ticket_id']} ({r.get('ticket_type')}) with {r.get('model')}"
    if e == "agent_start":
        return f"{r['agent']} started: {r.get('task', '')}"
    if e == "delegation":
        if r.get("ok") is False:
            return f"{r['agent']} -> {r.get('to_agent')} refused: {r.get('refused')}"
        return f"{r['agent']} -> {r.get('to_agent')}: {r.get('task', '')}"
    if e == "tool_call":
        return f"{r['agent']} called {r.get('tool')}({r.get('args', '')})"
    if e == "tool_result":
        return f"{r.get('tool')} returned {r.get('result', '')}"
    if e == "model_text":
        return r.get("text", "")
    if e == "retry":
        return f"Retry ({r.get('tool')}): {r.get('reason', '')}"
    if e == "agent_output":
        try:
            out = json.loads(r.get("output", ""))
        except (TypeError, json.JSONDecodeError):   # records written before outputs were kept whole
            raw = str(r.get("output", ""))
            m = re.search(r'"(?:outcome|summary)":\s*"((?:[^"\\]|\\.)*)', raw)
            status = re.search(r'"status":\s*"(\w+)"', raw)
            if m:
                return (f"[{status.group(1)}] " if status and '"outcome"' in raw else "") + m.group(1)
            return raw[:600]
        if "outcome" in out:
            return f"[{out.get('status')}] {out['outcome']}"
        return out.get("summary", "")
    if e in ("limit_hit", "error"):
        return f"{r.get('stop_reason') or r.get('limit')}: {r.get('detail', '')}"
    if e == "run_end":
        return (f"Run ended ({r.get('stop_reason')}), status {r.get('final_status')}, {r.get('agent_runs')} agent runs, "
                f"{r.get('requests')} model calls, {r.get('duration_s')}s")
    return r.get("note", e)


@app.get("/api/events", summary="Recent agent events: what each agent said and which tools it used")
async def events(ticket_id: int | None = None, run_id: str | None = None,
                 after: int = Query(0, description="Only events after this seq (for polling)"),
                 limit: int = Query(100, ge=1, le=1000), verbose: bool = False) -> dict:
    lines = settings.AUDIT_PATH.read_text(encoding="utf-8").splitlines() if settings.AUDIT_PATH.is_file() else []
    out = []
    for seq, line in enumerate(lines, 1):
        if seq <= after or not line.strip():
            continue
        r = json.loads(line)
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        if run_id and r.get("run_id") != run_id:
            continue
        if not verbose and r["event"] not in _EVENT_TYPES:
            continue
        ev = {"seq": seq, "ts": r["ts"], "run_id": r["run_id"], "ticket_id": r["ticket_id"], "agent": r["agent"],
              "event": r["event"], "text": _event_text(r)}
        for k in ("tool", "to_agent", "ok", "stop_reason", "final_status"):
            if k in r:
                ev[k] = r[k]
        out.append(ev)
    out = out[-limit:]
    return {"events": out, "last_seq": len(lines), "running_ticket": _active["ticket_id"]}


@app.get("/api/approvals", summary="Payments and purchases the agents prepared, waiting for a human")
async def list_approvals(status: str = Query("all", pattern="^(all|pending|approved|rejected)$")) -> dict:
    items = _load_queue()
    if status != "all":
        items = [i for i in items if i["status"] == status]
    pending = [i for i in _load_queue() if i["status"] == "pending"]
    return {"items": items, "pending_count": len(pending),
            "pending_total": round(sum(i["amount"] for i in pending), 2)}


class Decision(BaseModel):
    approved_by: str = Field("Owner", min_length=1, max_length=60, description="Who clicked (stored; shown as initials)")
    note: str | None = Field(None, max_length=300)


def _find(item_id: str) -> tuple[list[dict], dict]:
    items = _load_queue()
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        raise HTTPException(404, f"No queued payment {item_id!r}.")
    if item["status"] != "pending":
        raise HTTPException(409, f"{item_id} is already {item['status']}.")
    return items, item


@app.post("/api/approvals/{item_id}/approve", summary="Human approves one payment or purchase (moves cash)")
async def approve(item_id: str, body: Decision | None = None) -> dict:
    body = body or Decision()
    if _active["ticket_id"] is not None:
        raise HTTPException(409, "Wait for the running ticket to finish before approving payments.")
    with _queue_lock:
        items, item = _find(item_id)

    # Re-prepare through MCP right now: the amount, payee and paid/duplicate checks come from the DB, not the queue.
    if item["kind"] == "purchase":
        if not (item.get("sku") and item.get("size") and item.get("qty")):
            raise HTTPException(422, "This purchase has no SKU/size/qty; ask the team to prepare it again.")
        fresh = await mcp.call("prepare_restock_order", sku=item["sku"], size=item["size"], qty=item["qty"],
                               vendor_id=item["ref_id"])
        draft = fresh.get("purchase_draft")
        if fresh.get("duplicate_warning"):
            raise HTTPException(409, fresh["duplicate_warning"])
    else:
        fresh = await mcp.call("prepare_payment", kind=item["kind"], ref_id=item["ref_id"])
        draft = fresh.get("payment_draft")
    if "error" in fresh or draft is None:
        raise HTTPException(409, fresh.get("error", "Could not re-prepare this payment."))
    if not fresh.get("payable", False):
        raise HTTPException(409, fresh.get("not_payable_reason") or "Not payable (insufficient funds).")
    if g.norm(draft["amount"]) != g.norm(item["amount"]):
        raise HTTPException(409, f"Amount changed: queued ${item['amount']:,.2f}, database says ${draft['amount']:,.2f}.")

    try:
        payment = approvals.record_payment(item["kind"], item["ref_id"], float(draft["amount"]), body.approved_by)
    except approvals.ApprovalError as e:
        raise HTTPException(409, str(e)) from e

    with _queue_lock:
        items = _load_queue()
        for i in items:
            if i["id"] == item_id:
                i.update(status="approved", decided_at=_now(), decided_by=_initials(body.approved_by),
                         payment_id=payment["payment_id"], note=body.note)
                item = i
        _save_queue(items)
    AUDIT.record("human_approval", run_id="human", ticket_id=item["ticket_id"], agent="human",
                 approval_id=item_id, kind=item["kind"], ref_id=item["ref_id"], payee=item["payee"],
                 amount=payment["amount"], payment_id=payment["payment_id"],
                 balance_before=payment["balance_before"], balance_after=payment["balance_after"],
                 approved_by=_initials(body.approved_by), low_cash_flag=bool(fresh.get("low_cash_flag")),
                 note=f"Human approved {item['kind']} {item_id} ${payment['amount']:,.2f} to {item['payee']}")
    cash = await mcp.call("get_cash_position")
    return {"approved": item, "payment": payment,
            "warning": fresh.get("low_cash_reason") if fresh.get("low_cash_flag") else None,
            "cash": {"account": cash["account"], "balance": cash["balance"], "total_owed": cash["total_owed"]}}


@app.post("/api/approvals/{item_id}/reject", summary="Human rejects one payment or purchase (nothing is paid)")
async def reject(item_id: str, body: Decision | None = None) -> dict:
    body = body or Decision()
    with _queue_lock:
        items, item = _find(item_id)
        item.update(status="rejected", decided_at=_now(), decided_by=_initials(body.approved_by), note=body.note)
        _save_queue(items)
    AUDIT.record("human_rejection", run_id="human", ticket_id=item["ticket_id"], agent="human",
                 approval_id=item_id, amount=item["amount"], payee=item["payee"], by=_initials(body.approved_by),
                 note=f"Human rejected {item_id}" + (f": {body.note}" if body.note else ""))
    return {"rejected": item}


@app.get("/api/cash", summary="Checking balance (cash_accounts), unpaid bills and recent payments")
async def cash() -> dict:
    return await mcp.call("get_cash_position")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@app.post("/api/reset", summary="Reset the working database to the original for a fresh run")
async def reset() -> dict:
    if _active["ticket_id"] is not None:
        raise HTTPException(409, f"Ticket {_active['ticket_id']} is running. Reset after it finishes.")
    before = _sha(shop_config.WORKING_DB_PATH)
    shutil.copyfile(shop_config.ORIGINAL_DB_PATH, shop_config.WORKING_DB_PATH)
    after = _sha(shop_config.WORKING_DB_PATH)
    if after != _sha(shop_config.ORIGINAL_DB_PATH):
        raise HTTPException(500, "Reset copy did not match the original database.")
    with _queue_lock:
        cleared = len(_load_queue())
        _save_queue([])
    RUNS.clear()
    AUDIT.record("db_reset", run_id="human", ticket_id=0, agent="human", db_sha_before=before, db_sha_after=after,
                 cleared_queue_items=cleared,
                 note="Working DB reset to the original. The audit trail is kept (append-only).")
    tickets = await mcp.call("list_tickets", status="all")
    cash_now = await mcp.call("get_cash_position")
    return {"reset": True, "database": shop_config.WORKING_DB_PATH.name, "copied_from": shop_config.ORIGINAL_DB_PATH.name,
            "cleared_queue_items": cleared, "balance": cash_now["balance"],
            "tickets": [{"id": t["id"], "status": t["status"]} for t in tickets["tickets"]],
            "audit_trail": "kept (append-only)"}
