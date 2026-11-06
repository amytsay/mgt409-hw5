// After a run: a short summary of what each agent did, the Boss's call, money queued and the customer reply.
import { useEffect, useRef } from "react";
import { CREW, CREW_ORDER, crewOf, jobMeta } from "../crew";
import type { AgentName, RunState, Ticket } from "../types";

const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export function Debrief({ run, ticket, onClose }: { run: RunState; ticket: Ticket | undefined; onClose: () => void }) {
  const closeBtn = useRef<HTMLButtonElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    closeBtn.current?.focus();
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close.current();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, []);

  const r = run.result;
  const res = r?.resolution ?? null;
  const meta = ticket ? jobMeta(ticket) : null;

  // One line per agent: the Boss's own words about each contribution, else the agent's report summary.
  const lines: Record<string, string[]> = {};
  res?.agent_contributions.forEach((c) => {
    if (typeof c === "string") return;
    (lines[c.agent] ??= []).push(c.contribution);
  });
  r?.reports.forEach((rep) => {
    if (!lines[rep.agent]?.length) (lines[rep.agent] ??= []).push(rep.summary);
  });
  if (res && !lines.boss?.length) lines.boss = [res.outcome];
  const worked = CREW_ORDER.filter((a) => lines[a]?.length);
  const toolCount = (a: AgentName) =>
    r?.reports.filter((x) => x.agent === a).reduce((n, x) => n + x.actions.length, 0) ?? 0;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="debrief" role="dialog" aria-modal="true" aria-labelledby="debrief-title" onClick={(e) => e.stopPropagation()}>
        <header className="debrief-head">
          <div>
            <span className="kicker">Crew debrief</span>
            <h2 id="debrief-title">{meta?.icon} Job #{run.ticket_id} · {meta?.name ?? "Job"}</h2>
          </div>
          <span className={`pill ${res?.status === "resolved" ? "resolved" : run.status === "error" ? "error" : "needs"}`}>
            {res?.status === "resolved" ? "RESOLVED" : run.status === "error" ? "CRASHED" : "NEEDS YOU"}
          </span>
        </header>

        {run.status === "error" && <p className="err">The run stopped: {run.error}</p>}
        {r && !res && <p className="err">Stopped early ({r.stop_reason}). {r.error}</p>}
        {res && <p className="outcome">{res.outcome}</p>}

        <div className="debrief-grid">
          {worked.map((a) => {
            const c = CREW[a];
            return (
              <article key={a} className={`agent-sum ${c.voice}`} style={{ "--c": c.color } as React.CSSProperties}>
                <h3><span aria-hidden="true">{c.icon}</span> {c.callsign} <small>{c.role}</small></h3>
                {lines[a].map((t, i) => <p key={i}>{t}</p>)}
                {a !== "boss" && <small className="muted">{toolCount(a)} tool steps reported</small>}
              </article>
            );
          })}
        </div>

        {r && r.delegations.length > 0 && (
          <div className="chain-row" aria-label="Delegation chain">
            <span className="chain-node" style={{ "--c": CREW.boss.color } as React.CSSProperties}>{CREW.boss.icon} {CREW.boss.callsign}</span>
            {r.delegations.map((d, i) => {
              const to = crewOf(d.to_agent);
              const from = crewOf(d.from_agent);
              return (
                <span key={i} className="chain-step">
                  <span className="arrow">{from && from.id !== "boss" ? `${from.callsign} ➜` : "➜"}</span>
                  <span className="chain-node" style={{ "--c": to?.color } as React.CSSProperties}>{to?.icon} {to?.callsign}</span>
                </span>
              );
            })}
          </div>
        )}

        {res && res.decisions.length > 0 && (
          <section>
            <h3 className="sec">Boss's calls</h3>
            <ul className="bullets">{res.decisions.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </section>
        )}

        {res && res.payment_requests.length > 0 && (
          <section>
            <h3 className="sec">Money queued for your approval</h3>
            <ul className="money">
              {res.payment_requests.map((p, i) => (
                <li key={i}>
                  <b>{fmt(p.amount)}</b> to {p.payee} <span className={`prio ${p.priority}`}>{p.priority}</span>
                  {p.low_cash_flag && <span className="prio defer">low cash</span>}
                  <small>{p.description}</small>
                </li>
              ))}
            </ul>
          </section>
        )}

        {res?.customer_reply && (
          <section>
            <h3 className="sec">Reply to the customer</h3>
            <div className="sms"><span>{res.customer_reply}</span></div>
          </section>
        )}

        {r && (
          <footer className="debrief-stats">
            <span>⏱ {run.duration_s ?? "?"}s</span>
            <span>🧠 {r.usage.requests} model calls</span>
            <span>🔧 {r.usage.tool_calls} tool calls</span>
            <span>👥 {r.agent_runs} agent runs</span>
            <span>🔤 {(r.usage.input_tokens + r.usage.output_tokens).toLocaleString()} tokens</span>
          </footer>
        )}
        <button type="button" ref={closeBtn} className="btn btn-go close" onClick={onClose}>Back to the streets</button>
      </div>
    </div>
  );
}
