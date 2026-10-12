"""Interactive text agent: python -m scripts.chat. /quit exits; yes/no resolves a proposal."""
import asyncio

from google import genai

from koe import agent
from koe.config import settings
from koe.text_agent import chat


async def main():
    context, history = agent.Conversation("cli"), []
    client = genai.Client(api_key=settings.gemini_api_key)
    print("Koe text mode. GitHub, Calendar, Notion and Sheets. Each proposal needs yes/no. /quit exits.")
    try:
        while True:
            try:
                text = await asyncio.to_thread(input, "You: ")
            except EOFError:
                break
            if text.strip() == "/quit":
                break
            result = await chat(text, history, context, client)
            print("Koe:", result["text"])
    finally:
        await client.aio.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCall ended. Pending proposals expire automatically after ten minutes.")
