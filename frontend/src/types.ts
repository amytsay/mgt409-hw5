// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = "boss" | "inventory" | "accounting" | "facilities" | "customer_service";

export interface LastRun {
  status: "running" | "done" | "error" | null;
  run_id?: string | null;
  stop_reason?: string | null;
  final_status?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface Ticket {
  id: number;
  type: "customer_order" | "rent_notice" | "price_override" | string;
  requester: string;
  subject: string;
  status: "open" | "resolved" | string;
  created_at: string;
  last_run: LastRun | null;
}

export interface TicketsResponse {
  today: string;
  tickets: Ticket[];
  counts: { open: number; resolved: number };
}

export interface AgentEvent {
  seq: number;
  ts: string;
  run_id: string;
  ticket_id: number;
  agent: string | null;
  event: string;
  text: string;
  tool?: string;
  to_agent?: string;
  ok?: boolean;
  stop_reason?: string;
  final_status?: string;
}

export interface EventsResponse {
  events: AgentEvent[];
  last_seq: number;
  running_ticket: number | null;
}

export interface PaymentRequest {
  kind: "invoice" | "rent" | "purchase";
  ref_id: number;
  payee: string;
  amount: number;
  description: string;
  due_date?: string | null;
  overdue?: boolean;
  low_cash_flag?: boolean;
  priority?: "urgent" | "normal" | "defer";
  reason?: string;
}

export interface AgentReport {
  agent: AgentName;
  summary: string;
  facts: string[];
  actions: string[];
  payment_requests: PaymentRequest[];
  customer_message?: string | null;
  needs_boss_decision?: string | null;
  risks?: string[] | string | null;
}

export interface AgentContribution {
  agent: AgentName;
  contribution: string;
}

export interface TicketResolution {
  ticket_id: number;
  status: "resolved" | "needs_human";
  outcome: string;
  decisions: string[];
  agent_contributions: (AgentContribution | string)[];
  payment_requests: PaymentRequest[];
  customer_reply?: string | null;
  human_approvals_needed: string[];
}

export interface RunResult {
  run_id: string;
  ticket_id: number;
  stop_reason: string;
  error: string | null;
  resolution: TicketResolution | null;
  delegations: { from_agent: AgentName; to_agent: AgentName; task: string; depth: number }[];
  reports: AgentReport[];
  usage: { requests: number; tool_calls: number; input_tokens: number; output_tokens: number };
  agent_runs: number;
}

export interface RunState {
  ticket_id: number;
  status: "running" | "done" | "error";
  started_at: string;
  finished_at?: string;
  duration_s?: number;
  run_id?: string;
  stop_reason?: string;
  final_status?: string | null;
  queued_for_approval?: number;
  error?: string;
  result?: RunResult;
}

export interface ApprovalItem {
  id: string;
  status: "pending" | "approved" | "rejected";
  kind: "invoice" | "rent" | "purchase";
  ref_id: number;
  payee: string;
  amount: number;
  description: string | null;
  due_date: string | null;
  overdue: boolean;
  low_cash_flag: boolean;
  priority: "urgent" | "normal" | "defer";
  reason: string | null;
  ticket_id: number;
  decided_by?: string;
}

export interface ApprovalsResponse {
  items: ApprovalItem[];
  pending_count: number;
  pending_total: number;
}

export interface UnpaidBill {
  kind: string;
  ref_id: number;
  payee: string;
  description: string;
  amount: number;
  due_date: string;
  overdue: boolean;
  days_overdue: number;
  days_until_due: number;
}

export interface CashResponse {
  today: string;
  account: string;
  balance: number;
  balance_as_of: string;
  unpaid_bills: UnpaidBill[];
  total_owed: number;
  cash_after_all_bills: number;
  recent_payments: { id: number; kind: string; ref_id: number; amount: number; paid_at: string; approved_by: string }[];
}
