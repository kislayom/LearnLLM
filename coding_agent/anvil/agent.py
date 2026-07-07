"""The reason-act loop: plan → clarify → approve → act → verify."""

from . import parser
from .prompts import system_prompt


class Agent:
    """One task-solving session.

    llm      : adapter with .complete(messages) -> str
    tools    : anvil.tools.Tools
    config   : anvil.config.AgentConfig
    on_event : callback(kind, payload) for UIs; kinds:
               'assistant' (model text), 'tool_call', 'tool_result',
               'approval', 'final', 'error'
    """

    def __init__(self, llm, tools, config, on_event=None):
        self.llm = llm
        self.tools = tools
        self.config = config
        self.on_event = on_event or (lambda kind, payload: None)
        self.history = [{
            "role": "system",
            "content": system_prompt(tools, plan_first=config.plan_first,
                                     on_mac=config.on_mac),
        }]

    # ------------------------------------------------------------------
    def run(self, task):
        """Run one task to completion; returns the final answer string."""
        self.history.append({"role": "user", "content": task})
        repairs = 0

        for _ in range(self.config.max_steps):
            reply = self.llm.complete(self.history)
            self.history.append({"role": "assistant", "content": reply})

            call, err = parser.extract_tool_call(reply)

            if call is None and err is None:          # final answer
                self.on_event("final", reply)
                return reply

            if err is not None:                        # malformed -> repair
                repairs += 1
                if repairs > self.config.repair_attempts:
                    msg = f"giving up after {repairs} malformed tool calls: {err}"
                    self.on_event("error", msg)
                    return msg
                self.on_event("error", f"repairing tool call: {err}")
                self.history.append({"role": "user",
                                     "content": parser.repair_hint(err)})
                continue

            repairs = 0
            result = self._execute(call)
            self.on_event("tool_result", result)
            self.history.append({
                "role": "user",
                "content": f"TOOL_RESULT[{call['tool']}]:\n{result}",
            })

        msg = f"stopped: reached max_steps={self.config.max_steps}"
        self.on_event("error", msg)
        return msg

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

        return self.tools.run(name, args)

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
