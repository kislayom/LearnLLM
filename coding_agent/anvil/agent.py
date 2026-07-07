"""The reason-act loop: plan → clarify → approve → act → verify.

v0.5 additions over the naive loop:
- repo map injected with the task (relevance-ranked, byte-budgeted)
- history compaction before each model call (small contexts survive long tasks)
- git checkpoint before the first mutation; one-command undo
- auto-verify: when the model claims it's done after mutating, the project's
  test command runs; failures are fed back and the loop continues.
"""

from . import compact, gitops, improve, parser, repomap, skills as skills_mod, verify
from .prompts import project_instructions, system_prompt

MUTATING = ("write_file", "edit_file", "run_shell")


class Agent:
    """One task-solving session.

    llm      : adapter with .complete(messages) -> str
    tools    : anvil.tools.Tools
    config   : anvil.config.AgentConfig
    on_event : callback(kind, payload); kinds: 'assistant', 'tool_call',
               'tool_result', 'approval', 'checkpoint', 'verify',
               'final', 'error'
    session  : anvil.session.Session for persistence (optional)
    resume   : prior messages (from session.load_history) to continue from
    """

    def __init__(self, llm, tools, config, on_event=None, session=None,
                 resume=None):
        self.llm = llm
        self.tools = tools
        self.config = config
        self.session = session
        raw_event = on_event or (lambda kind, payload: None)
        if session is not None:
            def logged(kind, payload, _raw=raw_event):
                session.log_event(kind, payload)
                _raw(kind, payload)
            self.on_event = logged
        else:
            self.on_event = raw_event

        skills = skills_mod.load_skills(tools.root)
        tools.skills = skills
        self.history = [{
            "role": "system",
            "content": system_prompt(
                tools, plan_first=config.plan_first, on_mac=config.on_mac,
                skills_text=skills_mod.prompt_lines(skills),
                lessons_text=improve.learned_lessons(tools.root),
                project_text=project_instructions(tools.root)),
        }]
        if resume:
            self.history.extend(resume)
        self._mutated = False
        self._checkpointed = False
        self._verify_rounds = 0

    def _add(self, role, content):
        self.history.append({"role": role, "content": content})
        if self.session is not None:
            self.session.log_message(role, content)

    # ------------------------------------------------------------------
    def run(self, task):
        """Run one task to completion; returns the final answer string."""
        self._add("user", self._task_msg(task))
        repairs = 0

        for _ in range(self.config.max_steps):
            compact.compact(self.history, self.config.context_tokens)
            reply = self.llm.complete(self.history)
            self._add("assistant", reply)
            self.on_event("assistant", reply)

            call, err = parser.extract_tool_call(reply)

            if call is None and err is None:            # model says done
                verdict = self._maybe_verify()
                if verdict is None:                      # verified (or n/a)
                    self.on_event("final", reply)
                    return reply
                self._add("user", verdict)
                continue                                 # go fix the failures

            if err is not None:                          # malformed -> repair
                repairs += 1
                if repairs > self.config.repair_attempts:
                    msg = f"giving up after {repairs} malformed tool calls: {err}"
                    self.on_event("error", msg)
                    return msg
                self.on_event("error", f"repairing tool call: {err}")
                self._add("user", parser.repair_hint(err))
                continue

            repairs = 0
            result = self._execute(call)
            self.on_event("tool_result", result)
            self._add("user", f"TOOL_RESULT[{call['tool']}]:\n{result}")

        msg = f"stopped: reached max_steps={self.config.max_steps}"
        self.on_event("error", msg)
        return msg

    # ------------------------------------------------------------------
    def _task_msg(self, task):
        if not self.config.use_repo_map:
            return task
        rmap = repomap.build_map(self.tools.root, task=task,
                                 budget_chars=self.config.repo_map_chars)
        if not rmap:
            return task
        return (f"{task}\n\nREPO MAP (files and symbols, most relevant "
                f"first — read files before editing):\n{rmap}")

    # ------------------------------------------------------------------
    def _maybe_verify(self):
        """Returns None if fine to finish, else a feedback message."""
        if (not self.config.auto_verify or not self._mutated
                or self._verify_rounds >= self.config.max_verify_rounds):
            return None
        cmd = verify.detect(self.tools.root)
        if not cmd:
            return None
        self._verify_rounds += 1
        ok, report = verify.run(self.tools.root, cmd,
                                timeout=self.config.shell_timeout * 5)
        self.on_event("verify", report)
        if ok:
            self._mutated = False   # verified clean; don't re-run next time
            return None
        return (f"VERIFY FAILED — the project's tests do not pass after your "
                f"changes:\n{report}\nFix the failures, then finish. "
                f"({self.config.max_verify_rounds - self._verify_rounds} "
                f"verify attempts left)")

    # ------------------------------------------------------------------
    def _execute(self, call):
        name, args = call["tool"], call["args"]
        self.on_event("tool_call", call)

        if (not self.config.auto_approve
                and name != "ask_user"
                and self.tools.needs_approval(name, args)):
            desc = self._describe(name, args)
            self.on_event("approval", desc)
            if self.tools.approve is None:
                return "DENIED: no approver configured; use ask_user to discuss instead."
            verdict = self.tools.approve(desc)
            if verdict is not True and str(verdict).strip().lower() not in ("y", "yes", "true"):
                reason = "" if verdict in (False, None) else f" User said: {verdict}"
                return f"DENIED by user.{reason} Adjust your approach or ask_user why."

        if name in MUTATING:
            self._checkpoint_once()
            self._mutated = True

        return self.tools.run(name, args)

    def _checkpoint_once(self):
        if self._checkpointed or not self.config.git_checkpoints:
            return
        self._checkpointed = True
        h = gitops.checkpoint(self.tools.root, "checkpoint before task")
        if h:
            self.on_event("checkpoint",
                          f"saved pre-task checkpoint {h} (revert: anvil undo)")

    @staticmethod
    def _describe(name, args):
        if name == "run_shell":
            return f"run shell command: {args.get('cmd', '')}"
        if name == "write_file":
            content = str(args.get("content", ""))
            return (f"write {len(content)} chars to {args.get('path')}\n"
                    f"--- preview ---\n{content[:600]}")
        if name == "edit_file":
            return (f"edit {args.get('path')}\n--- remove ---\n"
                    f"{str(args.get('old',''))[:400]}\n--- insert ---\n"
                    f"{str(args.get('new',''))[:400]}")
        if name == "mac":
            return f"mac {args.get('verb')}: {args.get('arg', '')}"
        return f"{name} {args}"
