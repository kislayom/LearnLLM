"""Chat REPL. The desktop shell will speak to the same Agent over JSON events.

    python3 -m anvil.cli --backend ollama --model qwen2.5-coder:7b
    python3 -m anvil.cli --profile studio          # named remote endpoint
    python3 -m anvil.cli --resume                  # continue the last session
    python3 -m anvil.cli undo                      # revert last checkpoint
    python3 -m anvil.cli sessions                  # list saved transcripts
    python3 -m anvil.cli improve [--reflect] [--schedule]
"""

import argparse
import os
import sys

from . import gitops, improve, session as session_mod
from .agent import Agent
from .config import AgentConfig, resolve_profile
from .llm import LLMError, make_adapter
from .tools import Tools

C_DIM, C_YEL, C_CYN, C_GRN, C_RED, C_END = (
    "\033[2m", "\033[33m", "\033[36m", "\033[32m", "\033[31m", "\033[0m")

SLASH_HELP = """slash commands:
  /help              this help
  /skills            list available skills
  /skill <name>      inject a skill's instructions into the next task
  /sessions          list saved session transcripts
  /undo              revert the agent's last git checkpoint
  /improve           mine session logs into learned lessons now
  /quit              exit"""


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
    elif kind == "checkpoint":
        print(f"{C_GRN}  ✓ {payload}{C_END}")
    elif kind == "verify":
        first = str(payload).splitlines()[0] if payload else ""
        print(f"{C_YEL}  ⚑ verify: {first[:110]}{C_END}")
    elif kind == "error":
        print(f"{C_RED}  ! {payload}{C_END}")


# ------------------------------------------------------------- subcommands
def cmd_improve(root, args, llm=None):
    stats, excerpts = improve.mine(root)
    lessons = improve.lessons_from_stats(stats)
    if args and "--reflect" in args and llm is not None:
        try:
            lessons += improve.reflect_with_llm(llm, excerpts)
        except LLMError as e:
            print(f"{C_RED}reflection skipped (model error: {e}){C_END}")
    added = improve.update_learned(root, lessons)
    print(f"mined {stats['sessions']} sessions / {stats['tasks']} tasks "
          f"({stats['tool_calls']} tool calls)")
    for k in ("repairs", "edit_misses", "verify_fails", "denials",
              "syntax_errors", "max_steps"):
        if stats[k]:
            print(f"  {k}: {stats[k]}")
    print(f"{added} new lesson(s) → {improve.learned_path(root)}")
    if args and "--schedule" in args:
        pkgdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        print(improve.install_schedule(sys.executable, root, pkgdir))


