"""Data types for the Campus Customs agent team (HW5 Problem 5).

Structured outputs: specialists return AgentReport, the Boss returns TicketResolution.
Run state shared by every agent working one ticket: TeamDeps (+ RunBudget for the loop limits).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from audit import AuditTrail

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_service")


# ---------- what agents hand back ----------

class PaymentRequest(BaseModel):
    """A payment or purchase an agent PREPARED with an MCP tool. Only a human approval moves the money."""
    kind: Literal["invoice", "rent", "purchase"]
    ref_id: int = Field(description="invoices.id for 'invoice', leases.id for 'rent', vendors.id for 'purchase'")
    payee: str
    amount: float = Field(description="Exact amount from the prepare_payment / prepare_restock_order tool output")
    description: str
    due_date: str | None = None
    overdue: bool = False
    low_cash_flag: bool = Field(False, description="Copied from the tool output")
    priority: Literal["urgent", "normal", "defer"] = "normal"
    reason: str = Field(description="Why this payment, why now, and which ticket it serves")


class PriceOverride(BaseModel):
    """A proposed price below list (ticket type price_override). Numbers come from quote_bulk_order."""
    sku: str
    qty: int
    list_price: float
    unit_cost: float
    proposed_unit_price: float
    discount_pct: float
    total: float
    within_boss_limit: bool = Field(description="True only if discount_pct <= 15 and price >= unit_cost")
    needs_human_approval: bool = True
    rationale: str


class AgentReport(BaseModel):
    """What a specialist (Inventory, Accounting, Facilities, Customer Service) reports back."""
    agent: AgentName
    summary: str = Field(description="2-4 sentences: what you found and what you did")
    facts: list[str] = Field(default_factory=list, description="Key facts with numbers, each from an MCP tool result")
    actions: list[str] = Field(default_factory=list, description="Tools called / work done, in order")
    payment_requests: list[PaymentRequest] = Field(default_factory=list)
    price_override: PriceOverride | None = None
    customer_message: str | None = Field(None, description="Customer Service only: the draft reply to the customer")
    needs_boss_decision: list[str] = Field(default_factory=list, description="Anything outside your limits")
    risks: list[str] = Field(default_factory=list)


class AgentContribution(BaseModel):
    agent: AgentName
    contribution: str


class TicketResolution(BaseModel):
    """The Boss's final answer for one ticket."""
    ticket_id: int
    status: Literal["resolved", "needs_human"] = Field(
        description="'resolved' when the work is done and any money is queued for human approval; "
                    "'needs_human' when a decision outside every agent's limits is still open")
    outcome: str = Field(description="3-5 sentences a manager can read: what happened and what is pending")
    decisions: list[str] = Field(default_factory=list, description="Each Boss decision and the rule behind it")
    agent_contributions: list[AgentContribution] = Field(default_factory=list)
    payment_requests: list[PaymentRequest] = Field(default_factory=list, description="Queued for human approval")
    price_override: PriceOverride | None = None
    customer_reply: str | None = Field(None, description="Final customer-facing message, if the ticket has a customer")
    human_approvals_needed: list[str] = Field(default_factory=list)


# ---------- run state ----------

@dataclass
class Delegation:
    from_agent: AgentName
    to_agent: AgentName
    task: str
    depth: int
    ok: bool = True
    note: str = ""


@dataclass
class RunBudget:
    """Shared by every agent on one ticket run, so the limits are per TICKET, not per agent."""
    agent_runs: int = 0
    delegations: list[Delegation] = field(default_factory=list)
    reports: list[AgentReport] = field(default_factory=list)
    seen_numbers: set[str] = field(default_factory=set)   # every number an MCP tool returned this run


@dataclass
class TeamDeps:
    ticket_id: int
    audit: "AuditTrail"
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    agent: AgentName = "boss"
    depth: int = 0
    chain: tuple[AgentName, ...] = ("boss",)
    budget: RunBudget = field(default_factory=RunBudget)
    ticket_type: str = ""                 # customer_order / rent_notice / price_override
    private_names: tuple[str, ...] = ()   # customer names to mask in the audit trail
    delegations_made: int = 0             # by THIS agent run (capped per run)

    def child(self, agent: AgentName) -> "TeamDeps":
        return TeamDeps(ticket_id=self.ticket_id, audit=self.audit, run_id=self.run_id, agent=agent,
                        depth=self.depth + 1, chain=self.chain + (agent,), budget=self.budget,
                        ticket_type=self.ticket_type, private_names=self.private_names)
