from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

DATA_VERSION = 1
IGNORED_DIR_NAMES = {
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}


@dataclass(frozen=True)
class ProjectInfo:
    name: str
    path: str


@dataclass
class ChatProjectState:
    current_project: Optional[str] = None
    threads_by_project: Dict[str, str] = field(default_factory=dict)
    default_thread_id: Optional[str] = None


_ROOTS: List[str] = []
_PROJECTS: Dict[str, ProjectInfo] = {}
_CHAT_STATE: Dict[int, ChatProjectState] = {}


def initialize() -> None:
    roots, projects, chat_state = _load_from_disk()
    _set_state(roots, projects, chat_state)


def list_roots() -> List[str]:
    return list(_ROOTS)


def list_projects() -> List[ProjectInfo]:
    return sorted(_PROJECTS.values(), key=lambda info: (info.name.lower(), info.path))


def get_project_info(path: str) -> Optional[ProjectInfo]:
    return _PROJECTS.get(path)


def get_current_project(chat_id: int) -> Optional[str]:
    chat_state = _CHAT_STATE.get(chat_id)
    if chat_state is None:
        return None
    return chat_state.current_project


def set_current_project(chat_id: int, project_path: Optional[str]) -> None:
    chat_state = _CHAT_STATE.setdefault(chat_id, ChatProjectState())
    chat_state.current_project = project_path
    _save_to_disk()


def get_thread_id(chat_id: int, project_path: Optional[str]) -> Optional[str]:
    chat_state = _CHAT_STATE.get(chat_id)
    if chat_state is None:
        return None
    if project_path:
        return chat_state.threads_by_project.get(project_path)
    return chat_state.default_thread_id


def set_thread_id(chat_id: int, thread_id: str, project_path: Optional[str]) -> None:
    chat_state = _CHAT_STATE.setdefault(chat_id, ChatProjectState())
    if project_path:
        chat_state.threads_by_project[project_path] = thread_id
    else:
        chat_state.default_thread_id = thread_id
    _save_to_disk()


def reset_thread_id(
    chat_id: int,
    project_path: Optional[str],
    reset_all: bool = False,
) -> None:
    chat_state = _CHAT_STATE.get(chat_id)
    if chat_state is None:
        return
    if reset_all:
        chat_state.default_thread_id = None
        chat_state.threads_by_project.clear()
    elif project_path:
        chat_state.threads_by_project.pop(project_path, None)
    else:
        chat_state.default_thread_id = None
    _save_to_disk()


def add_root(raw_path: str) -> Tuple[bool, str]:
    normalized = _normalize_path(raw_path)
    root_path = Path(normalized)
    if not root_path.is_dir():
        raise ValueError(f"Root does not exist or is not a directory: {raw_path}")
    if normalized in _ROOTS:
        return False, normalized
    _ROOTS.append(normalized)
    _ROOTS.sort()
    rescan_projects()
    return True, normalized


def remove_root(raw_path: str) -> bool:
    normalized = _normalize_path(raw_path)
    if normalized not in _ROOTS:
        return False
    _ROOTS[:] = [root for root in _ROOTS if root != normalized]
    rescan_projects()
    return True


def rescan_projects() -> int:
    projects = _scan_projects(_ROOTS)
    _PROJECTS.clear()
    _PROJECTS.update({info.path: info for info in projects})
    _prune_chat_state()
    _save_to_disk()
    return len(_PROJECTS)


def _set_state(
    roots: Iterable[str],
    projects: Iterable[ProjectInfo],
    chat_state: Dict[int, ChatProjectState],
) -> None:
    _ROOTS.clear()
    _ROOTS.extend(sorted(roots))
    _PROJECTS.clear()
    _PROJECTS.update({info.path: info for info in projects})
    _CHAT_STATE.clear()
    _CHAT_STATE.update(chat_state)


def _normalize_path(raw_path: str) -> str:
    return str(Path(raw_path).expanduser().resolve())


def normalize_path(raw_path: str) -> str:
    return _normalize_path(raw_path)


def _scan_projects(roots: Iterable[str]) -> List[ProjectInfo]:
    projects: Dict[str, ProjectInfo] = {}
    for root in roots:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path, followlinks=False):
            has_git = ".git" in dirnames or ".git" in filenames
            dirnames[:] = [name for name in dirnames if name not in IGNORED_DIR_NAMES]
            if has_git:
                project_path = str(Path(dirpath))
                projects[project_path] = ProjectInfo(
                    name=Path(dirpath).name,
                    path=project_path,
                )
                dirnames[:] = []
    return list(projects.values())


def _prune_chat_state() -> None:
    known_projects = set(_PROJECTS.keys())
    for chat_state in _CHAT_STATE.values():
        if chat_state.current_project not in known_projects:
            chat_state.current_project = None
        if chat_state.threads_by_project:
            chat_state.threads_by_project = {
                project: thread_id
                for project, thread_id in chat_state.threads_by_project.items()
                if project in known_projects
            }


def _data_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "projects.json"


def _load_from_disk() -> Tuple[List[str], List[ProjectInfo], Dict[int, ChatProjectState]]:
    data_path = _data_path()
    if not data_path.exists():
        return [], [], {}
    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Failed to read {data_path}: {exc}") from exc

    version = data.get("version", DATA_VERSION)
    if version != DATA_VERSION:
        raise RuntimeError(
            f"Unsupported project data version {version} in {data_path}.",
        )

    roots = [
        _normalize_path(root)
        for root in data.get("roots", [])
        if isinstance(root, str)
    ]
    projects_raw = data.get("projects", {})
    projects: List[ProjectInfo] = []
    if isinstance(projects_raw, dict):
        for project_path, info in projects_raw.items():
            if not isinstance(info, dict):
                continue
            name = info.get("name")
            path = info.get("path") or project_path
            if isinstance(name, str) and isinstance(path, str):
                projects.append(ProjectInfo(name=name, path=path))

    chat_state_raw = data.get("chat_state", {})
    chat_state: Dict[int, ChatProjectState] = {}
    if isinstance(chat_state_raw, dict):
        for chat_id_raw, entry in chat_state_raw.items():
            if not isinstance(entry, dict):
                continue
            try:
                chat_id = int(chat_id_raw)
            except (TypeError, ValueError):
                continue
            current_project = entry.get("current_project")
            if not isinstance(current_project, str):
                current_project = None
            default_thread_id = entry.get("default_thread_id")
            if not isinstance(default_thread_id, str):
                default_thread_id = None
            threads_raw = entry.get("threads_by_project", {})
            threads_by_project: Dict[str, str] = {}
            if isinstance(threads_raw, dict):
                for project, thread_id in threads_raw.items():
                    if isinstance(project, str) and isinstance(thread_id, str):
                        threads_by_project[project] = thread_id
            chat_state[chat_id] = ChatProjectState(
                current_project=current_project,
                threads_by_project=threads_by_project,
                default_thread_id=default_thread_id,
            )

    return roots, projects, chat_state


def _save_to_disk() -> None:
    data_path = _data_path()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": DATA_VERSION,
        "roots": list(_ROOTS),
        "projects": {
            project.path: {"name": project.name, "path": project.path}
            for project in _PROJECTS.values()
        },
        "chat_state": {
            str(chat_id): {
                "current_project": chat_state.current_project,
                "threads_by_project": dict(chat_state.threads_by_project),
                "default_thread_id": chat_state.default_thread_id,
            }
            for chat_id, chat_state in _CHAT_STATE.items()
        },
    }
    temp_path = data_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(data_path)
