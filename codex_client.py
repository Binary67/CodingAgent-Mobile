import json
import os
import subprocess
import sys


def main() -> int:
    instruction = " ".join(sys.argv[1:]) or "Summarize this repo."
    cmd = "codex.cmd" if os.name == "nt" else "codex"

    proc = subprocess.Popen(
        [cmd, "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if proc.stdin is None or proc.stdout is None:
        print("Failed to start codex app-server.")
        return 1

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    send(
        {
            "method": "initialize",
            "id": 0,
            "params": {
                "clientInfo": {
                    "name": "my_client",
                    "title": "My Client",
                    "version": "0.1.0",
                }
            },
        }
    )
    send({"method": "initialized", "params": {}})
    send({"method": "thread/start", "id": 1, "params": {"model": "gpt-5.2-codex"}})

    thread_id = None

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue

        msg = json.loads(line)
        print("server:", msg)

        if msg.get("id") == 1 and not thread_id:
            thread_id = msg.get("result", {}).get("thread", {}).get("id")
            if thread_id:
                send(
                    {
                        "method": "turn/start",
                        "id": 2,
                        "params": {
                            "threadId": thread_id,
                            "input": [{"type": "text", "text": instruction}],
                        },
                    }
                )

        if msg.get("method") == "turn/completed":
            break

    proc.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
