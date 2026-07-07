"""Tests for the v0.5 engine: robust edits, repo map, verify loop, compaction,
git checkpoints. All offline; the verify-loop test runs a real unittest
subprocess against a scripted model."""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anvil import compact, gitops, repomap, verify
from anvil.agent import Agent
from anvil.config import AgentConfig
from anvil.edits import EditError, apply_edit, unified_diff
from anvil.llm import ScriptedAdapter
from anvil.tools import Tools


class TestEdits(unittest.TestCase):
    def test_exact(self):
        out, how = apply_edit("a\nb\nc\n", "b", "B")
        self.assertEqual(out, "a\nB\nc\n")
        self.assertEqual(how, "exact")

    def test_trailing_whitespace_forgiven(self):
        text = "def f():   \n    return 1\n"
        out, how = apply_edit(text, "def f():\n    return 1", "def f():\n    return 2")
        self.assertIn("return 2", out)
        self.assertEqual(how, "trailing-ws")

    def test_indent_shift_reindents_replacement(self):
        text = "class A:\n        def f(self):\n            return 1\n"
        # model quotes it with 4-space indent instead of the file's 8
        out, how = apply_edit(text,
                              "    def f(self):\n        return 1",
                              "    def f(self):\n        return 2")
        self.assertEqual(how, "indent-shift")
        self.assertIn("        def f(self):", out)   # file indent preserved
        self.assertIn("            return 2", out)

    def test_fuzzy_close_match(self):
        text = "x = compute_total(items, tax_rate)\nprint(x)\n"
        out, how = apply_edit(text,
                              "x = compute_total(items,tax_rate)",  # missing space
                              "x = compute_total(items, 0.19)")
        self.assertIn("0.19", out)
        self.assertTrue(how.startswith("fuzzy"))

    def test_ambiguous_raises(self):
        with self.assertRaises(EditError):
            apply_edit("dup\ndup\n", "dup", "x")

    def test_not_found_shows_closest(self):
        try:
            apply_edit("alpha beta gamma\n", "alpha betta gamma zeta delta", "x")
        except EditError as e:
            self.assertIn("not found", str(e))
        else:
            self.fail("expected EditError")

    def test_unified_diff(self):
        d = unified_diff("f.py", "a\n", "b\n")
        self.assertIn("-a", d)
        self.assertIn("+b", d)


class TestRepoMap(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        r = self.dir.name
        os.makedirs(os.path.join(r, "src"))
        with open(os.path.join(r, "src", "parser.py"), "w") as f:
            f.write("class Parser:\n    pass\n\ndef parse_block(x):\n    pass\n")
        with open(os.path.join(r, "src", "app.js"), "w") as f:
            f.write("export function main() {}\nconst helper = () => {}\n")
        with open(os.path.join(r, "notes.txt"), "w") as f:
            f.write("not code\n")

    def test_symbols_extracted(self):
        m = repomap.build_map(self.dir.name)
        self.assertIn("Parser", m)
        self.assertIn("parse_block", m)
        self.assertIn("main", m)
        self.assertNotIn("notes.txt", m)

    def test_task_relevance_ranks_first(self):
        m = repomap.build_map(self.dir.name, task="fix the Parser class bug")
        self.assertLess(m.index("parser.py"), m.index("app.js"))

    def test_budget_respected(self):
        m = repomap.build_map(self.dir.name, budget_chars=60)
        self.assertLessEqual(len(m), 200)   # entry + "more files" marker


class TestVerify(unittest.TestCase):
    def test_detect_unittest_project(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "test_x.py"), "w") as f:
                f.write("import unittest\n")
            cmd = verify.detect(d)
            self.assertIsNotNone(cmd)
            self.assertIn("test", cmd)

    def test_detect_override_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, ".anvil-test"), "w") as f:
                f.write("echo custom && true\n")
            self.assertEqual(verify.detect(d), "echo custom && true")

    def test_detect_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(verify.detect(d))

    def test_run_reports_pass_fail(self):
        with tempfile.TemporaryDirectory() as d:
            ok, rep = verify.run(d, "true")
            self.assertTrue(ok)
            ok, rep = verify.run(d, "echo boom && false")
            self.assertFalse(ok)
            self.assertIn("boom", rep)


