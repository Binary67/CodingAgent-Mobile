from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional, Tuple

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from codex_client.session import run_codex_turn

from . import project_store, state, utils


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None:
        return
    await update.message.reply_text(
        "Codex bot is ready. Send me instructions and I'll reply with the result.\n\n"
        "Commands:\n"
        "/start - Intro\n"
        "/help - This help\n"
        "/reset - Reset conversation context\n"
        "/project - Manage project selection",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None:
        return
    await update.message.reply_text(
        "Commands:\n"
        "/start - Intro\n"
        "/help - This help\n"
        "/reset - Reset conversation context\n"
        "/project - Manage project selection\n\n"
        "Send any instruction as a normal message.",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None or update.effective_chat is None:
        return
    chat_id = update.effective_chat.id
    current_project = project_store.get_current_project(chat_id)
    project_store.reset_thread_id(chat_id, current_project)
    project_label = _format_project_label(current_project)
    if project_label:
        await update.message.reply_text(
            f"Conversation context reset for {project_label}.",
        )
        return
    await update.message.reply_text("Conversation context reset.")


async def project_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None or update.effective_chat is None:
        return

    chat_id = update.effective_chat.id
    args = context.args or []
    if not args:
        await _handle_project_default(update, chat_id)
        return

    subcommand = args[0].lower()
    handler = _PROJECT_SUBCOMMANDS.get(subcommand)
    if handler is None:
        await _reply_text(
            update,
            f"Unknown /project subcommand: {subcommand}\n"
            "Try /project, /project list, or /project root list.",
        )
        return
    await handler(update, chat_id, args[1:])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None or update.effective_chat is None:
        return
    instruction = update.message.text.strip()
    if not instruction:
        return

    chat_id = update.effective_chat.id
    lock = state.get_chat_lock(chat_id)
    if lock.locked():
        await update.message.reply_text("I'm already working on your last request.")
        return

    async with lock:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        current_project = project_store.get_current_project(chat_id)
        if current_project and not Path(current_project).is_dir():
            await update.message.reply_text(
                "Current project path is missing. Use /project rescan or "
                "/project use <name_or_index>.",
            )
            return
        status_message = await update.message.reply_text("Starting...")
        loop = asyncio.get_running_loop()

        async def _update_status(text: str) -> None:
            try:
                await status_message.edit_text(text)
            except BadRequest as exc:
                if "Message is not modified" in str(exc):
                    return
            except Exception:
                return

        def progress_callback(text: str) -> None:
            asyncio.run_coroutine_threadsafe(_update_status(text), loop)

        thread_id = project_store.get_thread_id(chat_id, current_project)
        try:
            response_text, new_thread_id, _log_path = await asyncio.to_thread(
                run_codex_turn,
                instruction,
                thread_id,
                current_project,
                progress_callback,
            )
        except Exception as exc:
            await _update_status(f"Error: {exc}")
            await update.message.reply_text(f"Error: {exc}")
            return

        project_store.set_thread_id(chat_id, new_thread_id, current_project)
        response_text = response_text.strip() if response_text else ""
        if not response_text:
            response_text = "No response produced."

        for chunk in utils.split_message(response_text):
            await update.message.reply_text(chunk)


def _format_project_label(project_path: Optional[str]) -> Optional[str]:
    if not project_path:
        return None
    info = project_store.get_project_info(project_path)
    if info is None:
        return project_path
    return f"{info.name} ({info.path})"


async def _reply_text(update: Update, text: str) -> None:
    if update.message is None:
        return
    for chunk in utils.split_message(text):
        await update.message.reply_text(chunk)


async def _handle_project_default(update: Update, chat_id: int) -> None:
    current_project = project_store.get_current_project(chat_id)
    label = _format_project_label(current_project)
    header = f"Current project: {label}" if label else "No project selected."
    await _reply_text(
        update,
        f"{header}\n"
        "Commands:\n"
        "/project list\n"
        "/project use <name_or_index>\n"
        "/project current\n"
        "/project rescan\n"
        "/project root list\n"
        "/project root add <path>\n"
        "/project root remove <path_or_index>",
    )


async def _handle_project_list(update: Update, chat_id: int, args: List[str]) -> None:
    projects = project_store.list_projects()
    if not projects:
        await _reply_text(
            update,
            "No projects found. Add roots with /project root add <path> and run "
            "/project rescan.",
        )
        return
    lines = ["Projects:"]
    for index, project in enumerate(projects, start=1):
        lines.append(f"{index}. {project.name} - {project.path}")
    await _reply_text(update, "\n".join(lines))


async def _handle_project_use(update: Update, chat_id: int, args: List[str]) -> None:
    if not args:
        await _reply_text(update, "Usage: /project use <name_or_index>")
        return
    selection = " ".join(args).strip()
    projects = project_store.list_projects()
    if not projects:
        await _reply_text(
            update,
            "No projects found. Add roots with /project root add <path> and run "
            "/project rescan.",
        )
        return
    project, error = _resolve_project_selection(selection, projects)
    if error:
        await _reply_text(update, error)
        return
    project_store.set_current_project(chat_id, project.path)
    await _reply_text(update, f"Current project set to {project.name} ({project.path}).")


async def _handle_project_current(
    update: Update,
    chat_id: int,
    args: List[str],
) -> None:
    current_project = project_store.get_current_project(chat_id)
    label = _format_project_label(current_project)
    if label:
        await _reply_text(update, f"Current project: {label}")
        return
    await _reply_text(update, "No project selected.")


async def _handle_project_rescan(update: Update, chat_id: int, args: List[str]) -> None:
    count = project_store.rescan_projects()
    await _reply_text(update, f"Rescan complete. Found {count} project(s).")


async def _handle_project_root(update: Update, chat_id: int, args: List[str]) -> None:
    if not args:
        await _reply_text(
            update,
            "Usage:\n"
            "/project root list\n"
            "/project root add <path>\n"
            "/project root remove <path_or_index>",
        )
        return
    subcommand = args[0].lower()
    handler = _ROOT_SUBCOMMANDS.get(subcommand)
    if handler is None:
        await _reply_text(update, f"Unknown /project root subcommand: {subcommand}")
        return
    await handler(update, chat_id, args[1:])


async def _handle_project_root_list(
    update: Update,
    chat_id: int,
    args: List[str],
) -> None:
    roots = project_store.list_roots()
    if not roots:
        await _reply_text(update, "No roots configured. Use /project root add <path>.")
        return
    lines = ["Roots:"]
    for index, root in enumerate(roots, start=1):
        status = "" if Path(root).is_dir() else " (missing)"
        lines.append(f"{index}. {root}{status}")
    await _reply_text(update, "\n".join(lines))


async def _handle_project_root_add(
    update: Update,
    chat_id: int,
    args: List[str],
) -> None:
    if not args:
        await _reply_text(update, "Usage: /project root add <path>")
        return
    raw_path = " ".join(args).strip()
    try:
        added, normalized = project_store.add_root(raw_path)
    except ValueError as exc:
        await _reply_text(update, str(exc))
        return
    count = len(project_store.list_projects())
    if added:
        await _reply_text(
            update,
            f"Root added: {normalized}\nFound {count} project(s).",
        )
        return
    await _reply_text(
        update,
        f"Root already exists: {normalized}\nFound {count} project(s).",
    )


async def _handle_project_root_remove(
    update: Update,
    chat_id: int,
    args: List[str],
) -> None:
    if not args:
        await _reply_text(update, "Usage: /project root remove <path_or_index>")
        return
    selection = " ".join(args).strip()
    roots = project_store.list_roots()
    if not roots:
        await _reply_text(update, "No roots configured.")
        return
    target = _resolve_root_selection(selection, roots)
    if target is None:
        await _reply_text(
            update,
            "Root not found. Use /project root list to see available roots.",
        )
        return
    removed = project_store.remove_root(target)
    if removed:
        count = len(project_store.list_projects())
        await _reply_text(
            update,
            f"Root removed: {target}\nFound {count} project(s).",
        )
        return
    await _reply_text(update, f"Root not found: {target}")


def _resolve_project_selection(
    selection: str,
    projects: List[project_store.ProjectInfo],
) -> Tuple[Optional[project_store.ProjectInfo], Optional[str]]:
    if selection.isdigit():
        index = int(selection)
        if index < 1 or index > len(projects):
            return None, f"Index out of range. Choose 1-{len(projects)}."
        return projects[index - 1], None

    normalized = selection.lower()
    matches = [project for project in projects if project.name.lower() == normalized]
    if not matches:
        return None, f"No project named '{selection}'. Use /project list."
    if len(matches) > 1:
        lines = [
            f"Multiple projects named '{selection}'. Use an index instead:",
        ]
        for index, project in enumerate(projects, start=1):
            if project in matches:
                lines.append(f"{index}. {project.name} - {project.path}")
        return None, "\n".join(lines)
    return matches[0], None


def _resolve_root_selection(selection: str, roots: List[str]) -> Optional[str]:
    if selection.isdigit():
        index = int(selection)
        if 1 <= index <= len(roots):
            return roots[index - 1]
        return None
    normalized = project_store.normalize_path(selection)
    for root in roots:
        if root == normalized:
            return root
    return None


_PROJECT_SUBCOMMANDS = {
    "list": _handle_project_list,
    "use": _handle_project_use,
    "current": _handle_project_current,
    "rescan": _handle_project_rescan,
    "root": _handle_project_root,
}

_ROOT_SUBCOMMANDS = {
    "list": _handle_project_root_list,
    "add": _handle_project_root_add,
    "remove": _handle_project_root_remove,
}
