"""Campus Customs MCP server (FastMCP). Every agent gets shop facts only through these tools.

Database: data/campus_customs_new.db, the working copy, found through shop_config.py.
Read tools open the DB read-only. The ONE write tool is set_ticket_status (tickets.status only; Boss only).
No tool moves money or changes stock: payments and restock purchases are only *prepared*, and a human
approves them through the backend's approve-payment route (Problem 7). Payment data is masked
(approver names -> initials, account identifiers shortened).

Run (stdio, for a vibe coder or the agents):  python mcp_server/server.py
"""

from __future__ import annotations

import sys
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make hw5/shop_config.py importable
import shop_config  # noqa: E402

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Campus Customs shop tools. 'Today' is desk.date_today, not the real clock. All facts come from "
        "data/campus_customs_new.db. Payments and purchases are prepared for human approval, never paid. "
        "Only set_ticket_status writes, and only to tickets.status."
    ),
)

APPROVAL_NOTE = "Prepared only. No money has moved. A human must approve this before cash changes."


# ---------- helpers ----------

def _db(readonly: bool = True):
    return closing(shop_config.connect(readonly=readonly))


def _today(con) -> date:
    return date.fromisoformat(con.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"])


def _money(x: float) -> float:
    return round(float(x), 2)


def _due_info(due: str, today: date) -> dict:
    days = (date.fromisoformat(due) - today).days
    return {"due_date": due, "overdue": days < 0, "days_overdue": max(0, -days), "days_until_due": max(0, days)}


def _initials(name: str | None) -> str | None:
    if not name:
        return name
    return " ".join(f"{p[0]}." for p in name.split() if p)


def _mask_account(name: str) -> str:
    """Account identifiers are never shown in full: 'checking' -> '****king'."""
    return "****" + name[-4:] if len(name) > 4 else "****"


def _mask_payment(row: dict) -> dict:
    out = dict(row)
    out["approved_by"] = _initials(out.get("approved_by"))
    out["account"] = _mask_account(out["account"]) if out.get("account") else out.get("account")
    return out


def _one_month_before(d: date) -> date:
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    for day in (d.day, 30, 29, 28):  # clamp e.g. Mar 31 -> Feb 28
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def _rent_paid_this_cycle(con, lease) -> list[dict]:
    """Rent payments for this lease on or after the start of the current rent cycle."""
    cycle_start = _one_month_before(date.fromisoformat(lease["next_due"])).isoformat()
    rows = con.execute(
        "SELECT * FROM payments WHERE kind = 'rent' AND ref_id = ? AND substr(paid_at, 1, 10) >= ?",
        (lease["id"], cycle_start),
    ).fetchall()
    return [dict(r) for r in rows]


def _unpaid_bills(con, today: date) -> list[dict]:
    """Every bill still owed: open invoices with no payment, plus lease rent not paid this cycle."""
    bills = []
    for inv in con.execute(
        "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
        "WHERE i.status = 'open' AND NOT EXISTS "
        "(SELECT 1 FROM payments p WHERE p.kind = 'invoice' AND p.ref_id = i.id)"
    ):
        bills.append({"kind": "invoice", "ref_id": inv["id"], "payee": inv["vendor_name"],
                      "description": inv["description"], "amount": _money(inv["amount"]),
                      **_due_info(inv["due_date"], today)})
    for lease in con.execute("SELECT * FROM leases"):
        if not _rent_paid_this_cycle(con, lease):
            bills.append({"kind": "rent", "ref_id": lease["id"], "payee": lease["landlord"],
                          "description": f"Monthly rent, {lease['space_name']}",
                          "amount": _money(lease["monthly_rent"]), **_due_info(lease["next_due"], today)})
    return bills


def _cash_check(con, today: date, amount: float, account: str, exclude: tuple[str, int] | None) -> dict:
    """Balance before/after, the other unpaid bills, and the low-cash flag, for a prepared payment."""
    acct = con.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if acct is None:
        return {"error": f"Unknown cash account {account!r}.",
                "accounts": [_mask_account(r["name"]) for r in con.execute("SELECT name FROM cash_accounts")]}
    balance = acct["balance"]
    after = balance - amount
    others = [b for b in _unpaid_bills(con, today) if exclude is None or (b["kind"], b["ref_id"]) != exclude]
    others_total = sum(b["amount"] for b in others)
    can_cover = after >= 0
    low_cash = can_cover and after < others_total
    return {
        "can_cover": can_cover,
        "cash_balance": _money(balance),
        "balance_after_payment": _money(after),
        "other_unpaid_bills": others,
        "other_unpaid_total": _money(others_total),
        "low_cash_flag": low_cash or not can_cover,
        "low_cash_reason": (
            "Insufficient funds for this payment." if not can_cover else
            f"After this payment ${_money(after):,.2f} would not cover the other unpaid bills "
            f"(${_money(others_total):,.2f})." if low_cash else None
        ),
    }


def _restock_invoices(con, today: date, sku: str, size: str) -> list[dict]:
    """Open invoices whose description names this SKU and size (e.g. 'Rush reprint CC-TEE-WHITE S')."""
    found = []
    for inv in con.execute(
        "SELECT i.*, v.name AS vendor_name, v.specialty, v.lead_days "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"
    ):
        words = (inv["description"] or "").split()
        if sku in words and size in words:
            found.append({
                "invoice_id": inv["id"], "description": inv["description"],
                "vendor_id": inv["vendor_id"], "vendor": inv["vendor_name"], "specialty": inv["specialty"],
                "lead_days": inv["lead_days"], "amount": _money(inv["amount"]),
                **_due_info(inv["due_date"], today),
                "earliest_arrival_if_released_today": (today + timedelta(days=inv["lead_days"])).isoformat(),
            })
    return found


# ---------- tickets ----------

@mcp.tool
def list_tickets(status: Literal["open", "resolved", "all"] = "open") -> dict:
    """List desk tickets (id, type, requester, subject, status, created_at). Default: open tickets only."""
    with _db() as con:
        today = _today(con)
        sql = "SELECT id, type, requester, subject, status, created_at FROM tickets"
        rows = con.execute(sql + ("" if status == "all" else " WHERE status = ?") + " ORDER BY id",
                           () if status == "all" else (status,)).fetchall()
    return {"today": today.isoformat(), "status_filter": status, "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """One ticket with every row it links to: the inventory rows and pricing for its SKU, the lease
    (lease_id), and the invoice and its vendor (invoice_id), with due and overdue status on the shop's today.
    Start here for any ticket."""
    with _db() as con:
        today = _today(con)
        t = con.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if t is None:
            return {"error": f"No ticket {ticket_id}.",
                    "ticket_ids": [r["id"] for r in con.execute("SELECT id FROM tickets ORDER BY id")]}
        out: dict = {"today": today.isoformat(), "ticket": dict(t), "linked": {}}
        if t["sku"]:
            inv = con.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY rowid", (t["sku"],)).fetchall()
            p = con.execute("SELECT * FROM pricing WHERE sku = ?", (t["sku"],)).fetchone()
            out["linked"]["inventory"] = [dict(r) for r in inv]
            out["linked"]["pricing"] = dict(p) if p else None
        if t["lease_id"] is not None:
            lease = con.execute("SELECT * FROM leases WHERE id = ?", (t["lease_id"],)).fetchone()
            out["linked"]["lease"] = {**dict(lease), **_due_info(lease["next_due"], today)} if lease else None
        if t["invoice_id"] is not None:
            i = con.execute("SELECT * FROM invoices WHERE id = ?", (t["invoice_id"],)).fetchone()
            if i:
                v = con.execute("SELECT * FROM vendors WHERE id = ?", (i["vendor_id"],)).fetchone()
                out["linked"]["invoice"] = {**dict(i), **_due_info(i["due_date"], today)}
                out["linked"]["vendor"] = dict(v) if v else None
    return out


@mcp.tool
def set_ticket_status(ticket_id: int, status: Literal["open", "resolved"]) -> dict:
    """BOSS ONLY. Set a ticket's status ('resolved' when its work is done or handed to a human for approval).
    Changes tickets.status only; never touches cash, stock, invoices or leases."""
    with _db(readonly=False) as con:
        row = con.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"error": f"No ticket {ticket_id}."}
        con.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        con.commit()
    return {"ticket_id": ticket_id, "previous_status": row["status"], "status": status}


# ---------- inventory / order fulfillment ----------

@mcp.tool
def check_stock_for_order(sku: str, size: str, qty: int) -> dict:
    """Can the shop fill an order for `qty` units of `sku` in `size` from stock today?

    Returns on-hand qty and aisle, the shortfall, the other sizes on hand for the same SKU, the list price and
    order total, any OPEN vendor invoice already covering a restock of this SKU and size (with its vendor, lead
    time and overdue status), and every vendor's earliest arrival date counted from the shop's today.
    Read-only: it never changes stock or places an order.
    """
    with _db() as con:
        today = _today(con)
        rows = con.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY rowid", (sku,)).fetchall()
        if not rows:
            skus = [r["sku"] for r in con.execute("SELECT DISTINCT sku FROM inventory")]
            return {"error": f"Unknown SKU {sku!r}.", "known_skus": skus}
        item = next((r for r in rows if r["size"] == size), None)
        if item is None:
            return {"error": f"{sku} has no size {size!r}.", "sizes": [r["size"] for r in rows]}

        price = con.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        on_hand = item["qty"]
        shortfall = max(0, qty - on_hand)
        restock_invoices = _restock_invoices(con, today, sku, size)
        vendors = [
            {"vendor_id": v["id"], "vendor": v["name"], "specialty": v["specialty"], "lead_days": v["lead_days"],
             "earliest_arrival": (today + timedelta(days=v["lead_days"])).isoformat()}
            for v in con.execute("SELECT * FROM vendors ORDER BY id")
        ]

    return {
        "today": today.isoformat(),
        "sku": sku, "name": item["name"], "size": size, "location": item["location"],
        "requested_qty": qty, "on_hand": on_hand,
        "can_fill_from_stock": shortfall == 0, "shortfall": shortfall,
        "other_sizes_on_hand": {r["size"]: r["qty"] for r in rows if r["size"] != size},
        "list_price": _money(price["list_price"]) if price else None,
        "order_total_at_list": _money(price["list_price"] * qty) if price else None,
        "open_restock_invoices": restock_invoices,
        "vendors": vendors,
    }


@mcp.tool
def get_inventory_report(sku: str | None = None) -> dict:
    """Stock audit: every inventory row (or one SKU) with qty, aisle, unit cost and list price, plus
    out-of-stock rows, units on hand and stock value at cost and at list."""
    with _db() as con:
        today = _today(con)
        sql = ("SELECT i.*, p.unit_cost, p.list_price FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku"
               + (" WHERE i.sku = ?" if sku else "") + " ORDER BY i.sku, i.rowid")
        rows = [dict(r) for r in con.execute(sql, (sku,) if sku else ())]
    if not rows:
        return {"error": f"Unknown SKU {sku!r}."}
    return {
        "today": today.isoformat(),
        "rows": rows,
        "out_of_stock": [{"sku": r["sku"], "name": r["name"], "size": r["size"]} for r in rows if r["qty"] <= 0],
        "units_on_hand": sum(r["qty"] for r in rows),
        "stock_value_at_cost": _money(sum(r["qty"] * (r["unit_cost"] or 0) for r in rows)),
        "stock_value_at_list": _money(sum(r["qty"] * (r["list_price"] or 0) for r in rows)),
    }


@mcp.tool
def prepare_restock_order(sku: str, size: str, qty: int, vendor_id: int, account: str = "checking") -> dict:
    """Prepare (do NOT place) a restock purchase of `qty` units of `sku`/`size` from a vendor, for human approval.

    Cost = qty x pricing.unit_cost. Returns the vendor's specialty and lead time, the arrival date counted from
    the shop's today, any open invoice ALREADY covering this SKU and size (so the shop doesn't order twice), and
    the cash check (balance before and after, other unpaid bills, low-cash flag). Read-only.
    """
    if qty <= 0:
        return {"error": "qty must be at least 1."}
    with _db() as con:
        today = _today(con)
        item = con.execute("SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            return {"error": f"No inventory row for {sku} size {size!r}."}
        p = con.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        v = con.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if v is None:
            return {"error": f"No vendor {vendor_id}.",
                    "vendors": [dict(r) for r in con.execute("SELECT * FROM vendors ORDER BY id")]}
        amount = qty * p["unit_cost"]
        existing = _restock_invoices(con, today, sku, size)
        cash = _cash_check(con, today, amount, account, exclude=None)
    if "error" in cash:
        return cash
    return {
        "today": today.isoformat(),
        "purchase_draft": {"kind": "purchase", "ref_id": vendor_id, "payee": v["name"],
                           "description": f"Restock {qty} x {sku} {size}", "amount": _money(amount),
                           "account": _mask_account(account)},
        "item": {"sku": sku, "name": item["name"], "size": size, "on_hand": item["qty"],
                 "unit_cost": _money(p["unit_cost"]), "list_price": _money(p["list_price"])},
        "vendor": {"vendor_id": v["id"], "name": v["name"], "specialty": v["specialty"], "lead_days": v["lead_days"]},
        "expected_arrival_if_approved_today": (today + timedelta(days=v["lead_days"])).isoformat(),
        "already_on_order": existing,
        "duplicate_warning": (f"Open invoice(s) {[e['invoice_id'] for e in existing]} already cover {sku} {size}; "
                              "pay or chase that order instead of buying again.") if existing else None,
        **cash,
        "payable": cash["can_cover"],
        "requires_human_approval": True,
        "status": "pending_human_approval",
        "note": APPROVAL_NOTE,
    }


# ---------- accounting ----------

@mcp.tool
def get_cash_position(account: str = "checking") -> dict:
    """Cash snapshot on the shop's today: account balance, every unpaid bill (open invoices + rent not yet paid
    this cycle) with due/overdue status, the total owed, cash left if all were paid, and recent approved
    payments (masked)."""
    with _db() as con:
        today = _today(con)
        acct = con.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            return {"error": f"Unknown cash account {account!r}."}
        bills = _unpaid_bills(con, today)
        pays = [_mask_payment(dict(r)) for r in con.execute("SELECT * FROM payments ORDER BY id DESC LIMIT 20")]
    owed = sum(b["amount"] for b in bills)
    return {
        "today": today.isoformat(),
        "account": _mask_account(account), "balance": _money(acct["balance"]), "balance_as_of": acct["date"],
        "unpaid_bills": bills, "total_owed": _money(owed),
        "overdue_total": _money(sum(b["amount"] for b in bills if b["overdue"])),
        "cash_after_all_bills": _money(acct["balance"] - owed),
        "can_cover_all_bills": acct["balance"] >= owed,
        "recent_payments": pays,
    }


@mcp.tool
def prepare_payment(kind: Literal["invoice", "rent"], ref_id: int, account: str = "checking") -> dict:
    """Prepare (do NOT make) a payment for a vendor invoice or lease rent, for a human to approve.

    kind="invoice": ref_id is invoices.id. kind="rent": ref_id is leases.id.
    Checks the amount, payee and due date against the DB, whether it is overdue on the shop's today, whether it
    was already paid, and whether the cash account can cover it. Flags low cash when the balance left after this
    payment would not cover the shop's other unpaid bills. Read-only: cash only changes when a human approves.
    """
    with _db() as con:
        today = _today(con)
        if kind == "invoice":
            row = con.execute(
                "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                "WHERE i.id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"No invoice {ref_id}."}
            prior = [dict(r) for r in con.execute(
                "SELECT * FROM payments WHERE kind = 'invoice' AND ref_id = ?", (ref_id,))]
            payee, amount, due = row["vendor_name"], row["amount"], row["due_date"]
            what = row["description"]
            not_payable = None if row["status"] == "open" else f"Invoice status is {row['status']!r}, not open."
        else:
            row = con.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if row is None:
                return {"error": f"No lease {ref_id}."}
            prior = _rent_paid_this_cycle(con, row)
            payee, amount, due = row["landlord"], row["monthly_rent"], row["next_due"]
            what = f"Monthly rent, {row['space_name']}"
            not_payable = None

        if prior and not not_payable:
            not_payable = "Already paid (see prior_payments)."
        cash = _cash_check(con, today, amount, account, exclude=(kind, ref_id))
    if "error" in cash:
        return cash

    return {
        "today": today.isoformat(),
        "payment_draft": {"kind": kind, "ref_id": ref_id, "payee": payee, "description": what,
                          "amount": _money(amount), "account": _mask_account(account)},
        **_due_info(due, today),
        "payable": not_payable is None and cash["can_cover"],
        "not_payable_reason": not_payable or (None if cash["can_cover"] else "Insufficient funds."),
        "prior_payments": [_mask_payment(p) for p in prior],
        **{k: v for k, v in cash.items() if k != "can_cover"},
        "requires_human_approval": True,
        "status": "pending_human_approval",
        "note": APPROVAL_NOTE,
    }


# ---------- facilities ----------

@mcp.tool
def get_lease(lease_id: int) -> dict:
    """Lease details for verifying a rent notice: space, landlord, monthly rent, next due date with
    days until due / overdue on the shop's today, and whether rent was already paid this cycle (masked)."""
    with _db() as con:
        today = _today(con)
        lease = con.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return {"error": f"No lease {lease_id}.",
                    "lease_ids": [r["id"] for r in con.execute("SELECT id FROM leases")]}
        paid = _rent_paid_this_cycle(con, lease)
    return {
        "today": today.isoformat(),
        "lease": dict(lease),
        **_due_info(lease["next_due"], today),
        "rent_paid_this_cycle": bool(paid),
        "payments_this_cycle": [_mask_payment(p) for p in paid],
    }


