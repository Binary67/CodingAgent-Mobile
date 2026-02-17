from __future__ import annotations

import os
from typing import List, Tuple

from dotenv import load_dotenv
from telegram import Update

from . import state

TELEGRAM_MESSAGE_LIMIT = 4000


def load_required_env() -> Tuple[str, int]:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    allowed_user_id = os.getenv("TELEGRAM_ALLOWED_USER_ID")
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": token,
            "TELEGRAM_ALLOWED_USER_ID": allowed_user_id,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    try:
        allowed_id_int = int(allowed_user_id)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_ALLOWED_USER_ID must be an integer.") from exc
    return token, allowed_id_int


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> List[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if current_len + len(line) > limit and current:
            chunks.append("".join(current))
            current = [line]
            current_len = len(line)
            continue
        current.append(line)
        current_len += len(line)

    if current:
        chunks.append("".join(current))
    return chunks


async def reject_if_unauthorized(update: Update) -> bool:
    allowed_user_id = state.get_allowed_user_id()
    if allowed_user_id is None:
        return True
    if update.effective_user is None or update.message is None:
        return True
    if update.effective_user.id != allowed_user_id:
        await update.message.reply_text("Unauthorized user.")
        return True
    return False
