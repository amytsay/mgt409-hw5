# Dashboard design: *Elm City Nights*

The Campus Customs dashboard (`frontend/`, React + Vite + TypeScript) turns the agent desk into a neon,
third-person driving game. You pick a job, drive to it, send the crew, and the car follows every hand-off
between agents while the crew radio plays what each one says and does. When the job closes, the city throws
a party. When money needs to move, your phone rings.

Run it with `npm run dev` in `frontend/` → http://localhost:5173. The backend runs at http://localhost:8000.
Add `?party` to the URL to preview the celebration without running a job.

---

## 1. The idea: an open-world drive through the desk

Grand Theft Auto VI arrives this month, and it's the most hyped game launch in years. Everyone is talking
about neon coastlines, sunsets over the skyline and that feeling of cruising a living city at night. This
dashboard borrows that **energy** for something very ordinary: a shop owner watching five AI agents close
three desk tickets.

It's an **homage to the genre, not a copy of any game.** Everything here is original:

- **The city:** "Elm City", a neon New Haven built on its real street grid (Elm, Chapel, Crown, Water, Park,
  York, College, Temple, State), with the Green and the harbor.
- **Names and logo:** "Elm City Nights" and the crew callsigns are new. There is no Rockstar logo, font,
  character, map, music or art anywhere.
- **Genre conventions only:** the chase cam, minimap, speedometer, mission markers, objective line, phone,
  money counter and "job complete" screen show up in racing and open-world games everywhere. They're used
  here as a shared language that players already understand.
- **Appropriate content:** the "jobs" are customer orders, rent and a bulk discount. The "crew" are
  coworkers. There's no violence, crime, weapons or wanted level. The only "heist" is getting a student club
  20 hoodies at a fair price.

## 2. The look

| Element | Choice | Why |
|---|---|---|
| Background | Near-black night (`#07060b`) | Matches the house style in `AGENTS.md` (black + pink). It makes neon pop and keeps text readable. |
| Primary accent | Hot pink `#ff3d9a` → violet `#b26bff` | The player's car, GPS route, job markers and primary buttons. It's the sunset color, and it says "this is you". |
| Streetlight cyan | `#35f0ff` | The selected job and the "you are here" state. |
| Gold | `#ffd23f` | The Boss, plus anything in progress. |
| Mint green | `#3dffa8` | Money and resolved jobs. Cash is always green, like a game's money counter. |
| Red / orange | `#ff4d6d`, `#ff9f43` | Money leaving, low-cash warnings and urgent bills. |
| Headlines | Heavy condensed italic (Impact family), skewed −6° to −9° | Speed: every title leans forward. |
| Body text | System sans (Segoe UI) | Agent messages are long, so they have to stay readable. |
| Sky | Synthwave sunset: a striped sun sitting on a dark skyline, with stars above | It instantly reads as a night drive and frames the city behind the HUD. |
| Buildings | Extruded 3D blocks with neon roof outlines and lit-window dot patterns | Built in pure CSS 3D. It's light and fast, and needs no game engine. |
| Ground | Asphalt streets with pink curbs, gold lane dashes, crosswalks and real street names; a neon grid that fades into the horizon | It's a real map, so you can follow where the car is going. |

**Camera:** the default is a **chase cam**, a low third-person view behind the car that turns when the car
turns, with the sunset on the horizon. **City view** pulls back to show the whole map, which is useful for
seeing every job and landmark at once. People with *reduced motion* switched on always get the city view.

### Screen layout

The 3D city fills the whole screen, and the controls float over it as dark glass panels, like a game HUD:

| Where | What |
|---|---|
| Top left | The *Elm City Nights* logo, "Campus Customs desk ops" and the shop's date (Aug 31, 2026). |
| Top center | The **objective line** (for example, "Sign off on 2 payments on your phone") and a GPS chip naming the destination. |
| Top right | Model badge (gpt-6-luna), 🎥 camera, 🔈 sound and ⟲ New game buttons, and the **cash counter** (checking balance, total owed, cash left after all bills). |
| Left panel | **Jobs board**: the three tickets with their status pills, the Start job button and a Debrief button once a job is closed. |
| Right panel | **Crew roster** (the five agents as chips) above the **crew radio** feed. |
| Center | The city, the player's car, the agents' buildings and the job markers with their speech bubbles. |
| Bottom left | **Speedometer** (with NITRO) and the **minimap**. |
| Pop-ups | The **phone** (approvals) slides up from the bottom. The **debrief** and the **JOB COMPLETE** party open over the city. |

Under 1,180 px wide, the panels stack below the city so it still works on a laptop or tablet.

