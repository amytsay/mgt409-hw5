// The "incoming call": payments and purchases the crew prepared. Only a human tap here moves cash.
import { useState } from "react";
import { CREW } from "../crew";
import type { ApprovalItem } from "../types";

const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
const KIND: Record<string, string> = { invoice: "Vendor invoice", rent: "Rent", purchase: "Restock purchase" };

interface Props {
  items: ApprovalItem[];
  balance: number | null;
  onApprove: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
}

export function ApprovalPhone({ items, balance, onApprove, onReject }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [open, setOpen] = useState(true);
  const pending = items.filter((i) => i.status === "pending");
  if (pending.length === 0) return null;
  const total = pending.reduce((s, i) => s + i.amount, 0);

  const act = async (id: string, fn: (id: string) => Promise<void>) => {
    setBusy(id);
    try { await fn(id); } finally { setBusy(null); }
  };

  if (!open) {
    return (
      <button type="button" className="phone-mini" onClick={() => setOpen(true)} aria-label={`${pending.length} payments waiting for your approval`}>
        📱 <b>{pending.length}</b> waiting on you
      </button>
    );
  }

  return (
    <aside className="phone" role="dialog" aria-label="Payments waiting for your approval">
      <div className="phone-notch" aria-hidden="true" />
      <header className="phone-head">
        <span className="ring" aria-hidden="true">📞</span>
        <div>
          <b>Incoming: {CREW.accounting.icon} {CREW.accounting.callsign}</b>
          <small>{pending.length} sign-off{pending.length > 1 ? "s" : ""} needed · {fmt(total)}</small>
        </div>
        <button type="button" className="phone-close" onClick={() => setOpen(false)} aria-label="Minimize">—</button>
      </header>
      <ul className="phone-list">
        {pending.map((i) => {
          const tooMuch = balance !== null && i.amount > balance;
          return (
            <li key={i.id} className={`pay-card prio-${i.priority} ${i.low_cash_flag ? "lowcash" : ""}`}>
              <div className="pay-top">
                <span className="pay-kind">{KIND[i.kind] ?? i.kind} · job #{i.ticket_id}</span>
                <span className={`prio ${i.priority}`}>{i.priority.toUpperCase()}</span>
              </div>
              <div className="pay-amount">{fmt(i.amount)}</div>
              <div className="pay-payee">to <b>{i.payee}</b>{i.due_date ? ` · due ${i.due_date}` : ""}{i.overdue ? " · OVERDUE" : ""}</div>
              {i.description && <div className="pay-desc">{i.description}</div>}
              {i.low_cash_flag && <div className="pay-warn">⚠ Low cash: paying this leaves less than the other bills owed.</div>}
              {tooMuch && <div className="pay-warn">⛔ More than the checking balance.</div>}
              {i.reason && <details><summary>Why the crew wants this</summary><p>{i.reason}</p></details>}
              <div className="pay-actions">
                <button type="button" className="btn btn-approve" disabled={busy !== null || tooMuch}
                        onClick={() => act(i.id, onApprove)}>
                  {busy === i.id ? "Paying…" : `Approve ${fmt(i.amount)}`}
                </button>
                <button type="button" className="btn btn-decline" disabled={busy !== null}
                        onClick={() => act(i.id, onReject)}>Decline</button>
              </div>
            </li>
          );
        })}
      </ul>
      <footer className="phone-foot">Agents only prepare payments. Nothing moves until you tap Approve.</footer>
    </aside>
  );
}
