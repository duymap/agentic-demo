import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import auth
from app.api import chat, conversations
from app.db import init_db
from app.telemetry import check_model_server, setup_telemetry

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    setup_telemetry()
    await check_model_server()
    yield


app = FastAPI(title="Agentic Support Demo", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(chat.router)
