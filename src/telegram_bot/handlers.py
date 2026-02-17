from __future__ import annotations

import asyncio

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from codex_client.session import run_codex_turn

from . import state, utils


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None:
        return
    await update.message.reply_text(
        "Codex bot is ready. Send me instructions and I'll reply with the result.",
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
        "/reset - Reset conversation context\n\n"
        "Send any instruction as a normal message.",
    )


async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await utils.reject_if_unauthorized(update):
        return
    if update.message is None or update.effective_chat is None:
        return
    state.reset_thread_id(update.effective_chat.id)
    await update.message.reply_text("Conversation context reset.")


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
        thread_id = state.get_thread_id(chat_id)
        try:
            response_text, new_thread_id, _log_path = await asyncio.to_thread(
                run_codex_turn,
                instruction,
                thread_id,
            )
        except Exception as exc:
            await update.message.reply_text(f"Error: {exc}")
            return

        state.set_thread_id(chat_id, new_thread_id)
        response_text = response_text.strip() if response_text else ""
        if not response_text:
            response_text = "No response produced."

        for chunk in utils.split_message(response_text):
            await update.message.reply_text(chunk)
