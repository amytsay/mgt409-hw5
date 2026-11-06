"""Runs the agent team on one desk ticket: Boss first, specialists via delegation, every loop step audited.

    python team.py 102          # from backend/: run ticket 102 and print the result as JSON

Limits (guardrails.py) are per ticket: one shared usage counter (model calls, tool calls, tokens) across every
agent, plus caps on agent runs, delegation depth, delegations per run, steps per agent and wall-clock time.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.usage import RunUsage

import guardrails as g
from agents import AGENTS, CUSTOMER_TICKET_TYPES
from audit import AuditTrail
from mcp_client import SHOP_MCP
from models import AgentName, AgentReport, Delegation, TeamDeps, TicketResolution
import settings


class StepLimitExceeded(RuntimeError):
    pass


def _tokens(u: RunUsage) -> dict[str, int]:
    return {"requests": u.requests, "tool_calls": u.tool_calls,
            "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}


async def run_agent(name: AgentName, task: str, deps: TeamDeps, usage: RunUsage) -> AgentReport | TicketResolution:
    """One agent's loop, step by step. Every step is written to the audit trail."""
    a, budget = deps.audit, deps.budget
    rec = lambda event, **kw: a.record(event, run_id=deps.run_id, ticket_id=deps.ticket_id, agent=name, **kw)

    budget.agent_runs += 1
    if deps.depth > 0:
        budget.delegations.append(Delegation(from_agent=deps.chain[-2], to_agent=name, task=task, depth=deps.depth))
        a.record("delegation", run_id=deps.run_id, ticket_id=deps.ticket_id, agent=deps.chain[-2],
                 to_agent=name, task=task, depth=deps.depth, ok=True)
    rec("agent_start", depth=deps.depth, chain=" -> ".join(deps.chain), task=task, agent_run=budget.agent_runs)

    steps = 0
    async with AGENTS[name].iter(task, deps=deps, usage=usage, usage_limits=g.TICKET_LIMITS) as run:
        async for node in run:
            steps += 1
            if steps > g.MAX_STEPS_PER_AGENT:
                rec("limit_hit", limit="MAX_STEPS_PER_AGENT", steps=steps)
                raise StepLimitExceeded(f"{name} exceeded {g.MAX_STEPS_PER_AGENT} loop steps")
            if Agent.is_model_request_node(node):
                for part in node.request.parts:
                    if isinstance(part, ToolReturnPart) and not part.tool_name.startswith("final_result"):
                        budget.seen_numbers |= g.numbers_in(part.content)
                        rec("tool_result", step=steps, tool=part.tool_name, result=part.content)
                    elif isinstance(part, RetryPromptPart):
                        rec("retry", step=steps, tool=part.tool_name, reason=part.content)
            elif Agent.is_call_tools_node(node):
                for part in node.model_response.parts:
                    if isinstance(part, ToolCallPart) and not part.tool_name.startswith("final_result"):
                        rec("tool_call", step=steps, tool=part.tool_name, args=part.args_as_dict(),
                            via="mcp" if part.tool_name != "delegate" else "team")
                    elif isinstance(part, TextPart) and part.content.strip():
                        rec("model_text", step=steps, text=part.content)
                rec("model_step", step=steps, **_tokens(usage))
        output = run.result.output

    rec("agent_output", output=output.model_dump())
    rec("agent_end", steps=steps, **_tokens(usage))
    if isinstance(output, AgentReport):
        budget.reports.append(output)
    return output


def private_names_for(ticket: dict) -> tuple[str, ...]:
    """Client names to mask in the audit trail: the full requester name, plus the first name of a person."""
    if ticket.get("type") not in CUSTOMER_TICKET_TYPES or not ticket.get("requester"):
        return ()
    name = ticket["requester"]
    return (name, name.split()[0]) if ticket["type"] == "customer_order" else (name,)


async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Run the whole team on one ticket. Always appends run_start ... run_end to the audit trail."""
    started = time.monotonic()
    usage = RunUsage()
    async with SHOP_MCP:   # one MCP server process for the whole ticket; every agent shares it
        meta = await SHOP_MCP.direct_call_tool("get_ticket", {"ticket_id": ticket_id})
        if not isinstance(meta, dict) or "ticket" not in meta:
            raise ValueError(f"Ticket {ticket_id} not found: {meta}")
        ticket = meta["ticket"]
        private = private_names_for(ticket)
        audit = AuditTrail(private_names=private)
        deps = TeamDeps(ticket_id=ticket_id, audit=audit, ticket_type=ticket["type"], private_names=private)
        audit.record("run_start", run_id=deps.run_id, ticket_id=ticket_id, agent="team",
                     ticket_type=ticket["type"], subject=ticket["subject"], model=settings.MODEL_NAME,
                     shop_today=meta.get("today"),
                     limits={"request_limit": g.TICKET_LIMITS.request_limit,
                             "tool_calls_limit": g.TICKET_LIMITS.tool_calls_limit,
                             "total_tokens_limit": g.TICKET_LIMITS.total_tokens_limit,
                             "max_agent_runs": g.MAX_AGENT_RUNS, "max_depth": g.MAX_DEPTH,
                             "max_delegations_per_run": g.MAX_DELEGATIONS_PER_RUN,
                             "max_steps_per_agent": g.MAX_STEPS_PER_AGENT, "timeout_s": g.TICKET_TIMEOUT_S})
        task = (f"Work desk ticket {ticket_id}. Read it with get_ticket, route it to the right specialists, apply "
                f"your limits, mark it resolved if appropriate, and return the TicketResolution.")
        resolution, stop, error = None, "completed", None
        try:
            resolution = await asyncio.wait_for(run_agent("boss", task, deps, usage), g.TICKET_TIMEOUT_S)
        except UsageLimitExceeded as e:
            stop, error = "usage_limit", str(e)
        except StepLimitExceeded as e:
            stop, error = "step_limit", str(e)
        except asyncio.TimeoutError:
            stop, error = "timeout", f"ticket exceeded {g.TICKET_TIMEOUT_S}s"
        except Exception as e:  # noqa: BLE001 - recorded, then re-raised below
            stop, error = "error", f"{type(e).__name__}: {e}"
        if error:
            audit.record("limit_hit" if stop != "error" else "error", run_id=deps.run_id, ticket_id=ticket_id,
                         agent="team", stop_reason=stop, detail=error)
        audit.record("run_end", run_id=deps.run_id, ticket_id=ticket_id, agent="team", stop_reason=stop,
                     duration_s=round(time.monotonic() - started, 1), agent_runs=deps.budget.agent_runs,
                     delegations=len(deps.budget.delegations), **_tokens(usage),
                     final_status=resolution.status if resolution else None)

    return {
        "run_id": deps.run_id, "ticket_id": ticket_id, "stop_reason": stop, "error": error,
        "resolution": resolution.model_dump() if resolution else None,
        "delegations": [d.__dict__ for d in deps.budget.delegations],
        "reports": [r.model_dump() for r in deps.budget.reports],
        "usage": _tokens(usage), "agent_runs": deps.budget.agent_runs,
    }


if __name__ == "__main__":
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else 102
    print(json.dumps(asyncio.run(run_ticket(tid)), indent=2, default=str))
