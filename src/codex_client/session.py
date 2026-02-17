"""Session loop for sending instructions to the Codex app-server."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

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


APPROVAL_METHODS = {
    "item/commandExecution/requestApproval",
    "item/fileChange/requestApproval",
}


def _start_stderr_logger(
    proc,
    log_file: "TextIO",
    log_lock: threading.Lock,
) -> Optional[threading.Thread]:
    if proc.stderr is None:
        return None

    def _drain_stderr() -> None:
        for err_line in proc.stderr:
            _write_log_line(log_file, log_lock, "stderr", err_line.rstrip("\n"))

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()
    return stderr_thread


def _handle_approval_request(proc, msg: Dict[str, object]) -> bool:
    method = msg.get("method")
    if method not in APPROVAL_METHODS:
        return False

    request_id = msg.get("id")
    if request_id is None:
        return False

    _send_message(proc, {"id": request_id, "result": {"decision": "accept"}})
    return True


def _extract_agent_delta(msg: Dict[str, object]) -> Optional[str]:
    if msg.get("method") != "item/agentMessage/delta":
        return None
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return None
    delta = params.get("delta") or params.get("text")
    if isinstance(delta, str):
        return delta
    return None


def _extract_agent_completed_text(msg: Dict[str, object]) -> Optional[str]:
    if msg.get("method") != "item/completed":
        return None
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return None
    item = params.get("item", {})
    if not isinstance(item, dict):
        return None
    if item.get("type") != "agentMessage":
        return None
    text = item.get("text")
    if isinstance(text, str):
        return text
    return None


DEFAULT_COMMAND_STATUS = "Running command..."
DELEGATING_STATUS = "Delegating task..."
SEARCHING_STATUS = "Searching web..."
OPENING_PAGE_STATUS = "Opening page..."
FINDING_IN_PAGE_STATUS = "Finding in page..."


def _status_for_command_execution(item: Dict[str, object]) -> str:
    actions = item.get("commandActions")
    if isinstance(actions, list) and actions:
        first_action = actions[0]
        if isinstance(first_action, dict):
            action_command = first_action.get("command")
            if isinstance(action_command, str) and action_command.strip():
                return f"Ran {action_command}"
    command = item.get("command")
    if isinstance(command, str) and command.strip():
        return f"Ran {command}"
    return DEFAULT_COMMAND_STATUS


def _status_for_item_started(item: Dict[str, object]) -> Optional[str]:
    item_type = item.get("type")
    if item_type == "commandExecution":
        return _status_for_command_execution(item)
    if item_type == "fileChange":
        return _status_for_file_change(item)
    if item_type == "webSearch":
        return _status_for_web_search(item)
    if item_type == "mcpToolCall":
        return _status_for_mcp_tool_call(item)
    if item_type == "collabToolCall":
        return _status_for_collab_tool_call(item)
    return None


def _best_name(item: Dict[str, object], keys: list[str]) -> Optional[str]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value).name
    return None


def _format_name_list(names: list[str], limit: int = 2) -> str:
    if not names:
        return ""
    if len(names) <= limit:
        return ", ".join(names)
    remaining = len(names) - limit
    return f"{', '.join(names[:limit])} +{remaining} more"


def _status_for_file_change(item: Dict[str, object]) -> str:
    changes = item.get("changes")
    if not isinstance(changes, list) or not changes:
        return "Editing files..."
    names: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            continue
        path_value = change.get("path")
        if isinstance(path_value, str) and path_value.strip():
            names.append(Path(path_value).name)
    formatted_names = _format_name_list(names)
    count = len(names) if names else len(changes)
    if formatted_names:
        return f"Editing {count} file(s): {formatted_names}"
    return f"Editing {count} file(s)..."


def _status_for_web_search(item: Dict[str, object]) -> str:
    action = item.get("action")
    if isinstance(action, dict):
        action_type = action.get("type")
        if action_type == "openPage":
            return OPENING_PAGE_STATUS
        if action_type == "findInPage":
            return FINDING_IN_PAGE_STATUS
    return SEARCHING_STATUS


def _status_for_mcp_tool_call(item: Dict[str, object]) -> str:
    server = item.get("server")
    tool = item.get("tool")
    if isinstance(server, str) and isinstance(tool, str) and server and tool:
        return f"Calling tool: {server}/{tool}"
    return "Calling tool..."


def _status_for_collab_tool_call(item: Dict[str, object]) -> str:
    tool = item.get("tool")
    if isinstance(tool, str) and tool:
        return f"Delegating: {tool}"
    return DELEGATING_STATUS


def run_codex_turn(
    instruction: str,
    thread_id: Optional[str] = None,
    cwd: Optional[str] = None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[str, str, Path]:
    proc = start_codex_process()
    log_path, log_file = _open_log_file()
    log_lock = threading.Lock()

    if proc.stdin is None or proc.stdout is None:
        _write_log_line(log_file, log_lock, "stderr", "Failed to start codex app-server.")
        log_file.close()
        raise RuntimeError("Failed to start codex app-server.")

    stderr_thread = _start_stderr_logger(proc, log_file, log_lock)
    reply_chunks: list[str] = []
    final_text: Optional[str] = None
    turn_started = False
    current_thread_id = thread_id
    last_status: Optional[str] = None
    response_started = False
    last_status_time = 0.0

    def _set_status(new_status: Optional[str], min_interval: Optional[float] = None) -> None:
        nonlocal last_status, last_status_time
        if progress_callback is None or not new_status or new_status == last_status:
            return
        if min_interval is not None:
            now = time.monotonic()
            if now - last_status_time < min_interval:
                return
        try:
            progress_callback(new_status)
        except Exception:
            return
        last_status = new_status
        last_status_time = time.monotonic()

    def _update_status(
        new_status: Optional[str],
        min_interval: Optional[float] = None,
        allow_after_response: bool = False,
    ) -> None:
        if response_started and not allow_after_response:
            return
        _set_status(new_status, min_interval)

    try:
        _send_message(proc, protocol.build_initialize_message())
        _send_message(proc, protocol.build_initialized_message())
        if current_thread_id:
            _send_message(
                proc,
                protocol.build_thread_resume_message(current_thread_id, cwd=cwd),
            )
        else:
            _send_message(proc, protocol.build_thread_start_message(cwd=cwd))

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            _write_log_line(log_file, log_lock, "stdout", line)
            msg = json.loads(line)

            if isinstance(msg, dict) and _handle_approval_request(proc, msg):
                continue

            if isinstance(msg, dict) and msg.get("id") == 1:
                error = msg.get("error")
                if error:
                    raise RuntimeError(f"Thread start/resume failed: {error}")
                result = msg.get("result", {})
                if isinstance(result, dict):
                    thread = result.get("thread", {})
                    if isinstance(thread, dict):
                        current_thread_id = thread.get("id") or current_thread_id
                if current_thread_id and not turn_started:
                    _send_message(
                        proc,
                        protocol.build_turn_start_message(
                            current_thread_id,
                            instruction,
                            cwd=cwd,
                        ),
                    )
                    turn_started = True
                continue

            if isinstance(msg, dict) and msg.get("id") == 2 and msg.get("error"):
                raise RuntimeError(f"Turn start failed: {msg.get('error')}")

            if isinstance(msg, dict):
                method = msg.get("method")
                if method == "item/started":
                    params = msg.get("params", {})
                    item = params.get("item", {}) if isinstance(params, dict) else {}
                    if isinstance(item, dict):
                        _update_status(_status_for_item_started(item))

                delta = _extract_agent_delta(msg)
                if delta:
                    if not response_started:
                        response_started = True
                    reply_chunks.append(delta)
                    continue

                completed_text = _extract_agent_completed_text(msg)
                if completed_text:
                    if not response_started:
                        response_started = True
                    final_text = completed_text
                    continue

                if msg.get("method") == "turn/completed":
                    break
    finally:
        proc.terminate()
        if stderr_thread is not None:
            stderr_thread.join(timeout=1.0)
        log_file.close()

    if not current_thread_id:
        raise RuntimeError("Codex did not return a thread id.")

    reply_text = final_text if final_text is not None else "".join(reply_chunks)
    return reply_text, current_thread_id, log_path


def run_session(instruction: str) -> int:
    try:
        run_codex_turn(instruction)
    except Exception:
        return 1
    return 0
