# Plan: Agentic Customer Support Demo

**Stack:** Strands Agents (Python) · FastAPI · React + Vite + TypeScript · oMLX (local model on Apple Silicon)

---

## 1. Goals

A customer support chat app in which an **orchestrator** coordinates two **specialist agents** (billing and technical), running entirely on a local model. The demo must prove that:

1. The orchestrator splits multi-part questions across the right agents and then merges the answers.
2. Multi-turn conversations understand shorthand references ("that customer", "what about the other one").
3. Each user has multiple isolated conversations and cannot read other users' conversations.
4. The UI shows live which agent is being called, and the reply text is streamed.

---

## 2. Architecture

```
┌──────────────┐  HTTP + SSE   ┌────────────────────────┐  OpenAI API   ┌─────────────┐
│ React (Vite) │ ────────────▶ │ FastAPI + Strands      │ ────────────▶ │ oMLX (Mac)  │
└──────────────┘   /api/*      │  - orchestrator        │  /v1/...      └─────────────┘
                               │  - billing_agent       │
                               │  - tech_support_agent  │
                               └──────────┬─────────────┘
                                          │
                     SQLite (users, conversations, mock data)
                     ./sessions (conversation history - FileSessionManager)
```

**Key constraint:** oMLX only runs on macOS Apple Silicon (M-series); it does not run on Linux or NVIDIA GPUs. The demo's model host is a Mac. The backend connects through Strands' `OpenAIModel` provider with `base_url` pointing at oMLX, so switching later to vLLM/Ollama on a GPU server or the cloud only requires changing `OMLX_BASE_URL` and `MODEL_ID`.

**Design principles:**

- **Stateless** backend: each request builds a new orchestrator; history is loaded and saved by the session manager under `session_id = conversation_id`.
- Only the **orchestrator holds the conversation**. Specialist agents are stateless and created fresh on every call; the orchestrator is responsible for passing along enough context.
- The **server generates the `conversation_id`** (UUID) and **always checks ownership** before any operation.
- Each conversation processes **only one message at a time** (lock; return 409 if busy).

---

## 3. Tech stack

| Component | Choice |
|---|---|
| Model server | oMLX, OpenAI-compatible API |
| Starting model | Qwen3.5-9B, MLX 4-bit build (switch to a larger model if the Mac has more RAM) |
| Agent framework | `strands-agents[openai,otel]` |
| API | FastAPI + Uvicorn, Python 3.12 |
| Storage | SQLite (metadata + mock data), `FileSessionManager` (conversation history) |
| Auth | JWT (PyJWT), 2 pre-seeded demo users |
| Frontend | React + Vite + TypeScript + Tailwind CSS v4 + react-markdown |
| Observability | Strands OpenTelemetry → Langfuse |
| Packaging | Docker Compose (backend + frontend/nginx), oMLX runs natively |

---

## 4. Repo structure

```
agentic-demo/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, lifespan, router
│   │   ├── config.py            # read environment variables
│   │   ├── db.py                # SQLite schema + connection
│   │   ├── auth.py              # hash password, JWT, /api/auth/login
│   │   ├── locks.py             # asyncio.Lock per conversation
│   │   ├── telemetry.py         # OpenTelemetry → Langfuse (Phase 5)
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── model.py         # get_model() -> OpenAIModel pointing at oMLX
│   │   │   ├── tools.py         # tools that read SQLite data
│   │   │   ├── specialists.py   # billing_agent, tech_support_agent
│   │   │   └── orchestrator.py  # build_orchestrator()
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── conversations.py # conversation CRUD, history
│   │       └── chat.py          # send message, SSE stream
│   ├── scripts/
│   │   └── smoke_test.py        # Phase 0
│   ├── seed.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/client.ts
│   │   ├── components/
│   │   │   ├── Login.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   ├── ChatPane.tsx
│   │   │   └── MessageBubble.tsx
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── vite.config.ts
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 5. API contract

Every endpoint (except login) requires the header `Authorization: Bearer <token>`.

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login` | Log in a demo user, returns `{ token }` |
| GET | `/api/conversations` | List the current user's conversations |
| POST | `/api/conversations` | Create a new conversation; the server generates the UUID |
| GET | `/api/conversations/{id}/messages` | History (text) for re-rendering the UI |
| DELETE | `/api/conversations/{id}` | Delete the conversation and its session |
| POST | `/api/conversations/{id}/messages` | Send a message, returns an SSE stream |