## 3. The map: every agent has a home base

| Place | Who works there | Street corner |
|---|---|---|
| 🐶 **Campus Customs HQ** (gold tower) | BIG DOG, the Boss | College & Chapel |
| 📦 **The Stockroom** | STACKS, Inventory | Park & Elm |
| 💸 **Ledger Lounge** (tallest tower, the "bank") | LEDGER, Accounting | State & Elm |
| 🔑 **Lease Office** | KEYS, Facilities | State & Water |
| 📞 **Hotline Diner** | HOTLINE, Customer Service | Park & Water |
| 👕 Job 101 · *Special Delivery* | the size-S tee customer | York & Crown |
| 🏠 Job 102 · *Rent Day* | the landlord's notice | Temple & Crown |
| 🧥 Job 103 · *Bulk Deal* | the student org | College & Water |

Each job has a **mission marker**: a glowing ring with a light beam and a sign. It's pink when open, cyan when
selected, gold while the crew works, mint when resolved and orange when it needs you. A few AI cars loop the
blocks so the city feels alive.

## 4. How a run plays out

1. **Pick a job** on the Jobs board (or click its marker). The car drives there along the streets: a pink GPS
   line on the road and the minimap, a speedometer that climbs, and an objective line that updates.
2. **Start the job.** The car heads to HQ for BIG DOG's briefing, and the crew radio starts recording.
3. **Follow the crew.** The dashboard polls `GET /api/events` every 1.2 seconds. Every delegation sends the
   car to the next agent's building, every tool call lights that agent up, and every message appears in a
   speech bubble above their building. When agents hand off faster than the car can drive, **NITRO** kicks
   in: a cyan exhaust flame and a speed boost so the car never falls behind the agents.
4. **Ticket resolved.** When the run ends, the car drives the result back to the job marker. The Boss marks
   the ticket resolved, the marker turns mint and the board updates.
5. **The party.** JOB COMPLETE slams onto the screen in chrome-gradient letters, with confetti, fireworks, the
   crew dancing, a victory donut from the car and run stats (time, crew size, tool calls, money waiting).
   With sound on, there's a short synth fanfare too.
6. **Debrief.** A card for each agent shows what they did, along with the delegation chain, the Boss's calls,
   the money queued and the reply drafted for the customer, shown as a text-message bubble.
7. **The phone rings.** Payments the crew prepared arrive as an "Incoming: LEDGER" call. You see the amount,
   payee, due date, priority, any low-cash warning and *why the crew wants it*. Tapping **Approve** is the
   only thing that moves money. The checking counter then rolls down with a red "−$2,400.00" floating away.

### How resolved tickets and cash are shown

**Resolved tickets.** A resolved ticket changes in four places at once, so it can't be missed:
- **Jobs board:** its pill turns green with "RESOLVED", the Start button becomes a disabled "JOB CLOSED" and a **Debrief** button appears.
- **Counter:** the "N / 3 done" counter goes up.
- **Map:** its marker turns mint green.
- **Party:** the JOB COMPLETE party plays once.

A run that stops without resolving shows an orange "NEEDS YOU" pill instead.

**Cash.** The top-right counter always shows the live **checking balance** from `cash_accounts`.
- **Under the balance:** "Owed $X · after all bills $Y", so you can see what's coming.
- **When you approve a payment:** the number rolls down, and a red "−$2,400.00" floats away. Cash is green, and money leaving is red.
- **On the phone, each payment shows:**
  - the amount, payee and due date;
  - a priority tag (URGENT or DEFER);
  - an orange **low-cash** warning, and a red **"More than the checking balance"** warning when it can't be paid.

In the Problem 9 run, the counter went $3,400.00 → $2,560.00 → $160.00 (see `resolved_board.html`).

## 5. How the agents "read" differently

Each agent has a callsign, a color, an icon, a building and its own **voice on the radio**, so you can tell
who's talking at a glance, even while scrolling quickly.

