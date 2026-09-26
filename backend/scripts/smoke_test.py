"""Check that the model on oMLX calls tools reliably (10 runs)."""
import json
import os

from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai import OpenAIModel

load_dotenv()

calls = {"n": 0}


@tool
def get_latest_invoice(customer_id: str) -> str:
    """Look up the latest invoice of a customer.

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
    calls["n"] += 1
    return json.dumps({"customer_id": customer_id, "amount_usd": 120.0, "status": "overdue"})


model = OpenAIModel(
    client_args={
        "api_key": os.getenv("OMLX_API_KEY", "local"),
        "base_url": os.getenv("OMLX_BASE_URL", "http://127.0.0.1:8001/v1"),
    },
    model_id=os.environ["MODEL_ID"],
    params={
        "temperature": 0.2,
        "max_tokens": 1024,
        "extra_body": {
            "chat_template_kwargs": {"enable_thinking": os.getenv("ENABLE_THINKING", "false").lower() == "true"}
        },
    },
)

ok = 0
for i in range(10):
    calls["n"] = 0
    agent = Agent(
        model=model,
        tools=[get_latest_invoice],
        system_prompt="Always use the tool to look up invoices; never make up numbers.",
        callback_handler=None,
    )
    result = agent("How much is customer C-1024's invoice, and is it overdue?")
    hit = calls["n"] > 0
    correct = "120" in str(result)
    ok += hit and correct
    print(f"#{i + 1} tool_called={hit} correct={correct} -> {str(result)[:80]!r}")

print(f"\nTool called correctly {ok}/10 times")
