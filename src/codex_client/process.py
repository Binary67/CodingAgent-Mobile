"""Process management for launching the Codex app-server."""

from __future__ import annotations

import os
import subprocess
from typing import List


def _resolve_codex_command() -> List[str]:
    command = "codex.cmd" if os.name == "nt" else "codex"
    return [command, "app-server"]


def start_codex_process() -> subprocess.Popen[str]:
    return subprocess.Popen(
        _resolve_codex_command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
