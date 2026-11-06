"""The five Campus Customs agents (PydanticAI). Each has its own prompt file, the same model (gpt-6-luna via
Portkey), its own filtered view of the MCP server, and the `delegate` tool to hand work to any teammate.

    boss              prompts/boss.md              -> TicketResolution
    inventory         prompts/inventory.md         -> AgentReport
    accounting        prompts/accounting.md        -> AgentReport
    facilities        prompts/facilities.md        -> AgentReport
    customer_service  prompts/customer_service.md  -> AgentReport

The agent LOOP (model -> tools -> model ... -> answer) is run step by step in team.run_agent, which audits
every step and enforces the limits in guardrails.py.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext

import guardrails as g
import settings
from llm import MODEL_SETTINGS, build_model
from mcp_client import TOOL_ACCESS, toolset_for
from models import AGENT_NAMES, AgentName, AgentReport, TeamDeps, TicketResolution

CUSTOMER_TICKET_TYPES = {"customer_order", "price_override"}

ROLE_LINES = {
    "boss": "Boss: routes tickets, approves anything outside limits, monitors all activity, resolves tickets",
    "inventory": "Inventory: stock checks and audits, existing orders, restock plans and arrival dates",
    "accounting": "Accounting: cash, unpaid bills, preparing payments and purchases, budget and discount math",
    "facilities": "Facilities: lease and rent notices, verifying and preparing the rent payment",
    "customer_service": "Customer Service: accurate, private replies to customers on stock, timing and price",
}


def _load_prompt(name: AgentName) -> str:
    return (settings.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _run_context(ctx: RunContext[TeamDeps]) -> str:
    """Per-run instructions: which ticket, where this agent sits in the delegation chain, what is left."""
    d = ctx.deps
    others = "\n".join(f"- {ROLE_LINES[a]}" for a in AGENT_NAMES if a != d.agent)
    return (
        f"## This run\n"
        f"- Ticket: {d.ticket_id} (type: {d.ticket_type or 'unknown'}). Use the MCP tools for every fact.\n"
        f"- You are `{d.agent}`. Delegation chain so far: {' -> '.join(d.chain)} (depth {d.depth} of max {g.MAX_DEPTH}).\n"
        f"- Your MCP tools: {', '.join(sorted(TOOL_ACCESS[d.agent]))}. Plus `delegate(to_agent, task)`.\n"
        f"- Delegations left for you this run: {g.MAX_DELEGATIONS_PER_RUN - d.delegations_made}. "
        f"Agent runs used on this ticket: {d.budget.agent_runs} of {g.MAX_AGENT_RUNS}.\n"
        f"- Agents already in the chain are waiting on you. Report back to them instead of delegating to them.\n"
        f"## Teammates you can delegate to\n{others}"
    )


async def delegate(ctx: RunContext[TeamDeps], to_agent: AgentName, task: str) -> dict[str, Any]:
    """Hand a specific task to a teammate and get their report back.

    to_agent: one of boss, inventory, accounting, facilities, customer_service (not yourself).
    task: exactly what you need, with the SKU/size/qty, invoice or lease id, and amounts you already know.
    Returns the teammate's AgentReport (summary, facts, payment_requests, customer_message, needs_boss_decision).
    """
    from team import run_agent   # late import: team imports this module

    d = ctx.deps
    refusal = None
    if to_agent == d.agent:
        refusal = "You cannot delegate to yourself."
    elif to_agent in d.chain:
        refusal = (f"{to_agent} is already in this delegation chain ({' -> '.join(d.chain)}) and is waiting on you. "
                   "Put what you need from them in your report instead (needs_boss_decision / risks).")
    elif d.depth >= g.MAX_DEPTH:
        refusal = f"Max delegation depth {g.MAX_DEPTH} reached. Finish with the facts you have."
    elif d.delegations_made >= g.MAX_DELEGATIONS_PER_RUN:
        refusal = f"You have used all {g.MAX_DELEGATIONS_PER_RUN} delegations for this run. Finish now."
    elif d.budget.agent_runs >= g.MAX_AGENT_RUNS:
        refusal = f"This ticket has used all {g.MAX_AGENT_RUNS} agent runs. Finish with the facts you have."

    if refusal:
        d.audit.record("delegation", run_id=d.run_id, ticket_id=d.ticket_id, agent=d.agent,
                       to_agent=to_agent, task=task, ok=False, refused=refusal)
        return {"refused": refusal}

    d.delegations_made += 1
    report = (await run_agent(to_agent, task, d.child(to_agent), usage=ctx.usage)).model_dump()
    # Prepared drafts live only in reports (nothing is written to the DB until a human approves), so every
    # delegation result carries ALL drafts prepared so far on this ticket. Agents never lose or re-request one.
    report["all_prepared_requests_this_ticket"] = [p.model_dump() for p in prepared_requests(d)]
    return report


def prepared_requests(d: TeamDeps):
    """Every payment/purchase draft any agent prepared on this ticket, once per (kind, ref_id)."""
    seen, out = set(), []
    for r in d.budget.reports:
        for p in r.payment_requests:
            if (p.kind, p.ref_id) not in seen:
                seen.add((p.kind, p.ref_id))
                out.append(p)
    return out


def _check_payments(output, seen: set[str]) -> None:
    for p in output.payment_requests:
        if g.norm(p.amount) not in seen:
            raise ModelRetry(f"Payment request amount {p.amount} for {p.payee} was not returned by any MCP tool. "
                             "Use prepare_payment / prepare_restock_order and copy the exact amount.")


def _make_specialist(name: AgentName) -> Agent[TeamDeps, AgentReport]:
    agent = Agent(
        build_model(), name=name, deps_type=TeamDeps, output_type=AgentReport,
        instructions=[_load_prompt(name), _run_context],
        toolsets=[toolset_for(name)], tools=[delegate],
        model_settings=MODEL_SETTINGS, retries={"tools": 1, "output": g.OUTPUT_RETRIES}, tool_timeout=60,
    )

    @agent.output_validator
    def validate(ctx: RunContext[TeamDeps], out: AgentReport) -> AgentReport:
        seen = ctx.deps.budget.seen_numbers
        _check_payments(out, seen)
        if ctx.deps.ticket_type in CUSTOMER_TICKET_TYPES:
            problems = g.customer_message_problems(out.customer_message, seen)
            if problems:
                raise ModelRetry("customer_message can't go to the customer: " + "; ".join(problems))
        return out.model_copy(update={"agent": ctx.deps.agent})

    return agent


def _make_boss() -> Agent[TeamDeps, TicketResolution]:
    agent = Agent(
        build_model(), name="boss", deps_type=TeamDeps, output_type=TicketResolution,
        instructions=[_load_prompt("boss"), _run_context],
        toolsets=[toolset_for("boss")], tools=[delegate],
        model_settings=MODEL_SETTINGS, retries={"tools": 1, "output": g.OUTPUT_RETRIES}, tool_timeout=60,
    )

    @agent.output_validator
    def validate(ctx: RunContext[TeamDeps], out: TicketResolution) -> TicketResolution:
        seen = ctx.deps.budget.seen_numbers
        _check_payments(out, seen)
        if ctx.deps.ticket_type in CUSTOMER_TICKET_TYPES:
            problems = g.customer_message_problems(out.customer_reply, seen)
            if problems:
                raise ModelRetry("customer_reply can't go to the customer: " + "; ".join(problems))
        po = out.price_override
        if po and out.status == "resolved" and (po.discount_pct > g.BOSS_DISCOUNT_LIMIT_PCT
                                                or po.proposed_unit_price < po.unit_cost):
            raise ModelRetry(f"A {po.discount_pct}% discount (or a price below unit cost) is outside the Boss's "
                             f"{g.BOSS_DISCOUNT_LIMIT_PCT:g}% limit. Set status 'needs_human' and list it in "
                             "human_approvals_needed.")
        return out.model_copy(update={"ticket_id": ctx.deps.ticket_id})

    return agent


AGENTS: dict[AgentName, Agent] = {
    "boss": _make_boss(),
    "inventory": _make_specialist("inventory"),
    "accounting": _make_specialist("accounting"),
    "facilities": _make_specialist("facilities"),
    "customer_service": _make_specialist("customer_service"),
}
