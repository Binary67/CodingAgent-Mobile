"""Session loop for sending instructions to the Codex app-server."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict

from . import protocol
from .process import start_codex_process


def _send_message(proc, message: Dict[str, object]) -> None:
    if proc.stdin is None:
        raise RuntimeError("Process stdin is unavailable.")
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _open_log_file() -> tuple[Path, "TextIO"]:
    repo_root = Path(__file__).resolve().parents[2]
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = logs_dir / f"codex-{timestamp}.log"
    log_file = log_path.open("a", encoding="utf-8", buffering=1)
    return log_path, log_file


def _write_log_line(
    log_file: "TextIO",
    lock: threading.Lock,
    stream_label: str,
    line: str,
) -> None:
    with lock:
        log_file.write(f"{stream_label}: {line}\n")
        log_file.flush()


def run_session(instruction: str) -> int:
    proc = start_codex_process()

    if proc.stdin is None or proc.stdout is None:
        log_path, log_file = _open_log_file()
        _write_log_line(log_file, threading.Lock(), "stderr", "Failed to start codex app-server.")
        log_file.close()
        return 1

    log_path, log_file = _open_log_file()
    log_lock = threading.Lock()
    stderr_thread = None
    if proc.stderr is not None:
        def _drain_stderr() -> None:
            for err_line in proc.stderr:
                _write_log_line(log_file, log_lock, "stderr", err_line.rstrip("\n"))

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

    _send_message(proc, protocol.build_initialize_message())
    _send_message(proc, protocol.build_initialized_message())
    _send_message(proc, protocol.build_thread_start_message())

    thread_id = None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            _write_log_line(log_file, log_lock, "stdout", line)
            msg = json.loads(line)

            if msg.get("id") == 1 and not thread_id:
                thread_id = msg.get("result", {}).get("thread", {}).get("id")
                if thread_id:
                    _send_message(
                        proc,
                        protocol.build_turn_start_message(thread_id, instruction),
                    )

            if msg.get("method") == "turn/completed":
                break
    finally:
        proc.terminate()
        if stderr_thread is not None:
            stderr_thread.join(timeout=1.0)
        log_file.close()
    return 0
