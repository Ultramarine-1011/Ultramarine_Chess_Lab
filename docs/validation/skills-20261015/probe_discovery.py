"""Read-only discovery evidence; no thread, model turn or config write is made.

Run from the repo root with a compatible Codex executable as the sole argument.
The output contains skill metadata, not MCP configuration or credentials.
"""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading


def main():
    root = Path.cwd().resolve()
    expected = {p.parent.name for p in (root / ".agents/skills").glob("*/SKILL.md")}
    if not expected:
        raise RuntimeError("Run from the UCL repository root")
    proc = subprocess.Popen(
        [sys.argv[1], "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8",
    )
    messages = queue.Queue()

    def read():
        for line in proc.stdout:
            messages.put(json.loads(line))
        messages.put(None)

    threading.Thread(target=read, daemon=True).start()

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def call(ident, method, params):
        send({"id": ident, "method": method, "params": params})
        while True:
            reply = messages.get(timeout=30)
            if reply is None:
                raise RuntimeError("app-server closed before replying")
            if reply.get("id") == ident:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply["result"]

    try:
        call(1, "initialize", {"clientInfo": {"name": "ucl-skills-audit", "version": "1"}})
        send({"method": "initialized"})
        result = call(2, "skills/list", {
            "cwds": [str(root), str(root / "tests")], "forceReload": True,
        })
        assert len(result["data"]) == 2, "Missing discovery result"
        for entry in result["data"]:
            assert not entry["errors"], entry["errors"]
            for name in expected:
                matches = [s for s in entry["skills"] if s["name"] == name]
                assert len(matches) == 1, (name, "duplicate or missing")
                skill = matches[0]
                assert skill["enabled"] and skill["scope"] == "repo", skill
                assert Path(skill["path"]).resolve() == root / ".agents/skills" / name / "SKILL.md"
                assert "$" + name in skill["interface"]["defaultPrompt"], name
        evidence = {
            "inventory": [{k: s[k] for k in ("name", "scope", "enabled")}
                          for s in result["data"][0]["skills"]],
            "data": [{"cwd": entry["cwd"], "errors": entry["errors"],
                      "totalSkills": len(entry["skills"]),
                      "skills": [s for s in entry["skills"] if s["scope"] == "repo"]}
                     for entry in result["data"]],
        }
        print(json.dumps(evidence, indent=2, ensure_ascii=False))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
