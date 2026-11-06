# Campus Customs Agent Harness (HW5)

This document describes how the Campus Customs agent team works, end to end: the shop's data, the MCP tools that
are the only way to reach it, the five agents, the safety rules, the backend API, the dashboard and the final runs.

**Contents**
1. Databases · 2. Tables and fields · 3. The three tickets · 4. MCP server and tools · 5. The five agents
· 6. Safety guardrails · 7. Backend routes · 8. Dashboard · 9. Final runs and cash (Problem 9) · 10. Output files

**How it fits together**

```
Owner (browser) ── React dashboard (frontend/, :5173)
                        │  HTTP + CORS
                        ▼
                  FastAPI backend (backend/main.py, :8000) ── approve click ──► backend/approvals.py ─► payments, cash_accounts
                        │  run ticket                                         (the only cash write)
                        ▼
      Boss ─delegate─► Inventory / Accounting / Facilities / Customer Service   (PydanticAI, gpt-6-luna via Portkey)
                        │  MCP tools only
                        ▼
             campus-customs MCP server (mcp_server/server.py) ─► data/campus_customs_new.db
                        │
   every step ─────────►  output/audit_trail.json (append-only, hash-chained)
```

## 1. Databases

| File | Role |
|---|---|
| `data/campus_customs.db` | Original shop data. Never modified. Used only to reset. |
| `data/campus_customs_new.db` | Working copy. The MCP server and backend read and write only this file, through `shop_config.py`. |

The shop's **today** is `desk.date_today` (**2026-08-31**). A bill is **overdue** when its status is still open
and its due date is before today. The full rules are in `SHOP_RULES.md`.

## 2. Tables and fields

### desk (1 row)
`date_today` (TEXT, required), `notes` (TEXT)

**Why it matters:** It sets the shop's "today", so every agent measures overdue bills, due dates and vendor arrival dates from the same date instead of the computer's clock.

### tickets (3 rows, all open)
`id` (PK), `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id` (FK → leases.id), `invoice_id` (FK → invoices.id), `status`, `notes`, `created_at`

**Why it matters:** This is the work queue. `type` tells the Boss which specialist to call first, and `sku`/`size`/`qty`, `lease_id` and `invoice_id` point to the rows that ticket needs.

### inventory (10 rows, PK = sku + size)
`sku`, `name`, `size`, `qty`, `location`

**Why it matters:** Inventory and Customer Service check stock per SKU and size here before promising anything. `qty = 0` means an order needs a restock.

### pricing (4 rows, PK = sku)
`sku`, `unit_cost`, `list_price`

**Why it matters:** List price is what a customer pays and unit cost is the floor for any discount. Agents use both to quote orders and judge a price override.

### vendors (3 rows)
`id` (PK), `name`, `specialty`, `lead_days`

**Why it matters:** It tells the Inventory agent which supplier makes what and how many days a restock takes, so the shop can give customers an honest arrival date.

### invoices (1 row)
`id` (PK), `vendor_id` (FK → vendors.id), `amount`, `due_date`, `status`, `description`

**Why it matters:** These are bills the shop owes vendors. Accounting compares `due_date` with today to spot overdue bills and prepares payments for a human to approve.

### leases (1 row)
`id` (PK), `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`

**Why it matters:** Facilities uses it to confirm rent notices against the actual lease (landlord, amount, due date) before Accounting prepares a rent payment.

### cash_accounts (1 row, PK = name)
`name`, `balance`, `date`

**Why it matters:** This is the shop's only cash: checking, $3,400.00 at start. Agents check it before preparing any payment, and only a human-approved payment lowers it.

### payments (0 rows at start)
`id` (PK), `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` (required)

**Why it matters:** It records every approved payment and who approved it. `kind` + `ref_id` point to the invoice or lease paid, and `account` matches `cash_accounts.name`. It is the audit record behind every cash change.

### Links
- Enforced foreign keys: `tickets.lease_id → leases.id`, `tickets.invoice_id → invoices.id`, `invoices.vendor_id → vendors.id`.
- Links the schema does not enforce, which agents have to join themselves: `tickets.sku → inventory.sku / pricing.sku`, `payments.ref_id → invoices.id or leases.id` (depending on `kind`), `payments.account → cash_accounts.name`.

