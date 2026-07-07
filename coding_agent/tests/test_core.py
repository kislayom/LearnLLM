"""Offline tests: tolerant parser, tools, and a full scripted agent run.

Run from the coding_agent/ directory:
    python3 -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anvil import parser
from anvil.agent import Agent
from anvil.config import AgentConfig, guess_tier
from anvil.llm import ScriptedAdapter
from anvil.tools import Tools


class TestParser(unittest.TestCase):
    """The local-model unlock: accept messy output, reject garbage helpfully."""

    def _ok(self, text, tool, **arg_checks):
        call, err = parser.extract_tool_call(text)
        self.assertIsNone(err, f"unexpected error: {err}")
        self.assertEqual(call["tool"], tool)
        for k, v in arg_checks.items():
            self.assertEqual(call["args"][k], v)

    def test_clean_json(self):
        self._ok('{"tool": "read_file", "args": {"path": "a.py"}}',
                 "read_file", path="a.py")

    def test_fenced_json(self):
        self._ok('Sure! I\'ll read it:\n```json\n{"tool": "read_file", '
                 '"args": {"path": "a.py"}}\n```', "read_file", path="a.py")

    def test_prose_around_json(self):
        self._ok('Let me search first. {"tool": "search", "args": '
                 '{"pattern": "def main"}} That should find it.',
                 "search", pattern="def main")

    def test_single_quotes(self):
        self._ok("{'tool': 'list_dir', 'args': {'path': '.'}}",
                 "list_dir", path=".")

    def test_trailing_comma_and_python_literals(self):
        self._ok('{"tool": "write_file", "args": {"path": "x", '
                 '"content": "hi",}}', "write_file", content="hi")
        call, err = parser.extract_tool_call(
            '{"tool": "run_shell", "args": {"cmd": "ls", "wait": True}}')
        self.assertIsNone(err)
        self.assertIs(call["args"]["wait"], True)

    def test_arguments_alias(self):
        self._ok('{"tool": "read_file", "arguments": {"path": "b.txt"}}',
                 "read_file", path="b.txt")

    def test_no_tool_call_is_final_answer(self):
        call, err = parser.extract_tool_call("All done! I fixed the bug.")
        self.assertIsNone(call)
        self.assertIsNone(err)

    def test_garbage_yields_repairable_error(self):
        call, err = parser.extract_tool_call('{"tool": broken here...')
        self.assertIsNone(call)
        self.assertIsNotNone(err)
        self.assertIn("JSON", parser.repair_hint(err))


class TestTools(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tools = Tools(root=self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_write_read_edit_roundtrip(self):
        self.tools.run("write_file",
                       {"path": "pkg/hello.py", "content": "x = 1\n"})
        out = self.tools.run("read_file", {"path": "pkg/hello.py"})
        self.assertIn("x = 1", out)
        out = self.tools.run("edit_file", {"path": "pkg/hello.py",
                                           "old": "x = 1", "new": "x = 2"})
        self.assertIn("edited", out)
        self.assertIn("x = 2", self.tools.run("read_file", {"path": "pkg/hello.py"}))

    def test_edit_requires_unique_match(self):
        self.tools.run("write_file", {"path": "a.txt", "content": "dup\ndup\n"})
        out = self.tools.run("edit_file", {"path": "a.txt", "old": "dup", "new": "x"})
        self.assertIn("2 times", out)

    def test_path_escape_blocked(self):
        out = self.tools.run("read_file", {"path": "../../etc/passwd"})
        self.assertIn("ERROR", out)

    def test_syntax_check_python_catches_error(self):
        self.tools.run("write_file", {"path": "bad.py", "content": "def f(:\n"})
        out = self.tools.run("check_syntax", {"path": "bad.py"})
        self.assertIn("SYNTAX ERRORS", out)
        self.tools.run("write_file", {"path": "good.py", "content": "def f():\n    pass\n"})
        self.assertIn("syntax OK", self.tools.run("check_syntax", {"path": "good.py"}))

    def test_write_reports_syntax_error_inline(self):
        out = self.tools.run("write_file", {"path": "bad2.py", "content": "def (\n"})
        self.assertIn("SYNTAX ERRORS", out)

    def test_search_fallbacks(self):
        self.tools.run("write_file", {"path": "s.txt", "content": "needle here\n"})
        self.assertIn("needle", self.tools.run("search", {"pattern": "needle"}))
        self.assertIn("s.txt", self.tools._py_search("needle", self.dir.name))

    def test_shell_blocklist(self):
        out = self.tools.run("run_shell", {"cmd": "sudo rm -rf /"})
        self.assertIn("blocked", out)

    def test_shell_runs_and_reports_exit(self):
        out = self.tools.run("run_shell", {"cmd": "echo hi"})
        self.assertIn("exit=0", out)
        self.assertIn("hi", out)

    def test_unknown_tool_lists_available(self):
        out = self.tools.run("frobnicate", {})
        self.assertIn("unknown tool", out)
        self.assertIn("read_file", out)

    def test_mac_tool_refuses_off_mac(self):
        out = self.tools.run("mac", {"verb": "spotlight", "arg": "x"})
        if sys.platform != "darwin":
            self.assertIn("requires macOS", out)


class TestAgentLoop(unittest.TestCase):
    def _agent(self, replies, approve=None, **cfg_over):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        llm = ScriptedAdapter(replies)
        cfg = AgentConfig(plan_first=False, **cfg_over)
        tools = Tools(root=self.dir.name, approve=approve)
        return Agent(llm, tools, cfg), llm

    def test_full_task_write_then_finish(self):
        agent, llm = self._agent([
            '{"tool": "write_file", "args": {"path": "hi.py", '
            '"content": "print(\'hi\')\\n"}}',
            "Done — created hi.py that prints hi.",
        ], approve=lambda d, question_mode=False: True)
        answer = agent.run("create hi.py")
        self.assertIn("Done", answer)
        self.assertTrue(os.path.exists(os.path.join(self.dir.name, "hi.py")))
        # tool result was fed back to the model
        self.assertTrue(any("TOOL_RESULT[write_file]" in m["content"]
                            for m in agent.history))

    def test_malformed_call_gets_repaired(self):
        agent, llm = self._agent([
            '{"tool": "read_file", "args": {"path": ',      # broken
            'final answer: nothing to do',
        ])
        answer = agent.run("noop")
        self.assertIn("final answer", answer)
        self.assertTrue(any("TOOL_ERROR" in m["content"]
                            for m in agent.history))

    def test_denied_write_reports_back(self):
        agent, llm = self._agent([
            '{"tool": "write_file", "args": {"path": "x.py", "content": "1"}}',
            "OK, I won't write the file.",
        ], approve=lambda d, question_mode=False: False)
        agent.run("write x.py")
        self.assertTrue(any("DENIED" in m["content"] for m in agent.history))
        self.assertFalse(os.path.exists(os.path.join(self.dir.name, "x.py")))

    def test_max_steps_stops_runaway(self):
        agent, _ = self._agent(
            ['{"tool": "list_dir", "args": {}}'] * 5, max_steps=3)
        answer = agent.run("loop forever")
        self.assertIn("max_steps", answer)

    def test_tier_guessing(self):
        self.assertEqual(guess_tier("qwen2.5-coder:7b"), "small")
        self.assertEqual(guess_tier("claude-sonnet"), "large")
        self.assertEqual(guess_tier("devstral"), "mid")


if __name__ == "__main__":
    unittest.main()
