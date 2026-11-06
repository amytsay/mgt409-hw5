# Campus Customs Multi-Agent Operations (MGT 409, Homework 5)

A Campus Customs help desk run by five AI agents (Boss, Inventory, Accounting, Facilities, Customer Service). They
reach shop data only through an MCP server, a FastAPI backend runs them, and a React board, *Elm City Nights*, lets
a human watch them and approve every payment. All agents use `gpt-6-luna` through Portkey.

**Quick start (full three-ticket run)**
1. Set up once: [Setup](#setup).
2. Reset the working DB to the original: [Copy the original DB](#1-copy-the-original-db-to-the-working-copy).
3. Optionally check the MCP server: [Start the MCP server](#2-start-the-mcp-server).
4. Start the backend: [Start the FastAPI backend](#3-start-the-fastapi-backend).
5. Start the board: [Start the React board](#4-start-the-react-board).
6. Run tickets 101, 102 and 103 on the board, and approve payments on the phone: [Full three-ticket run](#5-reset-before-a-full-three-ticket-run).

Results from the graded run are in `output/` (start with `output/desk_tickets.html` and `output/resolved_board.html`).

## What's in the repo

```
hw5/
├── AI_prompts.md     # log of the prompts used for each problem
├── SHOP_RULES.md     # shop rules + house policies the agents follow ("today" = desk.date_today, approvals)
├── shop_config.py    # the ONE place naming the DBs, Portkey settings and the model (gpt-6-luna only)
├── requirements.txt
├── .mcp.json         # connects the MCP server to the vibe coder (Claude Code)
├── .env.example      # variable names with placeholders (copy to .env)
├── .gitignore        # keeps .env and installs out of git
├── data/
│   ├── campus_customs.db       # original shop database (never modified)
│   └── campus_customs_new.db   # working copy used by the MCP server and backend
├── mcp_server/       # FastMCP server: the agents' only path to shop data (see mcp_server/README.md)
├── backend/
│   ├── main.py       # FastAPI routes for the dashboard (uvicorn main:app --reload --port 8000)
│   ├── approvals.py  # the human-approval write: the only code that moves cash
│   ├── agents.py     # the five agents: boss, inventory, accounting, facilities, customer_service
│   ├── team.py       # agent loop + delegation + audit of each step; `python team.py 102`
│   ├── models.py     # data types (AgentReport, TicketResolution, PaymentRequest, ...)
│   ├── prompts/      # one prompt file per agent
│   ├── mcp_client.py # MCP connection + per-agent tool access
│   ├── llm.py        # gpt-6-luna via Portkey
│   ├── guardrails.py # loop/token limits, masking, privacy checks
│   ├── audit.py      # append-only, hash-chained output/audit_trail.json
│   └── settings.py
├── frontend/         # React + Vite + TypeScript dashboard ("Elm City Nights"), see output/design.md
│   ├── src/App.tsx   # polling, events -> crew radio + car route, approvals, party
│   ├── src/api.ts    # the only place the backend URL lives (http://localhost:8000)
│   └── src/components/  # CityScene (3D city + chase cam), JobsBoard, CrewRadio, CashHud, ApprovalPhone, Debrief, Celebration
└── output/           # harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json,
                      # resolved_board.html (+ screenshots/), audit_trail.json, github_url.txt
```

## Setup

Tested with Python 3.13 and Node 24. Run every command from the `hw5/` folder unless a step says `cd`.

1. **Secrets:** copy `.env.example` to `.env` and put your own `PORTKEY_API_KEY` in it. `.env` is gitignored and is
   never committed.
2. **Python:** if the folder is inside OneDrive or Dropbox, pause syncing first. Live sync can lock files and corrupt the virtual environment.

   ```bash
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```

   On macOS or Linux, use `source .venv/bin/activate` and then `pip install -r requirements.txt`.
3. **Node:** `cd frontend` then `npm install`.

This setup was tested on 2026-11-05 in a fresh `.venv` (Python 3.13). The MCP server served all 10 tools, the backend
routes and CORS returned 200, the board loaded, and gpt-6-luna answered through Portkey.

## 1. Copy the original DB to the working copy

`data/campus_customs.db` is the original and is never modified. Everything else (the MCP server, the backend and the
approvals) uses only `data/campus_customs_new.db`, through `shop_config.py`. For a clean run, copy the original over
the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

On Windows PowerShell: `Copy-Item data\campus_customs.db data\campus_customs_new.db -Force`. If the backend is
running, use the reset route instead (step 5).

## 2. Start the MCP server

```bash
python mcp_server/server.py
```

It runs over stdio and has 10 tools (see `mcp_server/README.md`). You don't need to start it by hand for the app,
because the backend launches it automatically. `.mcp.json` connects it to a vibe coder (Claude Code). It contains
absolute paths from my machine, so update `command` and `args` to your own Python and checkout path.

## 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The backend runs at http://localhost:8000, and http://localhost:8000/docs lists every route (also in
`output/harness.md`, section 7).

## 4. Start the React board

In a second terminal:

```bash
cd frontend
npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000`.

## 5. Reset before a full three-ticket run

1. With the backend running, reset the working DB to the original. Either:
   - click **⟲ New game** on the board, or
   - run `curl -X POST http://localhost:8000/api/reset`.

   Either way, the original is copied over `campus_customs_new.db`, the approval queue is cleared, and checking goes
   back to **$3,400.00**. The audit trail is kept.
2. Run **101**, **102** and **103**: pick a job, hit **Start job**, and wait for RESOLVED.
3. Approve or decline each payment on the phone. Only an approval moves cash.

The graded run is documented in `output/desk_tickets.html` (Actual and Cash tabs). It went
$3,400.00 → $2,560.00 → $160.00.

## Run the agent team on one ticket (no UI)

```bash
cd backend
python team.py 102
```

This starts the MCP server over stdio, runs the Boss and whichever specialists it delegates to, and appends every
step to `output/audit_trail.json`. To check that audit file's hash chain: `python audit.py verify`.

## Notes

- **Don't edit `backend/` during a run.** `--reload` restarts the server on any `.py` change, which ends the run in
  progress.
- **CORS:** the backend allows the Vite origin (`http://localhost:5173`, plus other localhost ports).
- **Board extras:** add `?party` to the board's URL to preview the celebration. Sound is off until you turn it on.

## Secrets and model

All AI calls go through Portkey with `PORTKEY_API_KEY`, loaded from the nearest `.env`. Every agent uses
`gpt-6-luna`, and `shop_config.py` refuses to start if `OPENAI_MODEL` is set to anything else.