# ---------- pricing ----------

@mcp.tool
def quote_bulk_order(sku: str, qty: int, requested_unit_price: float | None = None) -> dict:
    """Price a bulk or discounted order for `sku` against the shop's list price and unit cost.

    Returns list and cost totals, margin at list, and the price floor: the unit cost, the lowest price that
    does not lose money, with the largest discount that keeps it. If `requested_unit_price` is given, also returns
    the discount, total and margin at that price, and whether it is allowed (at or above cost).
    Any price below list is a price override and needs human approval. Read-only.
    """
    with _db() as con:
        p = con.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"error": f"No pricing for SKU {sku!r}.",
                    "known_skus": [r["sku"] for r in con.execute("SELECT sku FROM pricing")]}
        name = con.execute("SELECT name FROM inventory WHERE sku = ? LIMIT 1", (sku,)).fetchone()

    lp, uc = p["list_price"], p["unit_cost"]
    out = {
        "sku": sku, "name": name["name"] if name else None, "qty": qty,
        "list_price": _money(lp), "unit_cost": _money(uc),
        "total_at_list": _money(lp * qty), "cost_total": _money(uc * qty),
        "margin_at_list": _money((lp - uc) * qty),
        "margin_pct_at_list": round((lp - uc) / lp * 100, 1),
        "price_floor_unit": _money(uc),
        "max_discount_pct_without_loss": round((lp - uc) / lp * 100, 1),
        "note": "The DB has no bulk-discount policy. Any price below list is a price override that needs human approval.",
    }
    if requested_unit_price is not None:
        rp = requested_unit_price
        out["requested"] = {
            "unit_price": _money(rp),
            "discount_pct": round((lp - rp) / lp * 100, 1),
            "total": _money(rp * qty),
            "margin_total": _money((rp - uc) * qty),
            "allowed": rp >= uc,
            "verdict": ("Below unit cost: the shop would lose money. Do not offer." if rp < uc else
                        "At or above cost: OK to propose, pending human approval." if rp < lp else
                        "At list price: no override needed."),
        }
    return out


if __name__ == "__main__":
    mcp.run(show_banner=False)
