"""Check that the model on oMLX calls tools reliably (10 runs)."""
import asyncio
import json
import os
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.openai import OpenAIChatCompletionClient
from dotenv import load_dotenv
from pydantic import Field

load_dotenv()

calls = {"n": 0}


@tool
def get_latest_invoice(customer_id: Annotated[str, Field(description="Customer ID, e.g. C-1024")]) -> str:
    """Look up the latest invoice of a customer."""
    calls["n"] += 1
    return json.dumps({"customer_id": customer_id, "amount_usd": 120.0, "status": "overdue"})


client = OpenAIChatCompletionClient(
    model=os.environ["MODEL_ID"],
    api_key=os.getenv("OMLX_API_KEY", "local"),
    base_url=os.getenv("OMLX_BASE_URL", "http://127.0.0.1:8001/v1"),
)
options = {
    "temperature": 0.2,
    "max_tokens": 1024,
    "extra_body": {
        "chat_template_kwargs": {"enable_thinking": os.getenv("ENABLE_THINKING", "false").lower() == "true"}
    },
}


async def main() -> None:
    ok = 0
    for i in range(10):
        calls["n"] = 0
        agent = Agent(
            client=client,
            instructions="Always use the tool to look up invoices; never make up numbers.",
            tools=[get_latest_invoice],
            default_options=options,
        )
        result = await agent.run("How much is customer C-1024's invoice, and is it overdue?")
        hit = calls["n"] > 0
        correct = "120" in result.text
        ok += hit and correct
        print(f"#{i + 1} tool_called={hit} correct={correct} -> {result.text[:80]!r}")

    print(f"\nTool called correctly {ok}/10 times")


asyncio.run(main())
