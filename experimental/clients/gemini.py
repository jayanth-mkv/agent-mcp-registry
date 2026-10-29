"""Let Gemini call the file MCP using the Google SDK's MCP integration."""

import asyncio
import os

from dotenv import load_dotenv
from fastmcp import Client
from google import genai


async def main():
    load_dotenv()
    model = os.environ.get("GEMINI_MODEL")
    if not model:
        raise SystemExit("Set GEMINI_MODEL to a model available in your Google account.")
    url = os.getenv("MCP_FILES_URL", "http://127.0.0.1:8000/mcp")
    async with genai.Client().aio as gemini, Client(url) as client:
        response = await gemini.models.generate_content(
            model=model,
            contents="Write 10 jokes to jokes.txt using the file tools.",
            config=genai.types.GenerateContentConfig(
                temperature=0, tools=[client.session],
            ),
        )
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