## 3. The three open tickets

All were created on 2026-08-31, which is today.

| Ticket | Type | Requester | Ask | Linked rows |
|---|---|---|---|---|
| 101 | customer_order | T. Z. (customer) | 1 × Classic Bulldog Tee, size S | inventory CC-TEE-WHITE/S (**qty 0**, Aisle B); pricing ($8 cost / $28 list); invoice 501 → vendor 1 |
| 102 | rent_notice | Elm City Properties | "Shop rent due in 2 days" | lease 1 (Chapel Street shop, $2,400/month, next due 2026-09-02); cash_accounts |
| 103 | price_override | Y. A. C. (student org) | 20 × Basic Hoodie Big Yale, size M, bulk discount | inventory CC-HOOD-NAVY/M (**qty 8**, Aisle A); pricing ($22 cost / $58 list) |

**Ticket 101.** The tee is out of stock in size S. Its `invoice_id` is 501, an $840 "Rush reprint CC-TEE-WHITE S" from
Bulldog Print Co (apparel reprint, 5-day lead time). That invoice was due 2026-08-28 and is still open, so it is
**3 days overdue**. Filling the order means paying, or planning to pay, the overdue reprint bill, and that payment needs human approval.

**Ticket 102.** The notice matches lease 1: $2,400 due 2026-09-02, which is 2 days after today and not overdue.
Accounting can prepare the rent payment, but a human must approve it before cash drops.

**Ticket 103.** At list price, 20 hoodies cost $1,160 (unit cost $440). Only 8 size M are in stock, so a full order of 20 needs 12 more
from a restock (Bulldog Print Co, 5 days) or a mix of sizes (S 4, L 14, XL 6). Any discount has to stay above the $22
unit cost.

**Cash.** Checking holds $3,400.00. Rent ($2,400) plus invoice 501 ($840) comes to $3,240, which would leave $160.
This is why every payment goes through a human approval.

## 4. MCP server and tools (Problem 3)

**Server:** `mcp_server/server.py` (FastMCP, server name `campus-customs`). It reads `data/campus_customs_new.db`
through `shop_config.py` and opens it **read-only**. (The one exception, added in Problem 5, is the Boss-only
`set_ticket_status`.) Tools only report facts and prepare actions, and a human approves anything that moves money. All values below are the actual tool outputs on the working DB at today = 2026-08-31.

| Ticket | Tool that unlocks it | Supporting tool |
|---|---|---|
| 101 (T. Z., tee size S) | `check_stock_for_order` | `prepare_payment(invoice, 501)` |
| 102 (Elm City rent notice) | `prepare_payment` | none |
| 103 (Y. A. C., 20 hoodies M) | `quote_bulk_order` | `check_stock_for_order` |

### Tool 1: `check_stock_for_order(sku, size, qty)` (inventory and order fulfillment)
- **Tables read:** `inventory` (qty, location, other sizes), `pricing` (list price), `invoices` + `vendors` (open restock invoices for this SKU and size, lead days), `desk` (today).
- **Unlocks ticket:** **101.** Also used for 103.
- **Why it's the right tool for 101:** Ticket 101 asks for one CC-TEE-WHITE size S, and the tool shows that size has **0 on hand** (shortfall 1). It also finds the **open invoice 501, "Rush reprint CC-TEE-WHITE S"** from Bulldog Print Co ($840, **3 days overdue**, 5-day lead time, earliest arrival **2026-09-05**). So the agent can tell the customer the real reason and the real date, and route the overdue invoice to Accounting instead of just saying "out of stock".
- **For 103:** CC-HOOD-NAVY size M has **8 on hand for 20 requested** (shortfall 12, with S 4 / L 14 / XL 6 on hand), $1,160 at list. So the team knows the club's order can't be filled in size M from stock.

