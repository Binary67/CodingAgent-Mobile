"""Process management for launching the Codex app-server."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Dict, List


def _build_process_env() -> Dict[str, str]:
    env = dict(os.environ)
    raw_path = env.get("PATH", "")
    expanded_entries = [
        os.path.expanduser(entry) if entry else entry
        for entry in raw_path.split(os.pathsep)
    ]
    env["PATH"] = os.pathsep.join(expanded_entries)
    return env


def _resolve_codex_command(env: Dict[str, str]) -> List[str]:
    override = env.get("CODEX_COMMAND")
    if override:
        return [override, "app-server"]

    command = "codex.cmd" if os.name == "nt" else "codex"
    codex_path = shutil.which(command, path=env.get("PATH"))
    if codex_path is None:
        raise FileNotFoundError(
            "Codex CLI not found in PATH. Install it and ensure it is available "
            "on PATH, or set CODEX_COMMAND to the full executable path. "
            "See Documentations/Codex-App-Server.md.",
        )
    return [codex_path, "app-server"]


def start_codex_process() -> subprocess.Popen[str]:
    env = _build_process_env()
    return subprocess.Popen(
        _resolve_codex_command(env),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
