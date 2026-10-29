"""List file tools and write an example file through Streamable HTTP."""

import asyncio
import os

from fastmcp import Client


async def main():
    url = os.getenv("MCP_FILES_URL", "http://127.0.0.1:8000/mcp")
    async with Client(url) as client:
        await client.ping()
        print("Tools:", [tool.name for tool in await client.list_tools()])
        result = await client.call_tool("write_file", {
            "path": "example.txt", "content": "Created by the MCP client.\n",
        })
        print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())
