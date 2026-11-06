// Top-right money counter: the checking balance from cash_accounts. Counts down when a payment is approved.
import { useEffect, useRef, useState } from "react";
import type { CashResponse } from "../types";

const fmt = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });

export function CashHud({ cash, error }: { cash: CashResponse | null; error: boolean }) {
  const [shown, setShown] = useState<number | null>(null);
  const [deltas, setDeltas] = useState<{ id: number; amount: number }[]>([]);
  const prev = useRef<number | null>(null);

  useEffect(() => {
    if (!cash) return;
    const from = prev.current ?? cash.balance;
    const to = cash.balance;
    prev.current = to;
    if (from !== to) {
      const id = Date.now();
      setDeltas((d) => [...d, { id, amount: to - from }]);
      setTimeout(() => setDeltas((d) => d.filter((x) => x.id !== id)), 2600);
    }
    const t0 = performance.now();
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / 1400);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(from + (to - from) * e);
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [cash]);

  const low = cash ? cash.balance < cash.total_owed : false;
  return (
    <section className={`cash-hud ${low ? "low" : ""}`} aria-label="Checking balance">
      <div className="cash-label">CHECKING <span>{cash?.account ?? "****"}</span></div>
      <div className="cash-amount" aria-live="polite">
        {error ? "—" : shown === null ? "$ · · ·" : fmt(shown)}
        {deltas.map((d) => (
          <span key={d.id} className={`cash-delta ${d.amount < 0 ? "down" : "up"}`}>
            {d.amount < 0 ? "−" : "+"}{fmt(Math.abs(d.amount))}
          </span>
        ))}
      </div>
      {cash && (
        <div className="cash-sub">
          Owed {fmt(cash.total_owed)} · after all bills <b className={cash.cash_after_all_bills < 0 ? "neg" : ""}>{fmt(cash.cash_after_all_bills)}</b>
        </div>
      )}
    </section>
  );
}
