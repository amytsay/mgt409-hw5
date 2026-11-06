import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, ApiError, api } from "./api";
import { CREW, CREW_ORDER, crewOf, jobMeta } from "./crew";
import { PLACES } from "./city";
import { playCash, playFanfare, playRadio, playStart, sound } from "./sound";
import type { AgentEvent, AgentName, ApprovalItem, CashResponse, RunState, Ticket } from "./types";
import { CityScene, type CamMode, type CitySceneHandle, type PlaceState } from "./components/CityScene";
import { JobsBoard } from "./components/JobsBoard";
import { CrewRadio, CrewRoster, type CrewStatus, type RadioLine } from "./components/CrewRadio";
import { CashHud } from "./components/CashHud";
import { ApprovalPhone } from "./components/ApprovalPhone";
import { Debrief } from "./components/Debrief";
import { Celebration } from "./components/Celebration";

const POLL_MS = 1200;
const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
const freshCrew = (): Record<AgentName, CrewStatus> =>
  Object.fromEntries(CREW_ORDER.map((a) => [a, { state: "idle", tools: 0 }])) as Record<AgentName, CrewStatus>;

interface Toast { id: number; text: string; tone: "info" | "good" | "bad" }
interface Party { ticketId: number; title: string; subtitle: string; stats: string[]; crew: AgentName[] }

