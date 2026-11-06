// Right panel: the crew roster (who's active) and the live crew radio (what each agent says and does).
import { useEffect, useRef, useState } from "react";
import { CREW, CREW_ORDER, crewOf } from "../crew";
import type { AgentName } from "../types";

export type LineKind = "speech" | "report" | "tool" | "result" | "dispatch" | "system" | "warn" | "human";

export interface RadioLine {
  key: string;
  agent: string | null;
  kind: LineKind;
  text: string;
  tool?: string;
  to?: string;
  ts: string;
}

export interface CrewStatus {
  state: "idle" | "active" | "done";
  tools: number;
  last?: string;
}

interface Props {
  lines: RadioLine[];
  status: Record<AgentName, CrewStatus>;
  running: boolean;
  activeAgent: AgentName | null;
}

const time = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

export function CrewRoster({ status, activeAgent }: Pick<Props, "status" | "activeAgent">) {
  return (
    <ul className="roster" aria-label="Crew">
      {CREW_ORDER.map((id) => {
        const c = CREW[id];
        const s = status[id];
        return (
          <li key={id} className={`crew-chip st-${s.state} ${activeAgent === id ? "talking" : ""}`}
              style={{ "--c": c.color } as React.CSSProperties} title={`${c.role}: ${c.tagline}`}>
            <span className="crew-avatar" aria-hidden="true">{c.icon}</span>
            <span className="crew-id">
              <b>{c.callsign}</b>
              <small>{c.role}</small>
            </span>
            <span className="crew-state">
              {s.state === "active" ? "ON AIR" : s.state === "done" ? `✓ ${s.tools} tools` : "standby"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function CrewRadio({ lines, running }: Pick<Props, "lines" | "running">) {
  const box = useRef<HTMLOListElement>(null);
  const [showData, setShowData] = useState(false);
  const [stick, setStick] = useState(true);

  useEffect(() => {
    if (stick && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines, stick, showData]);

  const visible = showData ? lines : lines.filter((l) => l.kind !== "result");

  return (
    <section className="panel radio" aria-labelledby="radio-title">
      <header className="panel-head">
        <h2 id="radio-title"><span className={`rec ${running ? "on" : ""}`} aria-hidden="true" /> Crew radio</h2>
        <label className="toggle">
          <input type="checkbox" checked={showData} onChange={(e) => setShowData(e.target.checked)} /> tool data
        </label>
      </header>
      <ol className="radio-feed" ref={box} aria-live="polite" aria-relevant="additions"
          onScroll={(e) => {
            const el = e.currentTarget;
            setStick(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
          }}>
        {visible.length === 0 && (
          <li className="radio-empty">
            Radio is quiet. Pick a job and hit <b>Start job</b>. You'll hear the Boss dispatch the crew here.
          </li>
        )}
        {visible.map((l) => {
          const c = crewOf(l.agent);
          const to = crewOf(l.to);
          return (
            <li key={l.key} className={`line kind-${l.kind} ${c ? c.voice : "voice-system"}`}
                style={{ "--c": c?.color ?? "#b9b2d0" } as React.CSSProperties}>
              <div className="line-head">
                <span className="who">{c ? `${c.icon} ${c.callsign}` : l.kind === "human" ? "🧑 YOU" : "📡 DISPATCH"}</span>
                {l.kind === "dispatch" && to && <span className="to">➜ {to.icon} {to.callsign}</span>}
                {l.kind === "report" && <span className="tag">REPORT</span>}
                <time>{time(l.ts)}</time>
              </div>
              {l.kind === "tool" ? (
                <div className="tool-chip"><span>{c?.icon ?? "🔧"} {c?.callsign} · {l.tool}</span><code>{l.text}</code></div>
              ) : (
                <p>{l.text}</p>
              )}
            </li>
          );
        })}
      </ol>
      {!stick && (
        <button type="button" className="btn btn-ghost jump" onClick={() => setStick(true)}>↓ Latest</button>
      )}
    </section>
  );
}
