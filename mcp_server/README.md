# Campus Customs MCP server

**What it's for:** This is the only way the five Campus Customs agents (Boss, Inventory, Accounting, Facilities,
Customer Service) get shop facts. The agents call these tools instead of querying the database, so every
answer comes from real rows and nothing is made up. The backend connects to it over stdio
(`backend/mcp_client.py`), and so does the vibe coder (`.mcp.json`).

**Database:** `data/campus_customs_new.db`, the working copy. Its path comes from `shop_config.py`, shared with the
backend. The original `data/campus_customs.db` is never touched. "Today" is `desk.date_today` (2026-08-31), not the
computer's clock.

**Safety built into the tools:**
- 9 of the 10 tools are read-only. The only write is `set_ticket_status`, which changes `tickets.status` and
  nothing else (Boss only).
- No tool moves money or changes stock. Payments and purchases come back as `pending_human_approval` drafts, and only
  a human approval in the backend changes cash.
- Payment data is masked: account names are shortened (`****king`), and approver names in past payments become initials.

**Built with:** FastMCP (`fastmcp` package), in `server.py`.

## Tools (10)

| Tool | Tables it uses | Used by | Main ticket | What it returns |
|---|---|---|---|---|
| `list_tickets(status="open")` | tickets, desk | Boss | all | Ticket ids, types, requesters, subjects and status |
| `get_ticket(ticket_id)` | tickets, inventory, pricing, leases, invoices, vendors, desk | all agents | all | One ticket plus every row it links to, with due and overdue status |
| `set_ticket_status(ticket_id, status)` | tickets (**write**: status only) | Boss | all | Previous and new status |
| `check_stock_for_order(sku, size, qty)` | inventory, pricing, invoices, vendors, desk | Inventory, Customer Service | **101**, 103 | On hand, shortfall, other sizes, aisle, list total, open restock invoice for that item, each vendor's arrival date |
| `get_inventory_report(sku=None)` | inventory, pricing, desk | Boss, Inventory | 101, 103 | Stock audit: every row, out-of-stock list, units on hand, stock value at cost and at list |
| `prepare_restock_order(sku, size, qty, vendor_id)` | inventory, pricing, vendors, invoices, leases, cash_accounts, payments, desk | Inventory, Accounting | **103** | Purchase draft (qty × unit cost), arrival date, duplicate-order warning, cash check, low-cash flag |
| `get_cash_position()` | cash_accounts, invoices, vendors, leases, payments, desk | Boss, Accounting | 101, 102, 103 | Balance, every unpaid bill with overdue status, total owed, cash left after all bills, recent payments (masked) |
| `prepare_payment(kind, ref_id)` | invoices, vendors, leases, cash_accounts, payments, desk | Accounting, Facilities | **102**, 101 | Invoice or rent payment draft, already-paid check, balance before and after, low-cash flag, `requires_human_approval` |
| `get_lease(lease_id)` | leases, payments, desk | Facilities | **102** | Lease terms, next due date with days until due or overdue, whether rent is already paid this cycle |
| `quote_bulk_order(sku, qty, requested_unit_price=None)` | pricing, inventory | Accounting, Customer Service | **103** | List and cost totals, margin, price floor, largest discount without a loss, and the math for a requested price |

Each agent sees only the tools in its "Used by" column (`backend/mcp_client.py`, `TOOL_ACCESS`).

## Run

```bash
python mcp_server/server.py
```

This runs over stdio. The backend starts it automatically for each ticket run.
Requires `fastmcp` and `python-dotenv` (see `requirements.txt`).
