"""Chat REPL. The desktop shell will speak to the same Agent over JSON events.

    python3 -m anvil.cli --backend ollama --model qwen2.5-coder:7b
    python3 -m anvil.cli --backend openai --url http://localhost:1234/v1 --model local
"""

import argparse
import os
import sys

from .agent import Agent
from .config import AgentConfig
from .llm import LLMError, make_adapter
from .tools import Tools

C_DIM, C_YEL, C_CYN, C_GRN, C_RED, C_END = (
    "\033[2m", "\033[33m", "\033[36m", "\033[32m", "\033[31m", "\033[0m")


def _approve(desc, question_mode=False):
    """Terminal approval / question channel."""
    if question_mode:
        print(f"\n{C_YEL}🤔 Anvil asks:{C_END} {desc[10:] if desc.startswith('QUESTION:') else desc}")
        return input(f"{C_YEL}your answer> {C_END}").strip() or "(no answer)"
    print(f"\n{C_YEL}⚠ approval needed:{C_END}\n{desc}")
    ans = input(f"{C_YEL}allow? [y/N/reason] {C_END}").strip()
    return True if ans.lower() in ("y", "yes") else (ans or False)


def _on_event(kind, payload):
    if kind == "tool_call":
        print(f"{C_CYN}→ {payload['tool']}{C_END} {C_DIM}{payload['args']}{C_END}")
    elif kind == "tool_result":
        first = str(payload).splitlines()[0] if payload else ""
        print(f"{C_DIM}  {first[:120]}{C_END}")
    elif kind == "error":
        print(f"{C_RED}  ! {payload}{C_END}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="anvil", description="local-first coding agent")
    ap.add_argument("--backend", choices=["ollama", "openai"], default="ollama")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--url", default=None, help="server URL (default per backend)")
    ap.add_argument("--api-key", default=os.environ.get("ANVIL_API_KEY"))
    ap.add_argument("--dir", default=".", help="project folder to work in")
    ap.add_argument("--auto", action="store_true",
                    help="auto-approve writes/shell (careful!)")
    ap.add_argument("--no-plan", action="store_true", help="skip plan-first mode")
    ap.add_argument("task", nargs="*", help="one-shot task (else interactive)")
    args = ap.parse_args(argv)

    llm = make_adapter(args.backend, args.model, args.url, args.api_key)
    cfg = AgentConfig.for_model(args.model, auto_approve=args.auto,
                                plan_first=not args.no_plan)
    tools = Tools(root=args.dir, approve=_approve,
                  shell_timeout=cfg.shell_timeout)
    agent = Agent(llm, tools, cfg, on_event=_on_event)

    print(f"{C_GRN}anvil{C_END} · {args.backend}:{args.model} · tier={cfg.tier} "
          f"· dir={os.path.realpath(args.dir)}")

    def run_one(task):
        try:
            answer = agent.run(task)
            print(f"\n{C_GRN}{answer}{C_END}\n")
        except LLMError as e:
            print(f"{C_RED}model error: {e}{C_END}")

    if args.task:
        run_one(" ".join(args.task))
        return

    print(f"{C_DIM}type a task, or 'quit'{C_END}")
    while True:
        try:
            task = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if task.lower() in ("quit", "exit", "q"):
            break
        if task:
            run_one(task)


if __name__ == "__main__":
    main()
