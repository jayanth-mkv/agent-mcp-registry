"""Interactive Gemini agent with MCP file tools."""

import asyncio
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():
    load_dotenv()
    model = os.environ.get("GEMINI_MODEL")
    if not model:
        raise SystemExit("Set GEMINI_MODEL to a model available in your Google account.")
    client = MultiServerMCPClient({"files": {
        "url": os.getenv("MCP_FILES_URL", "http://127.0.0.1:8000/mcp"),
        "transport": "http",
    }})
    tools = await client.get_tools()
    agent = create_agent(ChatGoogleGenerativeAI(model=model), tools)
    print("File agent ready. Type quit to exit.")
    while True:
        query = await asyncio.to_thread(input, "\nYou: ")
        if query.strip().lower() == "quit":
            break
        response = await agent.ainvoke({"messages": [("user", query)]})
        print("Assistant:", response["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
