from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager

from app.agents.model import get_model
from app.agents.specialists import billing_agent, tech_support_agent
from app.config import SESSIONS_DIR

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


def build_orchestrator(conversation_id: str, user_id: str | None = None) -> Agent:
    """Build the orchestrator for one conversation. History is loaded/saved by the session manager."""
    return Agent(
        model=get_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[billing_agent, tech_support_agent],
        conversation_manager=SlidingWindowConversationManager(window_size=20),
        session_manager=FileSessionManager(session_id=conversation_id, storage_dir=SESSIONS_DIR),
        trace_attributes={"session.id": conversation_id, "user.id": user_id or "anonymous"},
        callback_handler=None,
    )
