"""Azure OpenAI agent connected to a separately provided Postgres MCP."""

import asyncio
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import AzureChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver


async def main():
    load_dotenv()
    required = (
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_DEPLOYMENT_NAME", "MCP_RENDER_URL",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise SystemExit("Set required environment variables: " + ", ".join(missing))
    transport = os.getenv("MCP_POSTGRES_TRANSPORT", "http")
    if transport not in {"http", "sse"}:
        raise SystemExit("MCP_POSTGRES_TRANSPORT must be http or sse.")
    model = AzureChatOpenAI(
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        temperature=0,
    )
    client = MultiServerMCPClient({"postgres": {
        "url": os.environ["MCP_RENDER_URL"], "transport": transport,
    }})
    agent = create_agent(model, await client.get_tools(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "postgres-demo"}}
    for question in (
        "How many customers are in the customers table?",
        "And how many orders are there?",
    ):
        print("\nYou:", question)
        result = await agent.ainvoke({"messages": [("user", question)]}, config=config)
        print("Assistant:", result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
