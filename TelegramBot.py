import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from telegram_bot.app import run_bot  # noqa: E402


if __name__ == "__main__":
    run_bot()