### Tool 2: `prepare_payment(kind, ref_id, account="checking")` (accounts payable with human approval and a low-cash flag)
- **Tables read:** `leases` (landlord, monthly_rent, next_due), `invoices` + `vendors` (amount, due_date, status, payee), `cash_accounts` (checking balance), `payments` (already-paid check), `desk` (today).
- **Unlocks ticket:** **102.** Also used for 101's invoice 501.
- **Why it's the right tool for 102:** The rent notice says "due in 2 days", and the tool checks that against lease 1. It confirms **Elm City Properties, $2,400, due 2026-09-02 (2 days, not overdue)**, finds no rent paid yet this cycle, and shows that checking goes from **$3,400 to $1,000**, which still covers the other unpaid bill (invoice 501, $840). It then returns the payment as **`pending_human_approval`** instead of paying, because agents may only prepare payments.
- **For 101:** `prepare_payment("invoice", 501)` drafts the **$840 overdue (3 days)** Bulldog Print Co payment. Checking would go from $3,400 to $2,560, still covering the $2,400 rent. With both paid, only **$160** is left.
- **Low-cash flag:** set when the balance after the payment can't cover the shop's other unpaid bills. Insufficient funds or an already-paid bill makes the payment `payable: false`.

### Tool 3: `quote_bulk_order(sku, qty, requested_unit_price=None)` (bulk pricing and price override)
- **Tables read:** `pricing` (unit_cost, list_price), `inventory` (product name).
- **Unlocks ticket:** **103.**
- **Why it's the right tool for 103:** Ticket 103 is a `price_override`: the club asks for a bulk discount on 20 CC-HOOD-NAVY. The DB has no discount policy, so the tool sets the limits from real numbers: **$1,160 at list, $440 at cost, $720 margin (62.1%)**, with a **$22.00/unit price floor**. Any discount up to 62.1% keeps the sale profitable, and a price under $22 (e.g. $20 → −$40) is flagged "do not offer". The agent can make a grounded counter-offer, and a human signs off on any price below list.

## 5. The agent team (Problem 5)

There are five PydanticAI agents. Every agent uses **gpt-6-luna through Portkey** (`PORTKEY_API_KEY`, `backend/llm.py`). The model
name lives only in `shop_config.py`, which refuses any other model. Each agent has its own prompt file, its own
filtered view of the MCP server, and the `delegate` tool. The agent loop (model → tool calls → model … → structured
answer) runs step by step in `backend/team.py`, which audits every step.

| Agent | Prompt | Job | MCP tools it may call | Returns |
|---|---|---|---|---|
| **Boss** | `backend/prompts/boss.md` | Routes each ticket to the right specialists, approves anything outside their limits (discounts up to 15%, payment priority when cash is low), monitors all activity, marks tickets resolved | `list_tickets`, `get_ticket`, `get_cash_position`, `get_inventory_report`, `set_ticket_status` | `TicketResolution` |
| **Inventory** | `backend/prompts/inventory.md` | Checks and audits stock, finds existing restock orders, plans restocks with the right vendor, reports to the Boss | `get_ticket`, `check_stock_for_order`, `get_inventory_report`, `prepare_restock_order` | `AgentReport` |
| **Accounting** | `backend/prompts/accounting.md` | Works with Inventory on how much to order and whether it fits the budget and cash on hand; prepares invoice, rent and purchase payments for human approval; discount math | `get_ticket`, `get_cash_position`, `prepare_payment`, `prepare_restock_order`, `quote_bulk_order` | `AgentReport` |
| **Facilities** | `backend/prompts/facilities.md` | Checks rent notices against the lease, makes sure rent is paid on time, and prepares the rent payment with Accounting | `get_ticket`, `get_lease`, `prepare_payment` | `AgentReport` |
| **Customer Service** | `backend/prompts/customer_service.md` | Works with Inventory and Accounting to give the customer accurate fulfillment, timing and price info; privacy-safe replies | `get_ticket`, `check_stock_for_order`, `quote_bulk_order` | `AgentReport` (with `customer_message`) |

**Delegation.** All five agents have `delegate(to_agent, task)`, so any agent can hand work to any other. The Boss
starts every ticket. A specialist can call another specialist directly (e.g. Customer Service → Inventory,
Facilities → Accounting). The delegated agent's `AgentReport` comes back as the tool result. Guard: an agent that is
already waiting in the current chain can't be called again, so A → B → A loops are impossible. Specialists escalate
to the Boss through `needs_boss_decision` in their report. Payment drafts aren't saved to the DB until a human
approves them, so every delegation result also carries `all_prepared_requests_this_ticket`. No draft gets lost between
agents, and none gets prepared twice.

