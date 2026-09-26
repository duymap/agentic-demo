import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from app.agents.orchestrator import build_orchestrator
from app.api.conversations import require_owner, touch_conversation
from app.auth import get_current_user
from app.config import TURN_TIMEOUT_S
from app.locks import get_lock

router = APIRouter(prefix="/api/conversations", tags=["chat"])
logger = logging.getLogger(__name__)


class SendMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: UUID,
    body: SendMessage,
    user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    cid = str(conversation_id)
    require_owner(cid, user_id)

    lock = get_lock(cid)
    if lock.locked():
        raise HTTPException(status_code=409, detail="Conversation is still processing the previous message")
    await lock.acquire()

    released = False

    def release() -> None:
        # Called from the stream's finally and from a background task (if the client disconnects
        # before the stream starts, finally never runs). Releases exactly once.
        nonlocal released
        if not released:
            released = True
            lock.release()

    async def event_stream():
        announced: set[str] = set()
        try:
            agent = build_orchestrator(cid, user_id)
            async with asyncio.timeout(TURN_TIMEOUT_S):
                async for event in agent.stream_async(body.message):
                    if "data" in event:
                        yield sse("token", {"text": event["data"]})

                    tool_use = event.get("current_tool_use")
                    if tool_use and tool_use.get("name"):
                        tool_id = tool_use.get("toolUseId")
                        if tool_id not in announced:  # this event repeats while the input streams in
                            announced.add(tool_id)
                            yield sse("tool_start", {"tool": tool_use["name"]})

            touch_conversation(cid, body.message)
            yield sse("done", {})
        except TimeoutError:
            logger.warning("Timeout conversation_id=%s user_id=%s", cid, user_id)
            yield sse("error", {"message": "Request timed out, please try again"})
        except Exception:
            logger.exception("Error handling conversation_id=%s user_id=%s", cid, user_id)
            yield sse("error", {"message": "Something went wrong, please try again"})
        finally:
            release()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=BackgroundTask(release),
    )