| Agent | Callsign | Color | Radio style | Why |
|---|---|---|---|---|
| Boss | 🐶 **BIG DOG** (after Yale's bulldog) | Gold | Bold text on a gold wash; final reports in small caps | It reads like a command, because the Boss decides. |
| Inventory | 📦 **STACKS** | Cyan | Monospace with a dashed border, like a packing manifest | Stock talk is SKUs, sizes and aisles, so it looks like a manifest. |
| Accounting | 💸 **LEDGER** | Mint | Monospace with tabular numbers on ruled ledger lines | Dollar figures line up the way they would in a ledger. |
| Facilities | 🔑 **KEYS** | Orange | Text on a blueprint grid | Leases and buildings get a blueprint feel. |
| Customer Service | 📞 **HOTLINE** | Pink | A rounded chat bubble | This agent talks to people, so it looks like texting. |
| System / Dispatch | 📡 **DISPATCH** | Gray | Centered, small italic | Narration stays out of the way. |

**Message types are styled differently too:**
- **Dispatch (delegation):** striped, with a 📻 and "➜ TO WHOM".
- **Report (final answer):** a glowing border and a REPORT tag.
- **Tool call:** a compact chip, e.g. `💸 LEDGER · prepare_payment(...)`.
- **Tool data:** hidden by default behind a "tool data" toggle, so the feed stays readable.
- **Warnings:** orange.
- **Your own approvals:** gold.

The **crew roster** above the radio shows the five agents as chips. The one talking glows and bobs ("ON AIR"),
and finished agents show "✓ N tools".

## 6. Why people would enjoy using this

- **It breaks the monotony.** Most operations dashboards are gray tables. A shop owner checking rent and
  invoices at 11 pm deserves a little joy. Turning routine approvals into "missions" makes the boring parts
  something you *want* to open.
- **Watching agents builds trust.** AI agents are a black box. Here, every hand-off becomes a drive you can
  watch: Boss to Facilities to Ledger and back. You can *see* that Facilities checked the lease before
  Accounting touched money. The audit trail stops being a log file and becomes a story you just watched.
- **Spatial memory.** People remember places better than rows. After one run you know Ledger Lounge is up by
  Elm and State. Next time the car heads there, you know money is involved before you read a word.
- **Clear moments of control.** The game never takes the wheel on money. The phone rings and *you* decide.
  Approve and Decline are big, clear and explained, and the cash counter reacts right away, so the
  consequence is impossible to miss.
- **Closure feels good.** The party scene rewards finishing a job. A small celebration turns "ticket
  resolved" into a win, and that is exactly the behavior you want to encourage at a help desk.
- **Perfect timing.** With GTA VI landing this month, the neon-sunset, open-world look is everywhere. Using
  that visual language (without borrowing anything from the game itself) makes the tool feel current and
  gives the team something to talk about. Nobody brags about their ticketing tool; people might show this
  one to a friend.

## 7. Accessibility and safety

- **Readable:** light text on near-black at high contrast, large display type for numbers, and body text in a
  plain sans font. Every status has a text label as well as its color.
- **Keyboard and screen readers:**
  - Everything is a real button with a label and a visible cyan focus ring.
  - The radio feed and toasts are `aria-live` regions.
  - Dialogs (debrief, phone) have labels and close with Esc.
- **Reduced motion:**
  - If the operating system asks for less motion, the chase cam is replaced by the steady city view.
  - Animations are cut back and the party uses far less confetti.
- **Sound is off by default.** The 🔈 toggle remembers your choice. All sound effects are synthesized in the
  browser; there are no audio files.
- **Clear loading and error states:**
  - Shimmering placeholders while the jobs load.
  - A red "Can't reach the backend" banner with the exact command to start it.
  - Errors from the backend (for example, "already approved") shown as toasts.
- **Privacy:**
  - Customers and the student org appear as initials (T. Z., Y. A. C.), including in run results and replies.
  - The bank account shows only as `****king`.
  - Internal costs never appear in the customer reply; the backend checks this.
- **Money:** agents only *prepare* payments. The dashboard's Approve button is the only way cash moves.
  The backend re-checks the payment through MCP before paying and refuses duplicates or overdrafts.

## 8. How it's built

- **No game engine.** The city is CSS 3D (`perspective`, `preserve-3d`, extruded `div` faces) on top of an
  SVG street map. The car is five stacked layers plus a cabin, which gives it a cheap 3D body.
  Camera-facing signs counter-rotate using CSS variables. The only dependencies are React and Vite, so the
  install stays small.
- **Smooth without heavy re-rendering.** Car physics (acceleration, braking before stops, nitro), camera
  smoothing, traffic, the speedometer and the minimap all run in one `requestAnimationFrame` loop that
  updates the page directly. React only re-renders when real data changes.
- **Talks only to the backend routes:** `/api/tickets`, `/api/tickets/{id}/run`, `/api/runs/{id}`,
  `/api/events`, `/api/approvals` (+ approve / reject), `/api/cash` and `/api/reset` ("⟲ New game").
  The address is set in `frontend/src/api.ts`: `http://localhost:8000`, or `VITE_API_BASE` if you set it.
  The backend's CORS allows the Vite origin, `http://localhost:5173`.
