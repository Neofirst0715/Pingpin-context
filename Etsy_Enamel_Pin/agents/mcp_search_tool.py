import os
import asyncio
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient

async def _call_dashscope_websearch(query: str) -> str:
    client = MultiServerMCPClient({
        "dashscope_websearch": {
            "url": "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp",
            "transport": "http",
            "headers": {
                "Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"
            }
        }
    })
    tools = await client.get_tools()
    search_tool = next(t for t in tools if "search" in t.name.lower())
    result = await search_tool.ainvoke({"query": query})
    return str(result)

@tool
def dashscope_web_search(query: str) -> str:
    """Search the web in real time via DashScope's hosted MCP WebSearch service.
    Use this for current Etsy policy updates or live market/trend information
    that would not be present in static local documents."""
    return asyncio.run(_call_dashscope_websearch(query))