**Tested live (gpt-6-luna via Portkey):**
- **Ticket 102:** Boss → Facilities → Accounting. $2,400 rent queued for approval and the ticket resolved. 13 model calls, about 39k tokens.
- **Ticket 101:** Boss → Inventory → Accounting, then Boss → Customer Service. $840 overdue invoice 501 queued, no duplicate order, privacy-checked reply. 14 calls, about 48k tokens.
- After each test the working DB was reset from the original. The test runs stay in the append-only audit trail.

**Data types** (`backend/models.py`): `PaymentRequest`, `PriceOverride`, `AgentReport`, `AgentContribution`,
`TicketResolution`, plus run state `TeamDeps`, `RunBudget` and `Delegation`.

**Code layout** (`backend/`): `agents.py` (the five agents and `delegate`), `team.py` (agent loop, audit of each step,
`run_ticket`), `mcp_client.py` (the only path to shop data), `llm.py` (Portkey + gpt-6-luna), `guardrails.py` (limits,
masking, output checks), `audit.py` (audit trail), `models.py`, `settings.py`, `prompts/`.

**Run one ticket:** from `backend/`, `python team.py 102`.

### MCP tools (final list) and the tables they use

| Tool | Tables | Read/Write |
|---|---|---|
| `list_tickets` | tickets, desk | read |
| `get_ticket` | tickets, inventory, pricing, leases, invoices, vendors, desk | read |
| `set_ticket_status` | tickets (status column only) | **write** (Boss only) |
| `check_stock_for_order` | inventory, pricing, invoices, vendors, desk | read |
| `get_inventory_report` | inventory, pricing, desk | read |
| `prepare_restock_order` | inventory, pricing, vendors, invoices, leases, cash_accounts, payments, desk | read (draft only) |
| `get_cash_position` | cash_accounts, invoices, vendors, leases, payments, desk | read |
| `prepare_payment` | invoices, vendors, leases, cash_accounts, payments, desk | read (draft only) |
| `get_lease` | leases, payments, desk | read |
| `quote_bulk_order` | pricing, inventory | read |

New in Problem 5: `list_tickets`, `get_ticket`, `set_ticket_status`, `get_inventory_report`, `prepare_restock_order`,
`get_cash_position`, `get_lease`. They give the Boss a way to read and close tickets, give Inventory a stock audit and
purchase drafts (ticket 103 needs 12 more M hoodies), give Accounting the whole-picture cash check, and give
Facilities the lease check for ticket 102.

### Audit trail (`output/audit_trail.json`)
- **Format:** JSON Lines, one record per agent-loop step, written by `backend/audit.py`. The file is only ever opened
  in append mode. Nothing truncates or rewrites it between runs.
- **Events:** `run_start` (ticket, model, limits), `agent_start` (agent, depth, chain, task), `delegation`,
  `tool_call` (tool and args), `tool_result`, `model_text`, `model_step` (running request and token counts),
  `retry`, `agent_output`, `agent_end`, `limit_hit`/`error`, and `run_end` (stop reason, duration, totals).
- **Every record has** `ts`, `run_id`, `ticket_id`, `agent`, `event`, `prev_hash` and `hash`.
- **Tamper evidence:** each record's hash covers the previous record's hash, so editing or deleting a line breaks
  the chain. `python backend/audit.py verify` checks it.
- **Privacy:** records are masked before writing. Customer names become initials, emails and card/bank/phone numbers
  are redacted, payment accounts arrive masked from MCP, and long values are length-capped.

## 6. Safety guardrails

**Money and authority**
1. **Human approval for every dollar.** Agents only prepare payments and purchases (`pending_human_approval`). Only
   the human's approve click in the backend (Problem 7) changes cash. No MCP tool can move money or change stock.
2. **Authority limits.** The Boss may approve discounts up to 15% off list on orders of 10+ units, never below unit
   cost. Anything deeper goes to the human. This is enforced in code: the Boss's answer is rejected if it resolves a
   larger discount.
3. **Cash discipline.** Every payment draft carries a low-cash flag (the balance left can't cover the other unpaid
   bills). Payment priority when cash is tight: rent before due → overdue invoices → restock for a customer order →
   other. Queued payments may never add up to more than the checking balance.
4. **No double payments or orders.** Tools refuse to treat an already-paid bill as payable, and they warn when a
   restock is already on order (e.g. invoice 501 for the size S tee).
