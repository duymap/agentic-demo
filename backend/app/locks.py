import asyncio

_locks: dict[str, asyncio.Lock] = {}


def get_lock(conversation_id: str) -> asyncio.Lock:
    return _locks.setdefault(conversation_id, asyncio.Lock())
