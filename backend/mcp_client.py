"""The agents' ONLY door to shop data: the campus-customs MCP server (mcp_server/server.py) over stdio.

There is no second shop-tools layer. Each agent sees a filtered view of the same MCP server
(least privilege): e.g. Customer Service has no cash tools, and only the Boss can set a ticket's status.
"""

from __future__ import annotations

import sys

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai.mcp import MCPToolset

import settings
from models import AgentName

SHOP_MCP = MCPToolset(
    Client(PythonStdioTransport(
        script_path=str(settings.MCP_SERVER_SCRIPT),
        python_cmd=sys.executable,
        cwd=str(settings.PROJECT_DIR),
    )),
    id="campus-customs",
    max_retries=1,
)

# Which MCP tools each agent may call.
TOOL_ACCESS: dict[AgentName, frozenset[str]] = {
    "boss": frozenset({"list_tickets", "get_ticket", "get_cash_position", "get_inventory_report",
                       "set_ticket_status"}),
    "inventory": frozenset({"get_ticket", "check_stock_for_order", "get_inventory_report",
                            "prepare_restock_order"}),
    "accounting": frozenset({"get_ticket", "get_cash_position", "prepare_payment", "prepare_restock_order",
                             "quote_bulk_order"}),
    "facilities": frozenset({"get_ticket", "get_lease", "prepare_payment"}),
    "customer_service": frozenset({"get_ticket", "check_stock_for_order", "quote_bulk_order"}),
}


def toolset_for(agent: AgentName):
    allowed = TOOL_ACCESS[agent]
    return SHOP_MCP.filtered(lambda ctx, tool_def: tool_def.name in allowed)
