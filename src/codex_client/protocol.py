"""Message builders for the Codex app-server protocol."""

from __future__ import annotations

from typing import Any, Dict, Optional

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


def build_thread_start_message(cwd: Optional[str] = None) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if cwd:
        params["cwd"] = cwd
    return {"method": "thread/start", "id": 1, "params": params}


def build_thread_resume_message(
    thread_id: str,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"threadId": thread_id}
    if cwd:
        params["cwd"] = cwd
    return {"method": "thread/resume", "id": 1, "params": params}


def build_turn_start_message(
    thread_id: str,
    instruction: str,
    cwd: Optional[str] = None,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "threadId": thread_id,
        "input": [{"type": "text", "text": instruction}],
    }
    if cwd:
        params["cwd"] = cwd
    return {
        "method": "turn/start",
        "id": 2,
        "params": params,
    }
