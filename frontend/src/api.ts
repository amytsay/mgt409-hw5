// Thin client for the FastAPI backend. The dashboard talks ONLY to these routes.
import type {
  ApprovalsResponse, CashResponse, EventsResponse, RunState, TicketsResponse,
} from "./types";

// Backend link: http://localhost:8000 (override with VITE_API_BASE in frontend/.env).
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; model: string; shop_today: string; running_ticket: number | null }>("/api/health"),
  tickets: () => call<TicketsResponse>("/api/tickets"),
  runTicket: (id: number) => call<RunState>(`/api/tickets/${id}/run`, { method: "POST" }),
  run: (id: number) => call<RunState>(`/api/runs/${id}`),
  events: (q: { ticket_id?: number; after?: number; limit?: number }) => {
    const p = new URLSearchParams();
    Object.entries(q).forEach(([k, v]) => v !== undefined && p.set(k, String(v)));
    return call<EventsResponse>(`/api/events?${p}`);
  },
  approvals: () => call<ApprovalsResponse>("/api/approvals"),
  approve: (id: string) =>
    call<{ payment: { amount: number; balance_before: number; balance_after: number }; warning: string | null }>(
      `/api/approvals/${encodeURIComponent(id)}/approve`,
      { method: "POST", body: JSON.stringify({ approved_by: "Owner" }) },
    ),
  reject: (id: string) =>
    call<unknown>(`/api/approvals/${encodeURIComponent(id)}/reject`, {
      method: "POST", body: JSON.stringify({ approved_by: "Owner" }),
    }),
  cash: () => call<CashResponse>("/api/cash"),
  reset: () => call<{ reset: boolean; balance: number }>("/api/reset", { method: "POST" }),
};