**SSE events** (each frame: `event: <name>\ndata: <json>\n\n`):

| Event | Data | Meaning |
|---|---|---|
| `token` | `{ "text": "..." }` | A chunk of the reply text |
| `tool_start` | `{ "tool": "billing_agent" }` | The orchestrator starts calling an agent/tool |
| `done` | `{}` | End of turn |
| `error` | `{ "message": "..." }` | Error or timeout |

**Error codes:** `401` invalid/expired token · `404` conversation does not exist **or does not belong to the user** (merged on purpose so valid IDs are not leaked) · `409` conversation is still processing the previous message · `422` invalid input.

---

## 6. Phases

Each phase has **completion criteria**; move on to the next phase only once they are met.

### Phase 0 — oMLX and tool-calling check

This is the biggest risk (whether a local model can call tools reliably), so do it first.

**Step 1.** Install oMLX, download a model, start the server. Check the port in the oMLX settings (the example below uses `8000`).

```bash
curl http://localhost:8000/v1/models

curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "<MODEL_ID>", "messages": [{"role": "user", "content": "Hello"}]}'
```

Take the exact model `id` from the `/v1/models` output to use as `MODEL_ID`.

**Step 2.** Run the tool-calling smoke test with Strands.

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install "strands-agents[openai]"
export MODEL_ID="<id from /v1/models>"
python scripts/smoke_test.py
```

`backend/scripts/smoke_test.py`:

```python
"""Check whether the model on oMLX calls tools reliably (10 runs)."""
import json
import os

from strands import Agent, tool
from strands.models.openai import OpenAIModel

calls = {"n": 0}


@tool
def get_latest_invoice(customer_id: str) -> str:
    """Look up a customer's most recent invoice.

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
    calls["n"] += 1
    return json.dumps({"customer_id": customer_id, "amount_usd": 120.0, "status": "overdue"})


model = OpenAIModel(
    client_args={
        "api_key": os.getenv("OMLX_API_KEY", "local"),
        "base_url": os.getenv("OMLX_BASE_URL", "http://localhost:8000/v1"),
    },
    model_id=os.environ["MODEL_ID"],
    params={"temperature": 0.2, "max_tokens": 1024},
)

ok = 0
for i in range(10):
    calls["n"] = 0
    agent = Agent(
        model=model,
        tools=[get_latest_invoice],
        system_prompt="Always use the tool to look up invoices; never make up figures.",
        callback_handler=None,
    )
    result = agent("How much is customer C-1024's invoice, and is it overdue?")
    hit = calls["n"] > 0
    ok += hit
    print(f"#{i + 1} tool_called={hit} -> {str(result)[:80]!r}")

print(f"\nTool called {ok}/10 times")
```

**Completion criteria:** the tool is called at least 9/10 times and the answer uses the correct figures from the tool.

---

### Phase 1 — Backend core (agents + data)

**`backend/requirements.txt`** (pin versions with `pip freeze` once Phase 0 runs reliably):

```
strands-agents[openai,otel]
fastapi
uvicorn[standard]
pyjwt
python-dotenv
```

**`backend/.env.example`**:

```bash
OMLX_BASE_URL=http://localhost:8000/v1
OMLX_API_KEY=local
MODEL_ID=<id from /v1/models>
JWT_SECRET=<random string, e.g.: python -c "import secrets; print(secrets.token_hex(32))">
DB_PATH=./data/demo.db
SESSIONS_DIR=./data/sessions
TURN_TIMEOUT_S=180
```

**`app/config.py`**:

```python
import os

from dotenv import load_dotenv

load_dotenv()

OMLX_BASE_URL = os.getenv("OMLX_BASE_URL", "http://localhost:8000/v1")
OMLX_API_KEY = os.getenv("OMLX_API_KEY", "local")
MODEL_ID = os.environ["MODEL_ID"]
JWT_SECRET = os.environ["JWT_SECRET"]
DB_PATH = os.getenv("DB_PATH", "./data/demo.db")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./data/sessions")
TURN_TIMEOUT_S = int(os.getenv("TURN_TIMEOUT_S", "180"))
```

**`app/db.py`**:

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL DEFAULT 'Cuộc hội thoại mới',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    plan TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    amount_usd REAL NOT NULL,
    status TEXT NOT NULL,
    due_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    customer_id TEXT PRIMARY KEY REFERENCES customers(id),
    locked INTEGER NOT NULL,
    lock_reason TEXT,
    failed_logins INTEGER NOT NULL
);
"""


