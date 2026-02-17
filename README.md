# CodingAgent-Mobile

**About**
This repository provides a lightweight Python client for the Codex `app-server` protocol and a Telegram bot that lets a single authorized user send Codex instructions from chat. The bot can pin a “current project” so Codex runs with that project as the working directory, and it persists thread IDs for continuity across sessions.

**Objectives**
- Offer a minimal, readable Codex `app-server` client that can start/resume threads and collect streamed responses.
- Provide a Telegram interface with simple project management and status updates while Codex works.
- Persist project roots, selections, and thread IDs on disk for long-running use.

**Prerequisites**
- Python `>=3.13`.
- Codex CLI installed with `app-server` support and available on `PATH` (or set `CODEX_COMMAND` to the full executable path).
- Telegram bot token and a numeric allowed user ID for the bot.
- Dependencies installed from `pyproject.toml`.

**How To Use**

**Install Dependencies**
1. Create and activate a virtual environment.
2. Install dependencies.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

If you use `uv`, you can run:

```bash
uv sync
```

**Run The Telegram Bot**
1. Create a `.env` file (loaded automatically) with:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USER_ID=123456789
```

2. Start the bot:

```bash
python TelegramBot.py
```

3. In Telegram, use:

- `/start` or `/help` for instructions.
- `/project root add /path/to/roots` to register root folders.
- `/project rescan` to find Git projects under those roots.
- `/project list` and `/project use <name_or_index>` to set a working directory.
- `/reset` to clear the current conversation context for the selected project.

**Run A One-Off Codex Turn**
Run a single turn with an instruction string:

```bash
python Main.py "Summarize this repo."
```

This starts a Codex `app-server` session and writes raw JSONL traffic to `logs/`. For programmatic use, import `run_codex_turn` from `src/codex_client/session.py` and handle the returned text/thread ID.

**Data And Logs**
- `data/projects.json` stores roots, discovered projects, and per-chat thread state.
- `logs/codex-YYYYMMDD-HHMMSS.log` contains raw Codex app-server traffic for each session.
