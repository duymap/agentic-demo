from agent_framework import Agent, FunctionTool

from app.agents.model import MODEL_OPTIONS, get_client
from app.agents.tools import check_account_status, get_latest_invoice

BILLING_PROMPT = """You are a billing specialist.
Only answer questions about invoices, payments and plans. Always use the tool to look up data;
never make up numbers. Be concise and state the amount, status and due date clearly."""

TECH_PROMPT = """You are a technical support specialist.
Only handle login, account and system issues. Always check the account status with the tool
before drawing conclusions, then give concrete next steps."""


def billing_agent() -> FunctionTool:
    """Billing specialist exposed to the orchestrator as a tool. Runs without a session (stateless)."""
    agent = Agent(
        client=get_client(),
        instructions=BILLING_PROMPT,
        name="billing_agent",
        tools=[get_latest_invoice],
        default_options=MODEL_OPTIONS,
    )
    return agent.as_tool(
        name="billing_agent",
        description="Billing specialist: handles questions about invoices, payments, overdue bills and plans.",
        arg_name="query",
        arg_description="The billing question, written with full context and the customer ID",
    )


def tech_support_agent() -> FunctionTool:
    """Tech support specialist exposed to the orchestrator as a tool. Runs without a session (stateless)."""
    agent = Agent(
        client=get_client(),
        instructions=TECH_PROMPT,
        name="tech_support_agent",
        tools=[check_account_status],
        default_options=MODEL_OPTIONS,
    )
    return agent.as_tool(
        name="tech_support_agent",
        description="Tech support specialist: handles login errors, account locks and system incidents.",
        arg_name="query",
        arg_description="Description of the technical issue, with full context and the customer ID",
    )