@contextmanager
def get_conn():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
```

**`backend/seed.py`** (safe to re-run multiple times):

```python
import uuid

from app.auth import hash_password, new_salt
from app.db import get_conn, init_db

USERS = [("alice", "demo123"), ("bob", "demo123")]

CUSTOMERS = [
    ("C-1024", "Công ty An Phát", "Business"),
    ("C-2048", "Nguyễn Minh", "Pro"),
    ("C-4096", "Studio Hạ Long", "Starter"),
]
INVOICES = [
    ("INV-9001", "C-1024", 120.0, "overdue", "2026-09-10"),
    ("INV-9002", "C-2048", 45.0, "paid", "2026-09-15"),
    ("INV-9003", "C-4096", 19.0, "open", "2026-10-05"),
]
ACCOUNTS = [
    ("C-1024", 1, "too_many_failed_logins", 6),
    ("C-2048", 0, None, 0),
    ("C-4096", 1, "payment_overdue", 0),
]


def main() -> None:
    init_db()
    with get_conn() as conn:
        for username, password in USERS:
            salt = new_salt()
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, salt) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), username, hash_password(password, salt), salt),
            )
        conn.executemany("INSERT OR IGNORE INTO customers VALUES (?, ?, ?)", CUSTOMERS)
        conn.executemany("INSERT OR IGNORE INTO invoices VALUES (?, ?, ?, ?, ?)", INVOICES)
        conn.executemany("INSERT OR IGNORE INTO accounts VALUES (?, ?, ?, ?)", ACCOUNTS)
    print("Seed done")


if __name__ == "__main__":
    main()
```

**`app/agents/model.py`**:

```python
from strands.models.openai import OpenAIModel

from app.config import MODEL_ID, OMLX_API_KEY, OMLX_BASE_URL


def get_model() -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": OMLX_API_KEY, "base_url": OMLX_BASE_URL},
        model_id=MODEL_ID,
        params={"temperature": 0.2, "max_tokens": 2048},
    )
```

**`app/agents/tools.py`**:

```python
import json

from strands import tool

from app.db import get_conn


@tool
def get_latest_invoice(customer_id: str) -> str:
    """Look up a customer's most recent invoice and plan.

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT i.id, i.customer_id, c.name, c.plan, i.amount_usd, i.status, i.due_date
               FROM invoices i JOIN customers c ON c.id = i.customer_id
               WHERE i.customer_id = ? ORDER BY i.due_date DESC LIMIT 1""",
            (customer_id,),
        ).fetchone()
    if not row:
        return json.dumps({"error": f"No invoice found for {customer_id}"}, ensure_ascii=False)
    return json.dumps(dict(row), ensure_ascii=False)


@tool
def check_account_status(customer_id: str) -> str:
    """Check account status (locked or not, lock reason, number of failed logins).

    Args:
        customer_id: Customer ID, e.g. C-1024
    """
    with get_conn() as conn:
        row = conn.execute(
            """SELECT a.customer_id, c.name, a.locked, a.lock_reason, a.failed_logins
               FROM accounts a JOIN customers c ON c.id = a.customer_id
               WHERE a.customer_id = ?""",
            (customer_id,),
        ).fetchone()
    if not row:
        return json.dumps({"error": f"No account found for {customer_id}"}, ensure_ascii=False)
    return json.dumps(dict(row), ensure_ascii=False)