class TestCompact(unittest.TestCase):
    def test_under_budget_untouched(self):
        h = [{"role": "system", "content": "s"},
             {"role": "user", "content": "task"}]
        before = [dict(m) for m in h]
        compact.compact(h, budget_tokens=1000)
        self.assertEqual(h, before)

    def test_old_tool_results_collapse_recent_kept(self):
        h = ([{"role": "system", "content": "s"},
              {"role": "user", "content": "task"}]
             + [{"role": "user",
                 "content": "TOOL_RESULT[read_file]:\n" + "x" * 2000}
                for _ in range(10)])
        compact.compact(h, budget_tokens=1500)
        self.assertIn("compacted", h[2]["content"])          # old: collapsed
        self.assertNotIn("compacted", h[-1]["content"])      # recent: intact


class TestVerifyLoop(unittest.TestCase):
    """End-to-end: model claims done with failing tests -> loop feeds failures
    back -> model fixes -> verify passes -> final answer accepted."""

    def test_agent_fixes_until_green(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        with open(os.path.join(d.name, "lib.py"), "w") as f:
            f.write("def add(a, b):\n    return a - b\n")
        with open(os.path.join(d.name, "test_lib.py"), "w") as f:
            f.write(textwrap.dedent("""\
                import unittest
                from lib import add

                class T(unittest.TestCase):
                    def test_add(self):
                        self.assertEqual(add(2, 3), 5)

                if __name__ == "__main__":
                    unittest.main()
                """))

        llm = ScriptedAdapter([
            # 1: model "fixes" nothing relevant, then claims done
            '{"tool": "edit_file", "args": {"path": "lib.py", '
            '"old": "def add(a, b):", "new": "def add(a, b):  # reviewed"}}',
            "Done, add() looks correct to me.",
            # 3: verify failed -> real fix
            '{"tool": "edit_file", "args": {"path": "lib.py", '
            '"old": "return a - b", "new": "return a + b"}}',
            "Fixed: add() now returns a + b. Tests pass.",
        ])
        cfg = AgentConfig(plan_first=False, auto_approve=True,
                          git_checkpoints=False, use_repo_map=False,
                          auto_verify=True, max_verify_rounds=2)
        agent = Agent(llm, Tools(root=d.name), cfg)
        answer = agent.run("make sure add() is correct")

        self.assertIn("Fixed", answer)
        self.assertTrue(any("VERIFY FAILED" in m["content"]
                            for m in agent.history))
        with open(os.path.join(d.name, "lib.py")) as f:
            self.assertIn("a + b", f.read())


class TestGitOps(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name
        subprocess.run(["git", "init", "-q", self.root], check=True)

    def _write(self, name, content):
        with open(os.path.join(self.root, name), "w") as f:
            f.write(content)

    def test_checkpoint_and_undo(self):
        self._write("a.txt", "v1")
        h1 = gitops.checkpoint(self.root, "first")
        self.assertIsNotNone(h1)
        self._write("a.txt", "v2")
        h2 = gitops.checkpoint(self.root, "second")
        self.assertIsNotNone(h2)
        msg = gitops.undo_last(self.root)
        self.assertIn("reverted", msg)
        with open(os.path.join(self.root, "a.txt")) as f:
            self.assertEqual(f.read(), "v1")

    def test_undo_refuses_user_commits(self):
        self._write("a.txt", "v1")
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.root, "-c", "user.name=u",
                        "-c", "user.email=u@x", "commit", "-qm", "user work"],
                       check=True)
        self.assertIn("refusing", gitops.undo_last(self.root))

    def test_checkpoint_noop_when_clean(self):
        self._write("a.txt", "v1")
        gitops.checkpoint(self.root, "first")
        self.assertIsNone(gitops.checkpoint(self.root, "again"))


if __name__ == "__main__":
    unittest.main()
