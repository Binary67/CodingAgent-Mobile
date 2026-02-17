"""Message builders for the Codex app-server protocol."""

from __future__ import annotations

from typing import Any, Dict

from . import config


def build_initialize_message() -> Dict[str, Any]:
    return {
        "method": "initialize",
        "id": 0,
        "params": {
            "clientInfo": {
                "name": config.CLIENT_NAME,
                "title": config.CLIENT_TITLE,
                "version": config.CLIENT_VERSION,
            }
        },
    }


def build_initialized_message() -> Dict[str, Any]:
    return {"method": "initialized", "params": {}}


def build_thread_start_message() -> Dict[str, Any]:
    return {"method": "thread/start", "id": 1, "params": {}}


def build_thread_resume_message(thread_id: str) -> Dict[str, Any]:
    return {"method": "thread/resume", "id": 1, "params": {"threadId": thread_id}}


def build_turn_start_message(thread_id: str, instruction: str) -> Dict[str, Any]:
    return {
        "method": "turn/start",
        "id": 2,
        "params": {
            "threadId": thread_id,
            "input": [{"type": "text", "text": instruction}],
        },
    }