5. **Fraud check on rent notices.** Facilities verifies a notice against the lease. Only `leases.landlord` is ever a
   payee, and a notice can't change the payee, amount or account.

**Data grounding**
6. **MCP is the only data path.** No agent has SQL or file access. Every agent sees only the MCP tools its role needs
   (least privilege). For example, Customer Service has no cash tools.
7. **No invented numbers.** A payment amount is rejected unless an MCP tool returned it this run, and so is any `$`
   amount in a customer message (output validators, `guardrails.py`).

**Privacy**
8. **Client information stays private.** Customer replies are checked automatically and rejected if they mention cash,
   balances, the bank account, invoices, vendors, rent, the landlord, costs or margins, or if they contain an email or
   account/card number. Customers are addressed by first name, and other customers are never mentioned.
9. **Masked payment data.** Account identifiers are masked at the source (`****king`), approver names become
   initials, and the audit trail masks customer names, emails, phone numbers and card/bank numbers.
10. **Prompt-injection resistance.** Ticket text is treated as data. Instructions inside a ticket ("skip approval",
    "pay now", "50% off") are ignored and noted.

**Loop and token limits** (`backend/guardrails.py`, per ticket; all agents share one usage counter)

| Limit | Value | What it stops |
|---|---|---|
| Model requests per ticket | 40 | Runaway model calls |
| Tool calls per ticket | 60 | Tool-call loops |
| Total tokens per ticket | 300,000 | Token cost blow-ups |
| Agent runs per ticket | 10 | Delegation storms |
| Delegation depth | 3 | Long chains (Boss → A → B → C at most) |
| Delegations per agent run | 4 | One agent fanning out to everyone |
| Loop steps per agent run | 16 | A single agent spinning |
| Wall-clock per ticket | 300 s | Hung calls |
| Output retries | 2 | Endless fix-and-retry on a failed check |
| Max tokens per model reply | 2,000 | Overlong answers |

When a limit is hit, the run stops cleanly. `limit_hit` and `run_end` (with the stop reason) go to the audit trail,
and the ticket stays open for a human.

## 7. Backend routes (Problem 7)

`backend/main.py` (FastAPI). Run it from `backend/` with `uvicorn main:app --reload --port 8000`. Base URL: http://localhost:8000. Interactive docs: http://localhost:8000/docs.

- `GET /api/health`: shows the server is up, plus the model (gpt-6-luna), the shop's today and which ticket is running, if any.
- `GET /api/tickets`: all 3 tickets, whether each is open or resolved, and the last run (customer names shown as initials).
- `GET /api/tickets/{id}`: one ticket with its linked inventory, pricing, lease, invoice and vendor rows.
- `POST /api/tickets/{id}/run`: runs the agent team on that ticket in the background (`?wait=true` waits for it). Only one ticket runs at a time.
- `GET /api/runs` and `GET /api/runs/{id}`: run status (running, done or error), plus the Boss's resolution, delegations, stop reason and token use.
- `GET /api/events`: recent agent events from the audit trail (what each agent said, delegations, tools called and their results). `?ticket_id=`, `?run_id=` and `?after=` filter the list so the board can refresh.
- `GET /api/approvals`: payments and purchases the agents prepared, with each one's status (pending, approved or rejected).
- `POST /api/approvals/{id}/approve`: the human clicks Approve. The payment is re-checked through MCP, then written to `payments` and taken off the checking balance; an approved invoice is marked paid. **This is the only route that moves cash.**
- `POST /api/approvals/{id}/reject`: the human clicks Reject. Nothing is paid.
- `GET /api/cash`: the current checking balance from `cash_accounts` (account shown masked), plus unpaid bills, total owed and recent payments.
- `POST /api/reset`: copies `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run and clears the approval queue. The audit trail is kept.

How the backend follows the guardrails:
- **Shop data comes through MCP.** Every route reads shop facts through the campus-customs MCP server. The approve write is the one exception: it lives in `backend/approvals.py`, where no agent can reach it.
- **Approvals are checked twice.** Before paying, the approve route re-prepares the payment through MCP and refuses it (HTTP 409) if any of these is true:
  - the amount has changed
  - it was already paid
  - it's a duplicate restock
  - there isn't enough cash
- **CORS:** the backend allows the dashboard's Vite origin (`http://localhost:5173`, plus other localhost ports), so the browser can call these routes. The dashboard (`frontend/src/api.ts`) calls `http://localhost:8000`.
- **The audit trail records human actions too.** Approvals, rejections and resets are appended to the audit trail as `human_approval`, `human_rejection` and `db_reset`.
- **One bill, one queue item.** Queue ids are built from the bill itself (`invoice-501`, `rent-1`,
  `purchase-{vendor}-{sku}-{size}-{qty}`), so a bill flagged by two agents or two tickets is still paid only once.
  - A decided item (approved or rejected) is never re-queued.
  - Since Problem 9, a pending item that a second ticket flags keeps the ticket that first raised it and lists the other under
    `also_requested_by`. In the P9 run, ticket 103 re-flagged invoice 501, and it stayed attributed to ticket 101.