def cmd_sessions(root):
    paths = session_mod.list_sessions(root)
    if not paths:
        print("no saved sessions (they appear in .anvil/sessions/ as you work)")
    for p in paths:
        recs = session_mod.read(p)
        tasks = [r["content"][:60] for r in recs
                 if r.get("kind") == "msg" and r.get("role") == "user"
                 and not r.get("content", "").startswith(
                     ("TOOL_RESULT", "TOOL_ERROR", "VERIFY FAILED"))]
        print(f"{os.path.basename(p):24s} {len(recs):4d} records  "
              f"{tasks[0] if tasks else '(empty)'}")


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(prog="anvil", description="local-first coding agent")
    ap.add_argument("--backend", choices=["ollama", "openai"], default="ollama")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--url", default=None, help="server URL (default per backend)")
    ap.add_argument("--api-key", default=os.environ.get("ANVIL_API_KEY"))
    ap.add_argument("--profile", default=None,
                    help="named endpoint from .anvil/config.json")
    ap.add_argument("--dir", default=".", help="project folder to work in")
    ap.add_argument("--auto", action="store_true",
                    help="auto-approve writes/shell (careful!)")
    ap.add_argument("--no-plan", action="store_true", help="skip plan-first mode")
    ap.add_argument("--no-verify", action="store_true",
                    help="don't auto-run the project's tests after changes")
    ap.add_argument("--no-save", action="store_true",
                    help="don't persist this session to .anvil/sessions/")
    ap.add_argument("--resume", action="store_true",
                    help="continue the most recent saved session")
    ap.add_argument("--reflect", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--schedule", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("task", nargs="*",
                    help="one-shot task, or: undo | sessions | improve")
    args = ap.parse_args(argv)
    root = os.path.realpath(args.dir)

    # ---- endpoint resolution (flags < profile) ----
    backend, model, url, api_key = args.backend, args.model, args.url, args.api_key
    try:
        prof = resolve_profile(args.profile, root)
    except ValueError as e:
        print(f"{C_RED}{e}{C_END}")
        return
    if prof and (args.profile or (backend == "ollama" and args.url is None
                                  and not args.task)):
        # explicit --profile always wins; a default_profile only kicks in
        # when the user didn't pass explicit endpoint flags
        if args.profile:
            backend = prof.get("backend", backend)
            model = prof.get("model", model)
            url = prof.get("url", url)
            api_key = prof.get("api_key") or api_key

    # ---- subcommands ----
    if args.task and args.task[0] == "undo":
        print(gitops.undo_last(root))
        return
    if args.task and args.task[0] == "sessions":
        cmd_sessions(root)
        return
    if args.task and args.task[0] == "improve":
        extra = []
        if args.reflect:
            extra.append("--reflect")
        if args.schedule:
            extra.append("--schedule")
        llm = make_adapter(backend, model, url, api_key) if args.reflect else None
        cmd_improve(root, extra, llm)
        return

    # ---- agent session ----
    llm = make_adapter(backend, model, url, api_key)
    cfg = AgentConfig.for_model(model, auto_approve=args.auto,
                                plan_first=not args.no_plan,
                                auto_verify=not args.no_verify)
    tools = Tools(root=root, approve=_approve, shell_timeout=cfg.shell_timeout)

    sess, resume_msgs = None, None
    if not args.no_save:
        if args.resume:
            prior = session_mod.list_sessions(root)
            if prior:
                latest = prior[-1]
                _, resume_msgs = session_mod.load_history(latest)
                sid = os.path.splitext(os.path.basename(latest))[0]
                sess = session_mod.Session(root, session_id=sid)
                print(f"{C_DIM}resumed {sid} ({len(resume_msgs)} messages){C_END}")
        if sess is None:
            sess = session_mod.Session(root, meta={"backend": backend,
                                                   "model": model,
                                                   "root": root})

    agent = Agent(llm, tools, cfg, on_event=_on_event, session=sess,
                  resume=resume_msgs)

    print(f"{C_GRN}anvil{C_END} · {backend}:{model} · tier={cfg.tier} · dir={root}"
          + (f" · session={sess.id}" if sess else ""))

    def run_one(task):
        try:
            answer = agent.run(task)
            print(f"\n{C_GRN}{answer}{C_END}\n")
        except LLMError as e:
            print(f"{C_RED}model error: {e}{C_END}")

    if args.task:
        run_one(" ".join(args.task))
        return

    print(f"{C_DIM}type a task, /help for commands, 'quit' to exit{C_END}")
    pending_skill = ""
    while True:
        try:
            task = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not task:
            continue
        if task.lower() in ("quit", "exit", "q", "/quit"):
            break
        if task.startswith("/"):
            cmd, _, rest = task.partition(" ")
            if cmd == "/help":
                print(SLASH_HELP)
            elif cmd == "/skills":
                for s in tools.skills.values():
                    print(f"  {s['name']:16s} {s['description'][:70]}")
                if not tools.skills:
                    print("  (none — add .md files to .anvil/skills/)")
            elif cmd == "/skill":
                s = tools.skills.get(rest.strip())
                if s:
                    pending_skill = (f"Use this skill for the next task:\n"
                                     f"{s['body']}\n\n")
                    print(f"{C_GRN}skill '{s['name']}' will be attached to "
                          f"your next task{C_END}")
                else:
                    print(f"{C_RED}unknown skill{C_END}")
            elif cmd == "/sessions":
                cmd_sessions(root)
            elif cmd == "/undo":
                print(gitops.undo_last(root))
            elif cmd == "/improve":
                cmd_improve(root, [])
            else:
                print(SLASH_HELP)
            continue
        run_one(pending_skill + task)
        pending_skill = ""


if __name__ == "__main__":
    main()
