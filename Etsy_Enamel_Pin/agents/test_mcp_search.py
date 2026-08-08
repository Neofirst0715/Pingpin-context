from dotenv import load_dotenv
load_dotenv()

from mcp_search_tool import dashscope_web_search

result = dashscope_web_search.invoke({"query": "Etsy handmade seller policy update 2026"})
print(result)
