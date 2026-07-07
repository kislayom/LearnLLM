"""Anvil eval harness: measure the agent, don't just claim things.

Each task lives in evals/tasks/<name>/:
    task.json   {"prompt": "...", "check": "python3 check.py", "steps": 15}
    files/      starting workspace (copied to a temp dir)
    check.py    exits 0 = pass, non-zero = fail, 2 = skip (toolchain missing)

The agent runs against a REAL backend with auto-approve on (evals are
sandboxed temp dirs), then the check script judges the result. Output is a
pass-rate table you can compare across models and agent versions.

Usage (on your Mac, with a model server running):
    python3 -m evals.harness --backend ollama --model qwen2.5-coder:7b
    python3 -m evals.harness --backend openai --url http://localhost:1234/v1 --model local
    python3 -m evals.harness --list
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anvil.agent import Agent          # noqa: E402
from anvil.config import AgentConfig   # noqa: E402
from anvil.llm import LLMError, make_adapter  # noqa: E402
from anvil.tools import Tools          # noqa: E402

TASKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")


def discover():
    tasks = []
    for name in sorted(os.listdir(TASKS_DIR)):
        meta = os.path.join(TASKS_DIR, name, "task.json")
        if os.path.exists(meta):
            with open(meta, "r", encoding="utf-8") as f:
                tasks.append((name, json.load(f)))
    return tasks


def run_task(name, meta, backend, model, url, api_key, quiet=True):
    src = os.path.join(TASKS_DIR, name, "files")
    work = tempfile.mkdtemp(prefix=f"anvil-eval-{name}-")
    if os.path.isdir(src):
        shutil.copytree(src, work, dirs_exist_ok=True)

    llm = make_adapter(backend, model, url, api_key)
    cfg = AgentConfig.for_model(model,
                                auto_approve=True,      # sandboxed temp dir
                                plan_first=False,       # evals measure acting
                                git_checkpoints=False,
                                max_steps=meta.get("steps", 15))
    tools = Tools(root=work, approve=lambda d, question_mode=False:
                  "(no user in eval; use your best judgment)" if question_mode else True)
    events = []
    agent = Agent(llm, tools, cfg,
                  on_event=lambda k, p: events.append((k, str(p)[:200])))

    t0 = time.time()
    status, detail = "fail", ""
    try:
        agent.run(meta["prompt"])
        # graders live outside files/ so the agent can't see or game them;
        # copy them in only after the run
        task_dir = os.path.join(TASKS_DIR, name)
        for item in os.listdir(task_dir):
            if item not in ("files", "task.json"):
                shutil.copy(os.path.join(task_dir, item), work)
        r = subprocess.run(meta["check"], shell=True, cwd=work,
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0:
            status = "pass"
        elif r.returncode == 2:
            status = "skip"
        detail = (r.stdout + r.stderr).strip().splitlines()
        detail = detail[-1][:120] if detail else ""
    except LLMError as e:
        status, detail = "error", str(e)[:120]
    except subprocess.TimeoutExpired:
        status, detail = "fail", "check timed out"
    finally:
        elapsed = time.time() - t0
        if not quiet:
            for k, p in events:
                print(f"    [{k}] {p}")
        shutil.rmtree(work, ignore_errors=True)

    steps = sum(1 for k, _ in events if k == "tool_call")
    return status, steps, elapsed, detail


def main(argv=None):
    ap = argparse.ArgumentParser(description="run the anvil eval suite")
    ap.add_argument("--backend", choices=["ollama", "openai"], default="ollama")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--url", default=None)
    ap.add_argument("--api-key", default=os.environ.get("ANVIL_API_KEY"))
    ap.add_argument("--only", default=None, help="run tasks whose name contains this")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    tasks = discover()
    if args.only:
        tasks = [(n, m) for n, m in tasks if args.only in n]
    if args.list or not tasks:
        for n, m in tasks:
            print(f"{n:28s} {m['prompt'][:70]}")
        if not tasks:
            print("(no tasks found)")
        return 0

    print(f"anvil evals · {args.backend}:{args.model} · {len(tasks)} tasks\n")
    results = []
    for name, meta in tasks:
        print(f"  {name:28s} ...", end="", flush=True)
        status, steps, secs, detail = run_task(
            name, meta, args.backend, args.model, args.url, args.api_key,
            quiet=not args.verbose)
        results.append(status)
        mark = {"pass": "✅", "fail": "❌", "skip": "⏭", "error": "💥"}[status]
        print(f"\r  {name:28s} {mark} {status:5s} {steps:2d} steps "
              f"{secs:5.1f}s  {detail}")

    ran = [r for r in results if r in ("pass", "fail")]
    passed = sum(1 for r in ran if r == "pass")
    print(f"\npass rate: {passed}/{len(ran)}"
          + (f"  (+{results.count('skip')} skipped, "
             f"{results.count('error')} errors)" if len(ran) < len(results) else ""))
    return 0 if passed == len(ran) and ran else 1


if __name__ == "__main__":
    raise SystemExit(main())
