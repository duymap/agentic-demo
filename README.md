# Agentic Customer Support Demo

An orchestrator (Strands Agents) coordinates two specialist agents — `billing_agent` and `tech_support_agent` — running entirely on a local model served by oMLX. Design details: [`agentic-demo-plan.md`](agentic-demo-plan.md).

```
React (Vite, :5173) ──/api──▶ FastAPI + Strands (:8002) ──OpenAI API──▶ oMLX (:8001)
                                   │
                    SQLite + ./data/sessions (FileSessionManager)
```

## Requirements

- Apple Silicon Mac, with oMLX running the `Qwen3.8-27B-MLX-4bit` model at `http://127.0.0.1:8001/v1`
- Python 3.12 (use [`uv`](https://docs.astral.sh/uv/) to create the venv), Node 22+
- Docker Desktop (only for running with Docker Compose)

## Run locally (dev)

```bash
# Backend
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env          # fill in OMLX_API_KEY, MODEL_ID, JWT_SECRET
python seed.py
uvicorn app.main:app --port 8002

# Frontend (another terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173, proxies /api -> :8002
```

Login: `alice / demo123` or `bob / demo123`.

## Run with Docker Compose

oMLX runs natively on the Mac (MLX needs Metal); the backend container reaches it via `host.docker.internal:8001`.

```bash
cp backend/.env.example backend/.env   # fill in the values
docker compose up --build
# open http://localhost:3000
```

> If the container cannot reach oMLX, make oMLX listen on `0.0.0.0` instead of `127.0.0.1`.

## Checks

```bash
cd backend
python scripts/smoke_test.py   # Phase 0: 10 tool-calling runs, needs >= 9/10
```

## Configuration (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `OMLX_BASE_URL` | `http://127.0.0.1:8001/v1` | To switch to vLLM/Ollama/..., change only this and `MODEL_ID` |
| `OMLX_API_KEY` | `local` | oMLX API key |
| `MODEL_ID` | — | The `id` from `GET /v1/models` |
| `ENABLE_THINKING` | `false` | Qwen3 thinking mode. Off makes nested agent calls faster |
| `JWT_SECRET` | — | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `TURN_TIMEOUT_S` | `300` | Timeout per chat turn |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | (empty) | Optional. Set it to send Strands traces to Langfuse / an OTLP collector |
| `OTEL_EXPORTER_OTLP_HEADERS` | (empty) | E.g. `Authorization=Basic <base64 pk:sk>` for Langfuse |

## Data storage

- **SQLite** (`backend/data/demo.db`): users, the conversation list (id, owner, title, timestamps) and the demo data (customers, invoices, accounts).
- **JSON files** (`backend/data/sessions/session_<conversation_id>/`): the full message history of each conversation, written by Strands `FileSessionManager`, including tool calls and specialist results.

Back up both when backing up the app.

## Observability (optional)

The agent framework is **Strands**; Strands emits OpenTelemetry traces on its own (orchestrator → specialist → tool, latency, tokens). Langfuse is only a place to view those traces. If `OTEL_EXPORTER_OTLP_ENDPOINT` is not set, telemetry is off and the app runs normally.

## Demo scenarios

1. Log in as **alice**, create a conversation, and ask: *"Customer C-1024 can't log in, and is this month's invoice overdue?"* → the UI shows the tech support and billing status lines, then one combined answer.
2. *"What plan is that customer on, and what do they need to do to unlock?"* → "that customer" is understood as C-1024.
3. Create a second conversation and ask about **C-4096** → no mix-up with C-1024.
4. Go back to the first conversation: *"Summarize the two issues"*.
5. Log out and log in as **bob** → alice's conversations are not visible.

> A two-part question takes ~5–7 nested LLM calls; with Qwen3.8-27B 4-bit each turn takes about 60–130 seconds.
