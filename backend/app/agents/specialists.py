from strands import Agent, tool

from app.agents.model import get_model
from app.agents.tools import check_account_status, get_latest_invoice

BILLING_PROMPT = """You are a billing specialist.
Only answer questions about invoices, payments and plans. Always use the tool to look up data;
never make up numbers. Be concise and state the amount, status and due date clearly."""

TECH_PROMPT = """You are a technical support specialist.
Only handle login, account and system issues. Always check the account status with the tool
before drawing conclusions, then give concrete next steps."""


@tool
def billing_agent(query: str) -> str:
    """Billing specialist: handles questions about invoices, payments, overdue bills and plans.

    Args:
        query: The billing question, written with full context and the customer ID
    """
    agent = Agent(
        model=get_model(),
        system_prompt=BILLING_PROMPT,
        tools=[get_latest_invoice],
        callback_handler=None,
    )
    return str(agent(query))


@tool
def tech_support_agent(query: str) -> str:
    """Tech support specialist: handles login errors, account locks and system incidents.

    Args:
        query: Description of the technical issue, with full context and the customer ID
    """
    agent = Agent(
        model=get_model(),
        system_prompt=TECH_PROMPT,
        tools=[check_account_status],
        callback_handler=None,
    )
    return str(agent(query))