**Tested on 2026-11-05.** I ran ticket 102 through `POST /api/tickets/102/run`. It went Boss → Facilities → Accounting and was resolved, with $2,400 rent queued for approval (11 model calls, 45.8 s).
- **Approve:** approving `rent-1` dropped the balance from $3,400 to $1,000, and the rent no longer appeared in the unpaid bills.
- **Double approval:** approving `rent-1` again returned 409.
- **Reset:** reset restored $3,400 and all 3 tickets to open. The working DB is byte-identical to the original.
- **Audit trail:** the hash chain checks out across 225 records.

## 8. Dashboard (Problem 8)

`frontend/` is a React 19 + Vite 6 + TypeScript app called *Elm City Nights*: a neon, third-person driving game where
each ticket is a "job". Run it with `npm run dev` in `frontend/` → http://localhost:5173. It calls the backend at
`http://localhost:8000` (`frontend/src/api.ts`, or `VITE_API_BASE`). Full design notes are in `output/design.md`.

**What it does**

| Requirement | On the dashboard |
|---|---|
| List the 3 tickets | Jobs board (left) and glowing mission markers on the city map. Each shows open / working / resolved / needs you. |
| Pick a ticket and start the team | Click a job, and the car drives there. **▶ Start job** calls `POST /api/tickets/{id}/run`. |
| Show each agent and what it says or does | The crew roster shows who is ON AIR. The crew radio polls `GET /api/events` every 1.2 s for messages, delegations and tool calls, with a "tool data" toggle. Speech bubbles appear over each agent's building, and the car follows every delegation. |
| Mark resolved when the run finishes | The marker turns green, the board says RESOLVED and a JOB COMPLETE party plays. |
| Short summary per agent | The **Debrief** has a card per agent, plus the delegation chain, the Boss's calls, the money queued and the customer reply. |
| Human approves a payment or purchase | Payments ring the **phone** ("Incoming: LEDGER"). Each shows the amount, payee, due date, priority, the low-cash or over-balance warning and *why the crew wants it*. Approve and Decline call `POST /api/approvals/{id}/approve` and `/reject`. |
| Checking balance drops after an approved payment | The top-right cash counter (`GET /api/cash`) rolls down, and a red "−$X" floats away. |

Each of the five agents has its own callsign, color, building and radio "voice":
- Boss = BIG DOG (gold)
- Inventory = STACKS (cyan, manifest style)
- Accounting = LEDGER (mint, ledger lines)
- Facilities = KEYS (orange, blueprint grid)
- Customer Service = HOTLINE (pink chat bubble)

**Accessibility:**
- black-and-pink, high contrast, real buttons with labels and focus rings
- `aria-live` radio and toasts
- reduced-motion support
- sound off by default
- clear loading and error states, including a "Can't reach the backend" banner

## 9. Final runs and cash (Problem 9)

**Reset.** `POST /api/reset` copied `data/campus_customs.db` over `data/campus_customs_new.db` on 2026-11-05 at 23:07 UTC.
The two files' SHA-256 matched (`23686a90…`). All 3 tickets were open, no payments existed, and the starting checking
balance was **$3,400.00**.

**Runs.** All three tickets were started from the dashboard, one after another. Each run used gpt-6-luna through
Portkey, stayed inside every loop and token limit (`stop_reason: completed`), and ended with the Boss setting the
ticket to **resolved**.