export default function App() {
  const reduced = useMemo(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches, []);
  const scene = useRef<CitySceneHandle>(null);
  const cursor = useRef(0);

  const [tickets, setTickets] = useState<Ticket[] | null>(null);
  const [today, setToday] = useState<string>("");
  const [cash, setCash] = useState<CashResponse | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [offline, setOffline] = useState<string | null>(null);
  const [model, setModel] = useState<string>("");

  const [selected, setSelected] = useState<number | null>(null);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [runs, setRuns] = useState<Record<number, RunState>>({});
  const [lines, setLines] = useState<RadioLine[]>([]);
  const [crew, setCrew] = useState(freshCrew);
  const [activeAgent, setActiveAgent] = useState<AgentName | null>(null);
  const [bubbles, setBubbles] = useState<Record<string, string | undefined>>({});
  const [arrivedAt, setArrivedAt] = useState<string | null>("hq");
  const [drive, setDrive] = useState<{ driving: boolean; dest: string | null; nitro: boolean }>({ driving: false, dest: null, nitro: false });
  const [cam, setCam] = useState<CamMode>(reduced ? "map" : "chase");
  const [soundOn, setSoundOn] = useState(sound.enabled);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [debrief, setDebrief] = useState<RunState | null>(null);
  const [party, setParty] = useState<Party | null>(null);
  const finishing = useRef<{ ticketId: number; run: RunState; location: string; fired: boolean } | null>(null);

  const toast = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200);
  }, []);

  const addLines = useCallback((more: RadioLine[]) => {
    if (more.length) setLines((l) => [...l, ...more].slice(-400));
  }, []);

  // ---------- data ----------
  const refreshTickets = useCallback(async () => {
    const t = await api.tickets();
    setTickets(t.tickets);
    setToday(t.today);
    return t.tickets;
  }, []);
  const refreshMoney = useCallback(async () => {
    const [c, a] = await Promise.all([api.cash(), api.approvals()]);
    setCash(c);
    setApprovals(a.items);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const [h, ev] = await Promise.all([api.health(), api.events({ limit: 1 })]);
        setModel(h.model);
        cursor.current = ev.last_seq;
        await Promise.all([refreshTickets(), refreshMoney()]);
        setOffline(null);
        if (h.running_ticket !== null) {   // page reloaded mid-run: pick the run back up
          setSelected(h.running_ticket);
          setRunningId(h.running_ticket);
          addLines([{ key: "resume", agent: null, kind: "system", ts: new Date().toISOString(),
            text: `Rejoining job #${h.running_ticket}. The crew is already rolling.` }]);
        }
      } catch (e) {
        setOffline(e instanceof ApiError ? e.message : String(e));
      }
    })();
  }, [refreshTickets, refreshMoney, addLines]);

  // Preview the celebration without running a job: http://localhost:5173/?party
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("party")) {
      setParty({ ticketId: 0, title: "JOB COMPLETE", subtitle: "🎉 Party preview", crew: [...CREW_ORDER],
        stats: ["⏱ 12.9s", "👥 5 crew", "🔧 11 tool calls", "💳 preview only"] });
    }
  }, []);

  // ---------- events -> radio, crew lights, car route ----------
  const goTo = useCallback((agent: AgentName | null) => {
    if (agent) scene.current?.driveTo(CREW[agent].base);
  }, []);

  const handleEvents = useCallback((events: AgentEvent[]) => {
    const out: RadioLine[] = [];
    let beep = false;
    for (const e of events) {
      const c = crewOf(e.agent);
      const a = c?.id ?? null;
      const base = { key: `${e.seq}`, agent: e.agent, ts: e.ts };
      switch (e.event) {
        case "run_start":
          out.push({ ...base, kind: "system", text: `Job #${e.ticket_id} is live. ${CREW.boss.callsign} has the ticket.` });
          break;
        case "agent_start":
          if (a) {
            setCrew((s) => ({ ...s, [a]: { ...s[a], state: "active" } }));
            setActiveAgent(a);
            goTo(a);
            if (a === "boss") out.push({ ...base, kind: "speech", text: "On it. Reading the ticket." });
          }
          break;
        case "delegation": {
          const to = crewOf(e.to_agent);
          const task = e.text.replace(/^\S+ -> \S+: /, "");
          if (e.ok === false) out.push({ ...base, kind: "warn", text: e.text });
          else {
            out.push({ ...base, kind: "dispatch", to: e.to_agent, text: task || e.text });
            if (to) goTo(to.id);
            beep = true;
          }
          break;
        }
        case "tool_call":
          if (e.tool === "delegate") break;
          out.push({ ...base, kind: "tool", tool: e.tool, text: e.text.replace(/^.*? called /, "") });
          if (a) {
            setCrew((s) => ({ ...s, [a]: { ...s[a], state: "active", tools: s[a].tools + 1 } }));
            setActiveAgent(a);
            goTo(a);
          }
          break;
        case "tool_result":
          if (e.tool !== "delegate") out.push({ ...base, kind: "result", text: clip(e.text, 280) });
          break;
        case "model_text":
          out.push({ ...base, kind: "speech", text: e.text });
          if (a) setBubbles((b) => ({ ...b, [CREW[a].base]: clip(e.text, 90) }));
          beep = true;
          break;
        case "agent_output":
          out.push({ ...base, kind: "report", text: e.text });
          if (a) {
            setCrew((s) => ({ ...s, [a]: { ...s[a], state: "done", last: e.text } }));
            setBubbles((b) => ({ ...b, [CREW[a].base]: clip(e.text.replace(/^\[\w+\]\s*/, ""), 90) }));
          }
          beep = true;
          break;
        case "retry":
        case "limit_hit":
        case "error":
          out.push({ ...base, kind: "warn", text: e.text });
          break;
        case "run_end":
          out.push({ ...base, kind: "system", text: e.text });
          break;
        case "human_approval":
        case "human_rejection":
          out.push({ ...base, kind: "human", text: e.text });
          break;
      }
    }
    addLines(out);
    if (beep) playRadio();
  }, [addLines, goTo]);

  // ---------- finishing a run: drive the result back to the job, then party ----------
  const fireFinish = useCallback(() => {
    const f = finishing.current;
    if (!f || f.fired) return;
    f.fired = true;
    const run = f.run;
    const res = run.result?.resolution;
    const t = tickets?.find((x) => x.id === f.ticketId);
    const meta = t ? jobMeta(t) : null;
    setBubbles({});
    setActiveAgent(null);
    if (run.status === "done" && res?.status === "resolved") {
      const queued = res.payment_requests.reduce((s, p) => s + p.amount, 0);
      const crewUsed = Array.from(new Set<AgentName>(["boss", ...(run.result?.delegations.map((d) => d.to_agent) ?? [])]));
      setParty({
        ticketId: f.ticketId,
        title: "JOB COMPLETE",
        subtitle: `${meta?.icon ?? ""} Job #${f.ticketId} · ${meta?.name ?? ""}`,
        stats: [
          `⏱ ${run.duration_s ?? "?"}s`,
          `👥 ${crewUsed.length} crew`,
          `🔧 ${run.result?.usage.tool_calls ?? 0} tool calls`,
          queued ? `💳 ${fmt(queued)} awaiting your OK` : "💳 no money needed",
        ],
        crew: crewUsed,
      });
      scene.current?.celebrate();
      playFanfare();
    } else {
      setDebrief(run);
      toast(run.status === "error" ? `Job #${f.ticketId} crashed: ${run.error}` : `Job #${f.ticketId} needs your call.`, "bad");
    }
  }, [tickets, toast]);

  const onArrive = useCallback((place: string) => {
    setArrivedAt(place);
    if (finishing.current && finishing.current.location === place) fireFinish();
  }, [fireFinish]);

  // ---------- polling while a run is live ----------
  useEffect(() => {
    if (runningId === null) return;
    let stop = false;
    const id = runningId;
    const tick = async () => {
      try {
        const ev = await api.events({ ticket_id: id, after: cursor.current, limit: 1000 });
        cursor.current = ev.last_seq;
        handleEvents(ev.events);
        const run = await api.run(id).catch(() => null);
        if (!stop && run && run.status !== "running") {
          stop = true;
          const last = await api.events({ ticket_id: id, after: cursor.current, limit: 1000 });
          cursor.current = last.last_seq;
          handleEvents(last.events);
          setRuns((r) => ({ ...r, [id]: run }));
          setRunningId(null);
          setCrew((s) => Object.fromEntries(CREW_ORDER.map((a) => [a, { ...s[a], state: s[a].state === "idle" ? "idle" : "done" }])) as Record<AgentName, CrewStatus>);
          await Promise.all([refreshTickets(), refreshMoney()]);
          const t = tickets?.find((x) => x.id === id);
          const location = t ? jobMeta(t).location : `t${id}`;
          finishing.current = { ticketId: id, run, location, fired: false };
          scene.current?.clearQueue();
          scene.current?.driveTo(location);
          setTimeout(() => {   // already parked there, or the drive takes too long: party anyway
            if (finishing.current?.ticketId === id) fireFinish();
          }, 9000);
        }
        setOffline(null);
      } catch (e) {
        setOffline(e instanceof ApiError ? e.message : String(e));
      }
    };
    void tick();
    const timer = setInterval(() => { if (!stop) void tick(); }, POLL_MS);
    return () => { stop = true; clearInterval(timer); };
  }, [runningId, handleEvents, refreshTickets, refreshMoney, tickets, fireFinish]);

  // ---------- user actions ----------
  const selectTicket = (id: number) => {
    setSelected(id);
    const t = tickets?.find((x) => x.id === id);
    if (t && runningId === null) scene.current?.driveTo(jobMeta(t).location);
  };

  const startJob = async (id: number) => {
    const t = tickets?.find((x) => x.id === id);
    if (!t) return;
    setSelected(id);
    setCrew(freshCrew());
    setBubbles({});
    setActiveAgent(null);
    finishing.current = null;
    setLines([{ key: `start-${Date.now()}`, agent: null, kind: "system", ts: new Date().toISOString(),
      text: `Dispatch: ${jobMeta(t).name} (job #${id}) accepted. Heading to HQ to brief ${CREW.boss.callsign}.` }]);
    scene.current?.driveTo(jobMeta(t).location);
    scene.current?.driveTo("hq");
    try {
      const ev = await api.events({ limit: 1 });
      cursor.current = ev.last_seq;
      await api.runTicket(id);
      setRunningId(id);
      playStart();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "bad");
    }
  };

  const approve = async (itemId: string) => {
    try {
      const r = await api.approve(itemId);
      playCash();
      toast(`Paid ${fmt(r.payment.amount)}. Checking is now ${fmt(r.payment.balance_after)}.`, "good");
      if (r.warning) toast(r.warning, "bad");
      addLines([{ key: `ap-${itemId}-${Date.now()}`, agent: null, kind: "human", ts: new Date().toISOString(),
        text: `You approved ${itemId}: ${fmt(r.payment.amount)} left checking.` }]);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "bad");
    }
    await refreshMoney().catch(() => undefined);
  };

  const reject = async (itemId: string) => {
    try {
      await api.reject(itemId);
      toast(`Declined ${itemId}. No money moved.`, "info");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "bad");
    }
    await refreshMoney().catch(() => undefined);
  };

  const resetWorld = async () => {
    if (runningId !== null) return toast("Wait for the crew to finish this job first.", "bad");
    if (!window.confirm("Reset the shop to its original data? Tickets reopen, cash goes back to the start, and the approval queue is cleared. The audit trail is kept.")) return;
    try {
      await api.reset();
      await Promise.all([refreshTickets(), refreshMoney()]);
      setRuns({});
      setCrew(freshCrew());
      setBubbles({});
      setSelected(null);
      setLines([{ key: `reset-${Date.now()}`, agent: null, kind: "system", ts: new Date().toISOString(),
        text: "New game: the shop is back to its original data. All three jobs are open." }]);
      scene.current?.clearQueue();
      scene.current?.driveTo("hq");
      toast("World reset. Fresh run ready.", "good");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "bad");
    }
  };

  const openDebrief = async (id: number) => {
    try {
      const r = runs[id] ?? (await api.run(id));
      setDebrief(r);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : String(e), "bad");
    }
  };

  // ---------- derived view state ----------
  const placeStates = useMemo(() => {
    const st: Record<string, PlaceState> = {};
    CREW_ORDER.forEach((a) => {
      const base = CREW[a].base;
      st[base] = activeAgent === a ? "active" : crew[a].state !== "idle" ? "visited" : "idle";
    });
    tickets?.forEach((t) => {
      const loc = jobMeta(t).location;
      st[loc] = runningId === t.id ? "running" : t.status === "resolved" ? "resolved"
        : t.last_run?.final_status === "needs_human" ? "needs" : selected === t.id ? "selected" : "open";
    });
    return st;
  }, [activeAgent, crew, tickets, runningId, selected]);

  const pending = approvals.filter((a) => a.status === "pending");
  const objective = (() => {
    if (offline) return "Backend offline. Start uvicorn on port 8000.";
    if (runningId !== null) {
      const c = activeAgent ? CREW[activeAgent] : CREW.boss;
      return `Follow the crew: ${c.icon} ${c.callsign} is working job #${runningId}`;
    }
    if (pending.length) return `Sign off on ${pending.length} payment${pending.length > 1 ? "s" : ""} on your phone`;
    if (selected !== null) {
      const t = tickets?.find((x) => x.id === selected);
      if (t?.status === "resolved") return `Job #${selected} is closed. Pick another job.`;
      return `Job #${selected}: hit Start job to send the crew`;
    }
    if (tickets && tickets.every((t) => t.status === "resolved")) return "All jobs closed. Elm City thanks you. 🌴";
    return "Pick a job on the board";
  })();

  const destName = drive.dest ? (PLACES[drive.dest]?.label ?? drive.dest) : null;
  const selectedTicket = tickets?.find((t) => t.id === debrief?.ticket_id);

  return (
    <div className="app">
      <CityScene ref={scene} mode={cam} placeStates={placeStates} bubbles={bubbles} onArrive={onArrive}
                 onDriveState={setDrive}
                 onPlaceClick={(p) => {
                   const t = tickets?.find((x) => jobMeta(x).location === p);
                   if (t) selectTicket(t.id);
                 }} />

      <header className="topbar">
        <div className="brand">
          <div className="logo" aria-label="Elm City Nights">
            <span className="logo-top">ELM CITY</span>
            <span className="logo-bottom">NIGHTS</span>
          </div>
          <div className="brand-sub">
            <b>Campus Customs</b> desk ops
            <span className="date">📅 {today ? new Date(`${today}T12:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }).toUpperCase() : "…"}</span>
          </div>
        </div>
        <div className="controls">
          <span className={`net ${offline ? "down" : "up"}`} title={offline ?? `Connected to ${API_BASE}`}>
            <i aria-hidden="true" /> {offline ? "offline" : model || "online"}
          </span>
          <button type="button" className="btn btn-ghost" onClick={() => setCam(cam === "chase" ? "map" : "chase")}
                  aria-pressed={cam === "chase"} disabled={reduced} title={reduced ? "Reduced motion is on" : "Switch camera"}>
            🎥 {cam === "chase" ? "Chase cam" : "City view"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => { sound.set(!soundOn); setSoundOn(!soundOn); }}
                  aria-pressed={soundOn}>{soundOn ? "🔊 Sound on" : "🔈 Sound off"}</button>
          <button type="button" className="btn btn-warn" onClick={resetWorld} disabled={runningId !== null}>⟲ New game</button>
        </div>
        <CashHud cash={cash} error={!!offline} />
      </header>

      <div className="objective" role="status">
        <span className="obj-label">OBJECTIVE</span> {objective}
        {drive.driving && destName && (
          <span className={`gps ${drive.nitro ? "nitro" : ""}`}>📍 {clip(destName, 30)}{drive.nitro ? " · NITRO" : ""}</span>
        )}
      </div>

      {offline && (
        <div className="offline" role="alert">
          <b>Can't reach the backend.</b> {offline} Start it from <code>backend/</code> with
          <code>uvicorn main:app --reload --port 8000</code>, then refresh.
        </div>
      )}

      <aside className="col-left">
        <JobsBoard tickets={tickets} selected={selected} runningId={runningId} arrivedAt={arrivedAt}
                   onSelect={selectTicket} onStart={startJob} onDebrief={openDebrief} />
      </aside>

      <aside className="col-right">
        <CrewRoster status={crew} activeAgent={activeAgent} />
        <CrewRadio lines={lines} running={runningId !== null} />
      </aside>

      <ApprovalPhone items={approvals} balance={cash?.balance ?? null} onApprove={approve} onReject={reject} />

      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}
      </div>

      {party && (
        <Celebration title={party.title} subtitle={party.subtitle} stats={party.stats} crew={party.crew}
                     onDone={() => {
                       const id = party.ticketId;
                       setParty(null);
                       finishing.current = null;
                       const r = runs[id];
                       if (r) setDebrief(r);
                     }} />
      )}
      {debrief && <Debrief run={debrief} ticket={selectedTicket ?? tickets?.find((t) => t.id === debrief.ticket_id)} onClose={() => setDebrief(null)} />}
    </div>
  );
}