```

**`app/agents/specialists.py`** (stateless — created fresh on every call, never shared between users):

```python
from strands import Agent, tool

from app.agents.model import get_model
from app.agents.tools import check_account_status, get_latest_invoice

BILLING_PROMPT = """You are a billing specialist.
Only answer questions about invoices, payments and plans. Always use tools to look up data;
never make up figures. Keep answers short, and state the amount, status and due date clearly."""

TECH_PROMPT = """You are a technical support specialist.
Only handle login, account and system error issues. Always check the account status
with the tool before drawing a conclusion, then give concrete steps to resolve the issue."""


@tool
def billing_agent(query: str) -> str:
    """Billing expert: handles questions about invoices, payments, overdue status and plans.

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
    """Technical expert: handles login errors, account lockouts and system incidents.

    Args:
        query: Description of the technical issue, written with full context and the customer ID
    """
    agent = Agent(
        model=get_model(),
        system_prompt=TECH_PROMPT,
        tools=[check_account_status],
        callback_handler=None,
    )
    return str(agent(query))
```

**`app/agents/orchestrator.py`**:

```python
from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager

from app.agents.model import get_model
from app.agents.specialists import billing_agent, tech_support_agent
from app.config import SESSIONS_DIR

ORCHESTRATOR_PROMPT = """You are a customer support coordinator.
- Questions about invoices / payments -> call billing_agent
- Questions about login / accounts / errors -> call tech_support_agent
- Multi-part questions: call each agent for its own part, then combine them
  into ONE coherent answer.
- Do not answer the specialist part yourself before asking the corresponding agent.
- The user may use shorthand ("that customer", "what about the other one"). When calling a
  specialist agent, always rewrite the question with FULL context (customer ID, the issue being discussed).
