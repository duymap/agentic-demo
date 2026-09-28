import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.agents.orchestrator import get_history
from app.auth import get_current_user
from app.config import SESSIONS_DIR
from app.db import get_conn

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
DEFAULT_TITLE = "New conversation"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_owner(conversation_id: str, user_id: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    # 404 for both "does not exist" and "not yours" so valid IDs are not leaked
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")


def touch_conversation(conversation_id: str, first_message: str) -> None:
    """Update updated_at; set the title from the first message."""
    with get_conn() as conn:
        conn.execute(
            """UPDATE conversations
               SET updated_at = ?, title = CASE WHEN title = ? THEN ? ELSE title END
               WHERE id = ?""",
            (now(), DEFAULT_TITLE, first_message[:50], conversation_id),
        )


@router.get("")
def list_conversations(user_id: str = Depends(get_current_user)) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
def create_conversation(user_id: str = Depends(get_current_user)) -> dict:
    conversation = {"id": str(uuid.uuid4()), "title": DEFAULT_TITLE, "updated_at": now()}
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conversation["id"], user_id, conversation["title"], conversation["updated_at"], conversation["updated_at"]),
        )
    return conversation


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: UUID, user_id: str = Depends(get_current_user)) -> list[dict]:
    cid = str(conversation_id)
    require_owner(cid, user_id)
    history = []
    for msg in await get_history().get_messages(cid):
        # Keep text only; skip function calls / function results
        text = msg.text
        if msg.role not in ("user", "assistant") or not text.strip():
            continue
        # One orchestrator turn can span several assistant messages (with tool results in between);
        # merge them into one bubble, like during streaming
        if history and history[-1]["role"] == msg.role == "assistant":
            history[-1]["content"] += "\n\n" + text
        else:
            history.append({"role": msg.role, "content": text})
    return history


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user_id: str = Depends(get_current_user)) -> Response:
    cid = str(conversation_id)
    require_owner(cid, user_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    # FileHistoryProvider stores data in <SESSIONS_DIR>/<id>.jsonl
    (Path(SESSIONS_DIR) / f"{cid}.jsonl").unlink(missing_ok=True)
    return Response(status_code=204)
