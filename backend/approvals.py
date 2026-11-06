"""Human approvals: the ONLY code in the project that moves cash.

Agents can't reach this module. They have MCP tools only, and every MCP tool just *prepares* payments. The
dashboard's Approve button calls POST /api/approvals/{id}/approve (main.py), which first re-prepares the
payment through MCP (so the amount, payee and "already paid" check come from the DB), then calls
record_payment() here. One SQLite transaction:

    payments       INSERT the approved payment (kind, ref_id, amount, account, paid_at = shop today, approved_by)
    cash_accounts  balance -= amount (refused if it would go negative)
    invoices       status 'open' -> 'paid'   (kind 'invoice' only)

Rent leaves leases.next_due alone: the payment row is what marks this rent cycle paid (the MCP tools check
payments since one month before next_due). A purchase pays the vendor; stock arrives lead_days later, so
inventory is not changed here.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date

import settings  # noqa: F401  (puts hw5/ on sys.path)
import shop_config


class ApprovalError(RuntimeError):
    """The payment can't be made (already paid, not open, insufficient funds...). Nothing was written."""


def _one_month_before(d: date) -> date:
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def record_payment(kind: str, ref_id: int, amount: float, approved_by: str, account: str = "checking") -> dict:
    """Write one human-approved payment. All-or-nothing; raises ApprovalError and writes nothing on any problem."""
    if kind not in ("invoice", "rent", "purchase"):
        raise ApprovalError(f"Unknown payment kind {kind!r}.")
    if amount <= 0:
        raise ApprovalError("Amount must be positive.")
    with closing(shop_config.connect(readonly=False)) as con:
        con.isolation_level = None            # explicit transaction below
        con.execute("BEGIN IMMEDIATE")        # lock out other writers until commit
        try:
            today = con.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
            acct = con.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
            if acct is None:
                raise ApprovalError("Unknown cash account.")
            before = float(acct["balance"])
            if before < amount:
                raise ApprovalError(f"Insufficient funds: balance ${before:,.2f}, payment ${amount:,.2f}.")

            if kind == "invoice":
                inv = con.execute("SELECT status, amount FROM invoices WHERE id = ?", (ref_id,)).fetchone()
                if inv is None:
                    raise ApprovalError(f"No invoice {ref_id}.")
                if inv["status"] != "open":
                    raise ApprovalError(f"Invoice {ref_id} is {inv['status']!r}, not open.")
                if round(float(inv["amount"]), 2) != round(amount, 2):
                    raise ApprovalError(f"Invoice {ref_id} is ${inv['amount']:,.2f}, not ${amount:,.2f}.")
                if con.execute("SELECT 1 FROM payments WHERE kind = 'invoice' AND ref_id = ?", (ref_id,)).fetchone():
                    raise ApprovalError(f"Invoice {ref_id} was already paid.")
            elif kind == "rent":
                lease = con.execute("SELECT monthly_rent, next_due FROM leases WHERE id = ?", (ref_id,)).fetchone()
                if lease is None:
                    raise ApprovalError(f"No lease {ref_id}.")
                if round(float(lease["monthly_rent"]), 2) != round(amount, 2):
                    raise ApprovalError(f"Lease {ref_id} rent is ${lease['monthly_rent']:,.2f}, not ${amount:,.2f}.")
                cycle_start = _one_month_before(date.fromisoformat(lease["next_due"])).isoformat()
                if con.execute("SELECT 1 FROM payments WHERE kind = 'rent' AND ref_id = ? AND substr(paid_at, 1, 10) >= ?",
                               (ref_id, cycle_start)).fetchone():
                    raise ApprovalError(f"Rent for lease {ref_id} is already paid this cycle.")
            else:  # purchase: ref_id is the vendor
                if con.execute("SELECT 1 FROM vendors WHERE id = ?", (ref_id,)).fetchone() is None:
                    raise ApprovalError(f"No vendor {ref_id}.")

            cur = con.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
                (kind, ref_id, round(amount, 2), account, today, approved_by),
            )
            con.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                        (round(amount, 2), today, account))
            if kind == "invoice":
                con.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    return {"payment_id": cur.lastrowid, "kind": kind, "ref_id": ref_id, "amount": round(amount, 2),
            "paid_at": today, "balance_before": round(before, 2), "balance_after": round(before - amount, 2)}
