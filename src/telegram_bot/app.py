from __future__ import annotations

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from . import handlers, project_store, state, utils


def build_application(token: str) -> Application:
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("reset", handlers.reset_command))
    application.add_handler(CommandHandler("project", handlers.project_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text),
    )
    return application


def run_bot() -> None:
    token, allowed_user_id = utils.load_required_env()
    state.set_allowed_user_id(allowed_user_id)
    project_store.initialize()
    application = build_application(token)
    application.run_polling()
