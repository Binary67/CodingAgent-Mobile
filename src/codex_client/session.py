"""Session loop for sending instructions to the Codex app-server."""

from __future__ import annotations

import json
from typing import Dict

from . import protocol
from .process import start_codex_process


def _send_message(proc, message: Dict[str, object]) -> None:
    if proc.stdin is None:
        raise RuntimeError("Process stdin is unavailable.")
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def run_session(instruction: str) -> int:
    proc = start_codex_process()

    if proc.stdin is None or proc.stdout is None:
        print("Failed to start codex app-server.")
        return 1

    _send_message(proc, protocol.build_initialize_message())
    _send_message(proc, protocol.build_initialized_message())
    _send_message(proc, protocol.build_thread_start_message())

    thread_id = None

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        msg = json.loads(line)
        print("server:", msg)

        if msg.get("id") == 1 and not thread_id:
            thread_id = msg.get("result", {}).get("thread", {}).get("id")
            if thread_id:
                _send_message(
                    proc,
                    protocol.build_turn_start_message(thread_id, instruction),
                )

        if msg.get("method") == "turn/completed":
            break

    proc.terminate()
    return 0