| Ticket | Run | Agents (delegations) | MCP tools used | Stats | Result |
|---|---|---|---|---|---|
| 101 | d92a5eff83d4 | Boss → Inventory → Accounting; Boss → Customer Service | get_ticket, check_stock_for_order, get_cash_position, prepare_payment, set_ticket_status | 7.4 s, 14 model / 13 tool calls | $840 overdue invoice 501 queued (urgent); no duplicate order; private reply |
| 102 | 99aa52d36a81 | Boss → Facilities → Accounting | get_ticket, get_lease, prepare_payment, get_cash_position, set_ticket_status | 6.1 s, 11 model / 11 tool calls | Notice verified against lease 1; $2,400 rent queued (urgent) |
| 103 | 8dc4d2342ecf | Boss → Accounting + Inventory (parallel); Inventory → Accounting; Boss → Customer Service | get_ticket, check_stock_for_order, quote_bulk_order, prepare_restock_order, get_cash_position, prepare_payment, get_inventory_report, set_ticket_status | 102.7 s, 22 model / 22 tool calls | 15% discount approved by the Boss ($49.30 × 20 = $986.00, above cost); $264 restock flagged low-cash and deferred |

**Human approvals and cash** (each step is the checking balance in `cash_accounts`):

| Step | Ticket | Payment | Amount | Checking after |
|---|---|---|---:|---:|
| Start | — | after reset | — | $3,400.00 |
| Approved | 101 | invoice 501 → Bulldog Print Co (payment #1) | −$840.00 | $2,560.00 |
| Approved | 102 | rent, lease 1 → Elm City Properties (payment #2) | −$2,400.00 | $160.00 |
| Left pending | 103 | restock 12 × CC-HOOD-NAVY M → Bulldog Print Co | $0.00 (not paid) | $160.00 |
| **End** | | **total paid out $3,240.00** | **−$3,240.00** | **$160.00** |

**Reconciliation:**
- $3,400.00 − $840.00 − $2,400.00 = **$160.00**. This equals `cash_accounts.balance` (checking) in the working DB, and
  the `payments` table sums to $3,240.00.
- The $264 restock can't be paid right now ($264 > $160), and the backend would refuse it. It stays pending until cash
  comes in.
- Ticket 103 also re-flagged invoice 501. That is the same bill, so it was paid once and counted under 101.

**How the safety rules showed up in the run**
- **Every dollar needed a human click.** Agents only prepared payments, and cash moved only on my two approvals.
  Each approval was re-checked through MCP first.
- **No double orders or payments:**
  - Ticket 101 found the reprint already on invoice 501 and didn't order again.
  - Rent was prepared by both Facilities and Accounting but was one queue item.
  - Invoice 501, flagged by both 101 and 103, was paid once.
- **Cash discipline.** The $264 restock got the low-cash flag ($3,136 left < $3,240 owed), and the Boss ranked it
  behind rent and the overdue invoice.
- **Authority limits.** The Boss approved exactly 15% on 20 units, at the edge of its limit and above the $22 unit
  cost. Nothing deeper was offered.
- **Privacy.** Customer replies use initials (T., Y. A. C.) and contain no costs, cash, vendors or invoices. The
  account shows as `****king`.
- **Loop limits.** The biggest run (103) used 22 of 40 model requests, 22 of 60 tool calls and 5 of 10 agent runs.

## 10. Output files

| File | What it is |
|---|---|
| `output/desk_tickets.html` | Per-ticket Expected (P6) and Actual (P9) sections, the Cash tab (itemized and reconciled) and the Reflection tab (P10) |
| `output/resolved_tickets.json` | For each ticket: id, final status, short outcome, agent contributions, delegations, tools, human approvals and cash change, plus the cash summary |
| `output/resolved_board.html` | Dashboard screenshots for each resolved ticket and the final board (`output/screenshots/`) |
| `output/audit_trail.json` | Append-only, hash-chained JSONL of every agent step, approval and reset, ending with the `p9_closeout` record. Check it with `python backend/audit.py verify`. |
| `output/design.md` | Dashboard design notes (P8) |
| `output/mcp_smoke.json` | MCP tool smoke test (P4) |
| `output/approval_queue.json` | Runtime approval queue (gitignored) |
