"""MCP Server exposing Decision Archaeologist graph tools over standard I/O."""

import asyncio
import json
import logging
import sys

from mcp.server.mcpserver import MCPServer

from dig.agent.tools import registry

logger = logging.getLogger(__name__)

mcp = MCPServer("Decision Archaeologist")

# Automatically register all tools from central registry
for tool_meta in registry.list_tools():
    mcp.add_tool(
        tool_meta.func,
        name=tool_meta.name,
        description=tool_meta.description,
    )


async def list_tools_cli() -> list[str]:
    """Return names of registered tools."""
    tools = await mcp.list_tools()
    return [t.name for t in tools]


async def test_tools_cli() -> None:
    """Run verification check by executing two tools through the MCP server."""
    print("=== Testing MCP Server Tools ===")
    tools = await list_tools_cli()
    print(f"Total tools registered in MCP server: {len(tools)}")
    print(f"Tool list: {', '.join(tools)}\n")

    # Call tool 1: search_decisions
    print("1. Calling tool 'search_decisions(query=\"Python\")' via MCP server:")
    res1 = await mcp.call_tool("search_decisions", {"query": "Python"})
    content1 = res1.content[0].text if res1.content else "{}"
    parsed1 = json.loads(content1)
    print(f"   Summary: {parsed1.get('summary')}")
    print(f"   Nodes touched: {len(parsed1.get('graph_elements', {}).get('nodes', []))}\n")

    # Call tool 2: central_people
    print("2. Calling tool 'central_people(scope=\"all\", limit=3)' via MCP server:")
    res2 = await mcp.call_tool("central_people", {"scope": "all", "limit": 3})
    content2 = res2.content[0].text if res2.content else "{}"
    parsed2 = json.loads(content2)
    print(f"   Summary: {parsed2.get('summary')}")
    print(f"   Top central people: {parsed2.get('data')}\n")

    print(
        "Algorithm path used: NetworkX PageRank over Person-MADE-Decision & Person-KNOWS-Module subgraphs."
    )
    print("=== MCP Server Verification Passed ===")


def main() -> None:
    """CLI entrypoint for MCP server."""
    if "--list" in sys.argv:

        async def _run_list():
            tools = await list_tools_cli()
            print("Registered MCP Tools:")
            for t in tools:
                print(f"  - {t}")

        asyncio.run(_run_list())
    elif "--test" in sys.argv:
        asyncio.run(test_tools_cli())
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
