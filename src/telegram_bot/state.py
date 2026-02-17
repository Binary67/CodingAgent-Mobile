from __future__ import annotations

import asyncio
from typing import Dict, Optional

_ALLOWED_USER_ID: Optional[int] = None
_THREAD_IDS: Dict[int, str] = {}
_CHAT_LOCKS: Dict[int, asyncio.Lock] = {}


def set_allowed_user_id(user_id: int) -> None:
    global _ALLOWED_USER_ID
    _ALLOWED_USER_ID = user_id


def get_allowed_user_id() -> Optional[int]:
    return _ALLOWED_USER_ID


def get_thread_id(chat_id: int) -> Optional[str]:
    return _THREAD_IDS.get(chat_id)


def set_thread_id(chat_id: int, thread_id: str) -> None:
    _THREAD_IDS[chat_id] = thread_id


def reset_thread_id(chat_id: int) -> None:
    _THREAD_IDS.pop(chat_id, None)


def get_chat_lock(chat_id: int) -> asyncio.Lock:
    lock = _CHAT_LOCKS.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _CHAT_LOCKS[chat_id] = lock
    return lock
