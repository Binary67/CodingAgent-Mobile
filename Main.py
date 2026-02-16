import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from codex_client import config  # noqa: E402
from codex_client.session import run_session  # noqa: E402

def main() -> int:
    instruction = " ".join(sys.argv[1:]) or config.DEFAULT_INSTRUCTION
    return run_session(instruction)


if __name__ == "__main__":
    raise SystemExit(main())
