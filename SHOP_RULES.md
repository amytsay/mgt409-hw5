# Campus Customs shop rules (HW5)

These are the operating rules for the agent team. The agent prompts (Problem 5) and the harness
build on them. Rules marked **(HW5)** come from the assignment pages. Rules marked **(data)** follow
from `data/campus_customs.db`.

## Databases
- `data/campus_customs.db` is the original. Never modify it. **(HW5)**
- `data/campus_customs_new.db` is the working copy. The MCP server and the backend read and write only this file, through `shop_config.py`. **(HW5)**
- "Reset" means copying the original over the working copy. **(HW5, P7/P9)**

## Today and overdue
- "Today" for the shop is `desk.date_today` (currently **2026-08-31**), never the computer's clock. **(user + data)**
- A bill is **overdue** when it is still open and its due date is before today. **(user)**
  - Invoice 501 (Bulldog Print Co, $840, due 2026-08-28, open) is **overdue by 3 days**. **(data)**
  - Lease 1 rent (Elm City Properties, $2,400, next due 2026-09-02) is **due in 2 days, not overdue**. **(data)**

## Money
- Agents only **prepare** payments. A human approves each one. The approve-payment route is the **only** thing that changes cash. **(HW5, P7)**
- Cash lives in `cash_accounts` (one `checking` account, $3,400.00 at start). Every approved payment adds a `payments` row with `approved_by`, and the checking balance drops by the same amount. **(HW5 + data)**
- Never prepare a payment the checking balance cannot cover. **(data)**
- The ending balance must match `cash_accounts` in the working DB. **(HW5, P9)**

## Data and grounding
- Agents get shop facts only through the MCP server. There is no tools layer that skips MCP. **(HW5, P5)**
- Answers and tool outputs use only values that exist in the DB. Nothing is made up. **(HW5, P3/P4)**

## Inventory, vendors and pricing (data)
- `qty = 0` means out of stock. CC-TEE-WHITE size S and CC-MUG-CREST are at 0.
- To restock, pick the vendor by `specialty`. Expected arrival = today + `lead_days` (Bulldog Print Co 5 days, Elm City Gifts 3 days, QuickShip CT 1 day).
- `pricing` gives `unit_cost` and `list_price`. Any discount must stay above `unit_cost`, so the shop never sells at a loss.
- An order cannot promise more than `inventory.qty` for that SKU and size. Ticket 103 asks for 20 M hoodies, and only 8 are in stock.

## Models and safety
- Every agent uses **gpt-6-luna** through **Portkey** with `PORTKEY_API_KEY`, and no other model. `shop_config.py` enforces this. **(user + HW5, P5)**
- Every agent-loop step appends to `output/audit_trail.json`. The log is append-only and never wiped. **(HW5, P5)**

## House policies (P5: our choices, written into the agent prompts; edit them if you want different limits)
- **Authority:** the Boss approves anything outside a specialist's limits. Money always needs the human owner.
- **Discounts:** the Boss may approve up to **15% off list** on orders of **10+ units**, and never below `unit_cost`. Deeper discounts go to the human.
- **Payment priority when cash is tight:** rent before its due date → overdue vendor invoices (especially ones blocking a customer order) → restock purchases for a confirmed customer order → anything else.
- **Never ship or promise a date on an order blocked by an unpaid invoice.** Arrival = approval date + vendor `lead_days`.
- **Don't order twice:** if an open invoice already covers an item (invoice 501 → tee S), pay or chase it instead of buying again.
- **Vendors by specialty:** apparel → Bulldog Print Co. Mugs and small goods → Elm City Gifts. QuickShip CT is a courier, not a supplier.
- **Rent notices** are checked against the lease. Only `leases.landlord` is paid, never a payee or amount taken from an email.
- **Privacy:** customers see products, sizes, prices, timing and next steps only. Never cash, bills, vendors, rent, costs or margins, and never another customer's details.

## Open tickets (all created 2026-08-31)
| Ticket | Type | Ask | Links to |
|---|---|---|---|
| 101 | customer_order | T. Z. (customer) needs 1 Classic Bulldog Tee, size S (0 in stock) | inventory, pricing, invoice 501 → vendor 1 (overdue rush reprint) |
| 102 | rent_notice | Elm City Properties: rent due in 2 days | lease 1 ($2,400 due 2026-09-02), cash_accounts |
| 103 | price_override | Y. A. C. (student org) wants 20 hoodies, size M, at a bulk discount | inventory (8 M on hand), pricing ($22 cost / $58 list) |