- Reply in the same language as the user, using markdown when needed."""


def build_orchestrator(conversation_id: str, user_id: str | None = None) -> Agent:
    """Build the orchestrator for a conversation. History is loaded/saved automatically by the session manager."""
    return Agent(
        model=get_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[billing_agent, tech_support_agent],
        conversation_manager=SlidingWindowConversationManager(window_size=20),
        session_manager=FileSessionManager(session_id=conversation_id, storage_dir=SESSIONS_DIR),
        trace_attributes={"session.id": conversation_id, "user.id": user_id or "anonymous"},
        callback_handler=None,
    )
```

**Quick check** (`python -c` or a throwaway script):

```python
from app.agents.orchestrator import build_orchestrator

agent = build_orchestrator("local-test")
print(agent("Customer C-1024 can't log in, and is this month's invoice overdue?"))
print(agent("How much does that customer owe?"))
```

**Completion criteria:** the two-part question calls both agents and answers with the correct seed data; the "that customer" question is correctly understood as C-1024.

---

### Phase 2 — Conversation API (auth, ownership, lock)

**`app/auth.py`**:

```python
import hashlib
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import JWT_SECRET
from app.db import get_conn

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer()


def new_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()


def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + 8 * 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return payload["sub"]


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if not row or not secrets.compare_digest(row["password_hash"], hash_password(body.password, row["salt"])):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
    return {"token": create_token(row["id"])}
```

**`app/locks.py`** (sufficient for a single backend instance; for multiple instances switch to a Redis lock):

```python
import asyncio

_locks: dict[str, asyncio.Lock] = {}


def get_lock(conversation_id: str) -> asyncio.Lock:
    return _locks.setdefault(conversation_id, asyncio.Lock())
```

**`app/api/conversations.py`**:

```python
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.agents.orchestrator import build_orchestrator
from app.auth import get_current_user
from app.config import SESSIONS_DIR
from app.db import get_conn

router = APIRouter(prefix="/api/conversations", tags=["conversations"])
DEFAULT_TITLE = "Cuộc hội thoại mới"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_owner(conversation_id: str, user_id: str) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT user_id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    # 404 for both "does not exist" and "not yours" so valid IDs are not leaked
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại")


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
def get_messages(conversation_id: UUID, user_id: str = Depends(get_current_user)) -> list[dict]:
    cid = str(conversation_id)
    require_owner(cid, user_id)
    agent = build_orchestrator(cid, user_id)  # session manager reloads the history
    history = []
    for msg in agent.messages:
        # Keep only the text parts; skip toolUse / toolResult
        text = "".join(block["text"] for block in msg["content"] if "text" in block)
        if text.strip():
            history.append({"role": msg["role"], "content": text})
    return history


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: UUID, user_id: str = Depends(get_current_user)) -> Response:
    cid = str(conversation_id)
    require_owner(cid, user_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    # FileSessionManager stores data at <SESSIONS_DIR>/session_<id>/
    shutil.rmtree(Path(SESSIONS_DIR) / f"session_{cid}", ignore_errors=True)
    return Response(status_code=204)
```

> `conversation_id` is declared as type `UUID`, so FastAPI automatically rejects non-UUID values, which also blocks path traversal into the sessions directory.

**`app/main.py`**:

```python
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import auth
from app.api import chat, conversations
from app.db import init_db

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Agentic Support Demo", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)
```

In this phase `chat.py` can be a non-streaming version (using `invoke_async`) to test the logic first; Phase 3 replaces it with the SSE version below.

**Test with curl:**

```bash
cd backend && cp .env.example .env   # fill in MODEL_ID, JWT_SECRET
python seed.py
uvicorn app.main:app --port 8001 --reload

TOKEN_A=$(curl -s localhost:8001/api/auth/login -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"demo123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
CID=$(curl -s -X POST localhost:8001/api/conversations -H "Authorization: Bearer $TOKEN_A" \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
echo $CID
```

**Completion criteria:** bob gets a 404 when accessing alice's conversation; after a server restart, alice's history is still there; when 2 parallel requests are sent to the same conversation, the later one gets a 409.

---

### Phase 3 — Streaming (SSE)

Use Strands' `stream_async` and map the orchestrator's events to SSE events. The lock is held for the entire stream and is always released in `finally` (including when the client disconnects).

**`app/api/chat.py`**:

```python
import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

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
        raise HTTPException(status_code=409, detail="Hội thoại đang xử lý tin nhắn trước")
    await lock.acquire()

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
            yield sse("error", {"message": "Quá thời gian xử lý, vui lòng thử lại"})
        except Exception:
            logger.exception("Error handling conversation %s", cid)
            yield sse("error", {"message": "Có lỗi khi xử lý, vui lòng thử lại"})
        finally:
            lock.release()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Test:**

```bash
curl -N -X POST localhost:8001/api/conversations/$CID/messages \
  -H "Authorization: Bearer $TOKEN_A" -H "Content-Type: application/json" \
  -d '{"message":"Customer C-1024 can't log in, and is this month's invoice overdue?"}'
```

**Completion criteria:** the `tool_start` events (`tech_support_agent`, `billing_agent`) appear first, then `token` events stream in gradually, ending with `done`.

---

### Phase 4 — React UI

**Setup:**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install tailwindcss @tailwindcss/vite react-markdown
```

**`vite.config.ts`** (proxy `/api` to the backend, no CORS needed):

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": "http://localhost:8001" },
  },
});
```

**`src/index.css`**:

```css
@import "tailwindcss";
```

**`src/api/client.ts`** — calls REST and reads SSE using `fetch` + `ReadableStream` (because `EventSource` cannot send a POST with an `Authorization` header):

```ts
export type Conversation = { id: string; title: string; updated_at: string };
export type ChatMessage = { role: "user" | "assistant"; content: string };

let token = localStorage.getItem("token") ?? "";

export function setToken(value: string) {
  token = value;
  if (value) localStorage.setItem("token", value);
  else localStorage.removeItem("token");
}

export function hasToken() {
  return token !== "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });
  if (res.status === 401) {
    setToken("");
    window.location.reload();
  }
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  listConversations: () => request<Conversation[]>("/conversations"),
  createConversation: () => request<Conversation>("/conversations", { method: "POST" }),
  getMessages: (id: string) => request<ChatMessage[]>(`/conversations/${id}/messages`),
  deleteConversation: (id: string) => request<void>(`/conversations/${id}`, { method: "DELETE" }),
};

export type StreamHandlers = {
  onToken: (text: string) => void;
  onToolStart: (tool: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
};

export async function sendMessage(id: string, message: string, h: StreamHandlers) {
  const res = await fetch(`/api/conversations/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  });
  if (!res.ok || !res.body) {
    h.onError(res.status === 409 ? "Đang xử lý tin nhắn trước, vui lòng đợi" : `Lỗi ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? ""; // the last frame may be incomplete
    for (const frame of frames) {
      const event = frame.match(/^event: (.*)$/m)?.[1];
      const data = JSON.parse(frame.match(/^data: (.*)$/m)?.[1] ?? "{}");
      if (event === "token") h.onToken(data.text);
      else if (event === "tool_start") h.onToolStart(data.tool);
      else if (event === "done") h.onDone();
      else if (event === "error") h.onError(data.message);
    }
  }
}
```

**`src/App.tsx`**:

```tsx
import { useCallback, useEffect, useState } from "react";
import { api, hasToken, setToken, type Conversation } from "./api/client";
import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import ChatPane from "./components/ChatPane";

export default function App() {
  const [loggedIn, setLoggedIn] = useState(hasToken());
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setConversations(await api.listConversations());
  }, []);

  useEffect(() => {
    if (loggedIn) refresh();
  }, [loggedIn, refresh]);

  if (!loggedIn) return <Login onSuccess={() => setLoggedIn(true)} />;

  return (
    <div className="flex h-screen bg-gray-50 text-gray-900">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={async () => {
          const c = await api.createConversation();
          await refresh();
          setActiveId(c.id);
        }}
        onDelete={async (id) => {
          await api.deleteConversation(id);
          if (id === activeId) setActiveId(null);
          await refresh();
        }}
        onLogout={() => {
          setToken("");
          setLoggedIn(false);
        }}
      />
      {activeId ? (
        <ChatPane key={activeId} conversationId={activeId} onTurnComplete={refresh} />
      ) : (
        <div className="flex flex-1 items-center justify-center text-gray-400">
          Chọn hoặc tạo một cuộc hội thoại
        </div>
      )}
    </div>
  );
}
```

**`src/components/Login.tsx`**:

```tsx
import { useState, type FormEvent } from "react";
import { api, setToken } from "../api/client";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const { token } = await api.login(username, password);
      setToken(token);
      onSuccess();
    } catch {
      setError("Sai tài khoản hoặc mật khẩu");
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-gray-50">
      <form onSubmit={submit} className="w-80 space-y-3 rounded-xl bg-white p-6 shadow">
        <h1 className="text-lg font-semibold">Agentic Support Demo</h1>
        <input className="w-full rounded border p-2" value={username}
          onChange={(e) => setUsername(e.target.value)} placeholder="Username" />
        <input className="w-full rounded border p-2" type="password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-blue-600 p-2 text-white">Đăng nhập</button>
      </form>
    </div>
  );
}
```

**`src/components/Sidebar.tsx`**:

```tsx
import type { Conversation } from "../api/client";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
};

export default function Sidebar({ conversations, activeId, onSelect, onCreate, onDelete, onLogout }: Props) {
  return (
    <aside className="flex w-72 flex-col border-r bg-white">
      <button onClick={onCreate} className="m-3 rounded bg-blue-600 p-2 text-white">
        + Cuộc hội thoại mới
      </button>
      <ul className="flex-1 overflow-y-auto">
        {conversations.map((c) => (
          <li key={c.id}
            className={`group flex cursor-pointer items-center justify-between px-4 py-2 hover:bg-gray-100 ${
              c.id === activeId ? "bg-gray-100 font-medium" : ""}`}
            onClick={() => onSelect(c.id)}>
            <span className="truncate">{c.title}</span>
            <button className="hidden text-gray-400 hover:text-red-600 group-hover:block"
              onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}>
              ✕
            </button>
          </li>
        ))}
      </ul>
      <button onClick={onLogout} className="m-3 text-sm text-gray-500 hover:underline">
        Đăng xuất
      </button>
    </aside>
  );
}
```

**`src/components/MessageBubble.tsx`**:

```tsx
import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../api/client";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] rounded-2xl px-4 py-2 ${
        isUser ? "bg-blue-600 text-white" : "bg-white shadow-sm"}`}>
        <div className="prose prose-sm max-w-none">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
```

**`src/components/ChatPane.tsx`** — streams text into the last message and shows which agent is running:

```tsx
import { useEffect, useRef, useState } from "react";
import { api, sendMessage, type ChatMessage } from "../api/client";
import MessageBubble from "./MessageBubble";

const TOOL_LABELS: Record<string, string> = {
  billing_agent: "Đang hỏi chuyên viên billing…",
  tech_support_agent: "Đang hỏi chuyên viên kỹ thuật…",
};

type Props = { conversationId: string; onTurnComplete: () => void };

export default function ChatPane({ conversationId, onTurnComplete }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activity, setActivity] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getMessages(conversationId).then(setMessages);
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activity]);

  const appendToLast = (text: string) =>
    setMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      copy[copy.length - 1] = { ...last, content: last.content + text };
      return copy;
    });

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setActivity([]);
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);

    await sendMessage(conversationId, text, {
      onToken: appendToLast,
      onToolStart: (tool) => setActivity((prev) => [...prev, TOOL_LABELS[tool] ?? `Đang chạy ${tool}…`]),
      onDone: onTurnComplete,
      onError: (msg) => appendToLast(`\n\n⚠️ ${msg}`),
    });

    setBusy(false);
    setActivity([]);
  };

  return (
    <main className="flex flex-1 flex-col">
      <div className="flex-1 space-y-3 overflow-y-auto p-6">
        {messages.map((m, i) => <MessageBubble key={i} message={m} />)}
        {busy && activity.map((a, i) => (
          <p key={i} className="text-sm italic text-gray-500">{a}</p>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2 border-t bg-white p-4">
        <textarea
          className="flex-1 resize-none rounded border p-2"
          rows={2}
          value={input}
          disabled={busy}
          placeholder="Nhập câu hỏi…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
        />
        <button onClick={send} disabled={busy} className="rounded bg-blue-600 px-4 text-white disabled:opacity-50">
          Gửi
        </button>
      </div>
    </main>
  );
}
```

> The `prose` class requires the `@tailwindcss/typography` plugin (`npm install @tailwindcss/typography`, and add `@plugin "@tailwindcss/typography";` to `index.css`). Without it, markdown still renders, just less nicely.

**Run:** `npm run dev`, open `http://localhost:5173`.

**Completion criteria:** run the full demo script (section 7) in the browser: text streams, the agent status lines appear correctly, and the conversation list updates its titles and order.

---

### Phase 5 — Observability and resilience

Enable Strands' OpenTelemetry and export traces to Langfuse to see the **orchestrator → specialist → tool** call tree, with latency and tokens for each step. The `trace_attributes` in `build_orchestrator` (Phase 1) already attach `session.id` and `user.id` so traces can be filtered by conversation.

**`app/telemetry.py`**:

```python
from strands.telemetry import StrandsTelemetry


def setup_telemetry() -> None:
    # Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS from the environment
    StrandsTelemetry().setup_otlp_exporter()
```

Call it in the `lifespan` of `main.py`:

```python
from app.telemetry import setup_telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_telemetry()
    yield
```

Add to `.env`:

```bash
# Langfuse Cloud or self-hosted: <host>/api/public/otel
OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
# Generate the string: echo -n "pk-lf-...:sk-lf-..." | base64
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64>
```

**Resilience (checklist):**

- [x] Per-turn timeout (`TURN_TIMEOUT_S`, Phase 3).
- [x] Input length limit (`max_length=4000`).
- [x] Per-conversation lock, returns 409.
- [ ] Check that oMLX is alive at startup: call `GET {OMLX_BASE_URL}/models` and log a clear warning if it cannot connect.
- [ ] Log `conversation_id` and `user_id` in every error log (do not log message content).

**Completion criteria:** every chat turn has a complete trace in Langfuse; if oMLX is shut down mid-turn, the UI receives an error message instead of hanging.

---

### Phase 6 — Packaging

oMLX runs **natively on the Mac** (MLX needs Metal and does not run in a container). The backend and frontend run with Docker Compose; the backend reaches oMLX via `host.docker.internal`.

**`backend/Dockerfile`**:

```dockerfile
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m app && mkdir -p /app/data && chown -R app /app
USER app

EXPOSE 8001
CMD ["sh", "-c", "python seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8001"]
```

**`frontend/nginx.conf`** (disable buffering so SSE is delivered immediately):

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;

    location / {
        try_files $uri /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8001;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

**`frontend/Dockerfile`**:

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
```

**`docker-compose.yml`**:

```yaml
services:
  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      OMLX_BASE_URL: http://host.docker.internal:8000/v1
      DB_PATH: /app/data/demo.db
      SESSIONS_DIR: /app/data/sessions
    volumes:
      - backend-data:/app/data

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  backend-data:
```

**Run:**

```bash
# 1. Start oMLX on the Mac, load the model
# 2. Fill in backend/.env from .env.example
docker compose up --build
# 3. Open http://localhost:3000, log in as alice / demo123
```

> If the backend inside the container cannot reach oMLX, configure oMLX to listen on `0.0.0.0` instead of only `127.0.0.1` (in the oMLX settings).

**Completion criteria:** on a clean Mac, clone the repo, follow the README, and have the demo running in under 15 minutes.

---

## 7. Demo script

| # | Action | What to look for |
|---|---|---|
| 1 | Log in as **alice**, create a conversation, ask: *"Customer C-1024 can't log in, and is this month's invoice overdue?"* | The UI shows the tech support status and then the billing status, with a combined answer: the account is locked due to 6 failed logins, and the 120 USD invoice has been overdue since Sep 10 |
| 2 | Follow up: *"What plan is that customer on, and what do they need to do to unlock?"* | Understands "that customer" as C-1024; calls billing for the plan part and technical support for the unlock part |
| 3 | Create a second conversation, ask about **C-4096** | Answered separately, not mixed up with C-1024 |
| 4 | Go back to the first conversation, ask *"Summarize the two issues"* | Context is still correct |
| 5 | Log out, log in as **bob** | None of alice's conversations are visible |
| 6 | Open Langfuse | The trace for turn 1 shows the tree orchestrator → 2 agents → 2 tools, with latency |

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Local model calls tools unreliably | Check in Phase 0; tools with few parameters and clear docstrings; low `temperature`; if below 9/10, switch to a larger model |
| "Thinking" model prints its reasoning into the answer | Turn off the model's thinking mode in oMLX or via `params`; check this right away in Phase 0 |
| Slowness from nested model calls (a two-part question can take 5–7 LLM calls) | Stream tokens + show agent status so viewers can see the system is working; oMLX's SSD-backed KV cache makes subsequent turns faster |
| Context bloat in long chats | `SlidingWindowConversationManager(window_size=20)`; stateless sub-agents |
| Lock is only correct with a single backend instance | Good enough for the demo; switch to a Redis lock in production |
| Strands API changes between versions | Pin versions in `requirements.txt` after Phase 0 |

---

## 9. After the demo: path to production

- **Session storage:** move from `FileSessionManager` to storage on S3, prefixed by tenant (`tenants/{tenant_id}/`). Newer Strands docs recommend `SnapshotSessionManager` for single-agent sessions; re-check when migrating.
- **Lock:** Redis lock per `conversation_id` to run multiple pods.
- **Auth:** replace the demo login with OIDC (Cognito/Keycloak/Entra ID).
- **Model:** point `OMLX_BASE_URL` at vLLM on a GPU server or at Bedrock; the agent code stays the same.
- **Deploy:** backend container on EKS, frontend on S3 + CloudFront.
- **Evals:** use the `strands-agents` evals SDK to automatically score a sample question set whenever the prompt or model changes.
