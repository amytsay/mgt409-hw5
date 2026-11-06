// Left panel: the three desk tickets as "jobs". Pick one to drive there, then start the crew on it.
import { jobMeta } from "../crew";
import type { Ticket } from "../types";

interface Props {
  tickets: Ticket[] | null;
  selected: number | null;
  runningId: number | null;
  arrivedAt: string | null;
  onSelect: (id: number) => void;
  onStart: (id: number) => void;
  onDebrief: (id: number) => void;
}

function statusOf(t: Ticket, runningId: number | null) {
  if (runningId === t.id) return { label: "IN PROGRESS", cls: "running" };
  if (t.status === "resolved") return { label: "RESOLVED", cls: "resolved" };
  if (t.last_run?.final_status === "needs_human") return { label: "NEEDS YOU", cls: "needs" };
  if (t.last_run?.status === "error") return { label: "CRASHED", cls: "error" };
  return { label: "OPEN", cls: "open" };
}

export function JobsBoard({ tickets, selected, runningId, arrivedAt, onSelect, onStart, onDebrief }: Props) {
  return (
    <section className="panel jobs" aria-labelledby="jobs-title">
      <header className="panel-head">
        <h2 id="jobs-title">Jobs</h2>
        <span className="panel-sub">
          {tickets ? `${tickets.filter((t) => t.status === "resolved").length} / ${tickets.length} done` : "…"}
        </span>
      </header>
      {!tickets && <div className="skeleton-list">{[0, 1, 2].map((i) => <div key={i} className="skeleton" />)}</div>}
      <ol className="job-list">
        {tickets?.map((t) => {
          const meta = jobMeta(t);
          const st = statusOf(t, runningId);
          const isSel = selected === t.id;
          const here = arrivedAt === meta.location;
          const canStart = runningId === null && t.status !== "resolved";
          return (
            <li key={t.id} className={`job-card st-${st.cls} ${isSel ? "selected" : ""}`}>
              <button type="button" className="job-main" onClick={() => onSelect(t.id)} aria-pressed={isSel}
                      aria-label={`Job ${t.id}, ${meta.name}: ${t.subject}. Status ${st.label}. Drive here.`}>
                <span className="job-icon" aria-hidden="true">{meta.icon}</span>
                <span className="job-text">
                  <span className="job-name">#{t.id} · {meta.name}</span>
                  <span className="job-subject">{t.subject} <em>· {t.requester}</em></span>
                  <span className="job-blurb">{meta.blurb}</span>
                </span>
                <span className={`pill ${st.cls}`}>{st.label}</span>
              </button>
              {isSel && (
                <div className="job-actions">
                  <button type="button" className="btn btn-go" disabled={!canStart} onClick={() => onStart(t.id)}>
                    {runningId === t.id ? "Crew is rolling…" : t.status === "resolved" ? "Job closed" : here ? "▶ Start job" : "▶ Start job (drive + dispatch)"}
                  </button>
                  {t.last_run && t.last_run.status !== "running" && (
                    <button type="button" className="btn btn-ghost" onClick={() => onDebrief(t.id)}>Debrief</button>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="hint">Pick a job to drive there. Starting it sends the Boss out, and the car follows every hand-off.</p>
    </section>
  );
}
