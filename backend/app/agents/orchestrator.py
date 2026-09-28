from agent_framework import Agent, AgentSession, CompactionProvider, FileHistoryProvider, SlidingWindowStrategy

from app.agents.model import MODEL_OPTIONS, get_client
from app.agents.specialists import billing_agent, tech_support_agent
from app.config import SESSIONS_DIR
from app.telemetry import set_trace_attributes

ORCHESTRATOR_PROMPT = """You are a customer support coordinator. You have NO data of your own;
all customer information must come from two specialists:
- billing_agent: invoices, payments, outstanding balances, plans
- tech_support_agent: login, account lock / unlock, system errors

MANDATORY RULES:
1. For EVERY message asking about billing or technical issues, call the matching specialist IN
   THIS TURN, even if the conversation history already contains that information (the data may
   have changed). Never answer the specialist part from history alone.
2. Multi-part questions: call each specialist for its own part, then combine the results into
   ONE coherent answer.
3. Users often use shorthand ("that customer", "what about the other one"). When calling a
   specialist, always rewrite the question with FULL context (customer ID, the issue being
   discussed).
4. The only exception: if the user just asks for a summary / recap of what was discussed,
   answer directly from history without calling any specialist.

Example: the previous turn looked up customer C-2048. The user asks "Does that customer still
owe anything, and can they log in again?" -> call billing_agent("Does customer C-2048 have any
outstanding balance?") AND tech_support_agent("Can customer C-2048's account log in now?").

Reply in the same language as the user, using markdown when helpful."""


def get_history() -> FileHistoryProvider:
    """One JSONL file per conversation: <SESSIONS_DIR>/<conversation_id>.jsonl"""
    return FileHistoryProvider(SESSIONS_DIR)


def build_orchestrator(conversation_id: str, user_id: str | None = None) -> tuple[Agent, AgentSession]:
    """Build the orchestrator for one conversation. History is loaded/saved per session by the history provider."""
    set_trace_attributes({"session.id": conversation_id, "user.id": user_id or "anonymous"})
    history = get_history()
    agent = Agent(
        client=get_client(),
        instructions=ORCHESTRATOR_PROMPT,
        name="orchestrator",
        tools=[billing_agent(), tech_support_agent()],
        default_options=MODEL_OPTIONS,
        context_providers=[
            history,
            # Only the most recent turns are sent to the model; the file keeps the full history
            CompactionProvider(
                before_strategy=SlidingWindowStrategy(keep_last_groups=20),
                history_source_id=history.source_id,
            ),
        ],
    )
    return agent, agent.create_session(session_id=conversation_id)
