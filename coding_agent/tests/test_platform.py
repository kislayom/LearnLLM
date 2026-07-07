"""Tests for the platform layer: session persistence + resume, skills,
profiles (remote endpoints), self-improvement mining, and prompt injection."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anvil import improve, session, skills
from anvil.agent import Agent
from anvil.config import AgentConfig, resolve_profile
from anvil.llm import ScriptedAdapter
from anvil.tools import Tools


class TestSession(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name

    def test_roundtrip_and_resume(self):
        s = session.Session(self.root, meta={"model": "m1"})
        s.log_message("user", "fix the bug")
        s.log_message("assistant", "reading file...")
        s.log_event("tool_call", {"tool": "read_file"})
        paths = session.list_sessions(self.root)
        self.assertEqual(len(paths), 1)
        meta, msgs = session.load_history(paths[0])
        self.assertEqual(meta["model"], "m1")
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])

    def test_agent_persists_everything(self):
        s = session.Session(self.root, meta={})
        llm = ScriptedAdapter([
            '{"tool": "write_file", "args": {"path": "a.py", "content": "x=1\\n"}}',
            "Done.",
        ])
        cfg = AgentConfig(plan_first=False, auto_approve=True,
                          git_checkpoints=False, auto_verify=False,
                          use_repo_map=False)
        agent = Agent(llm, Tools(root=self.root), cfg, session=s)
        agent.run("create a.py")
        recs = session.read(s.path)
        kinds = {(r.get("kind"), r.get("event")) for r in recs}
        self.assertIn(("event", "tool_call"), kinds)     # edits captured
        self.assertIn(("event", "final"), kinds)
        contents = [r.get("content", "") for r in recs if r.get("kind") == "msg"]
        self.assertTrue(any("TOOL_RESULT[write_file]" in c for c in contents))

    def test_resume_continues_history(self):
        s1 = session.Session(self.root, meta={})
        llm = ScriptedAdapter(["First answer, no tools needed."])
        cfg = AgentConfig(plan_first=False, auto_verify=False,
                          use_repo_map=False, git_checkpoints=False)
        Agent(llm, Tools(root=self.root), cfg, session=s1).run("task one")

        _, msgs = session.load_history(session.list_sessions(self.root)[-1])
        llm2 = ScriptedAdapter(["Second answer."])
        agent2 = Agent(llm2, Tools(root=self.root), cfg, resume=msgs)
        agent2.run("task two")
        joined = " ".join(m["content"] for m in agent2.history)
        self.assertIn("task one", joined)
        self.assertIn("task two", joined)

    def test_torn_line_tolerated(self):
        s = session.Session(self.root, meta={})
        s.log_message("user", "hello")
        with open(s.path, "a") as f:
            f.write('{"kind": "msg", "role": "us')   # crash mid-write
        self.assertEqual(len(session.read(s.path)), 2)  # meta + msg survive


class TestSkills(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name
        d = os.path.join(self.root, ".anvil", "skills")
        os.makedirs(d)
        with open(os.path.join(d, "release.md"), "w") as f:
            f.write("---\nname: release\ndescription: cut a release\n---\n"
                    "1. bump version\n2. tag\n")
        with open(os.path.join(d, "review.md"), "w") as f:
            f.write("# thorough code review\ncheck edge cases\n")

    def test_load_and_parse(self):
        sk = skills.load_skills(self.root)
        self.assertEqual(sk["release"]["description"], "cut a release")
        self.assertIn("bump version", sk["release"]["body"])
        self.assertEqual(sk["review"]["description"], "thorough code review")

    def test_skill_tool_and_prompt_listing(self):
        sk = skills.load_skills(self.root)
        tools = Tools(root=self.root, skills=sk)
        self.assertIn("bump version", tools.run("skill", {"name": "release"}))
        self.assertIn("unknown skill", tools.run("skill", {"name": "nope"}))
        self.assertIn(("skill", '{"name"} -> load a skill\'s full instructions'),
                      tools.spec())
        listing = skills.prompt_lines(sk)
        self.assertIn("release: cut a release", listing)

    def test_agent_system_prompt_lists_skills(self):
        cfg = AgentConfig(use_repo_map=False, git_checkpoints=False)
        agent = Agent(ScriptedAdapter([]), Tools(root=self.root), cfg)
        self.assertIn("release", agent.history[0]["content"])


class TestProfiles(unittest.TestCase):
    def test_resolve_remote_profile(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "config.json")
            with open(cfg, "w") as f:
                json.dump({"profiles": {"studio": {
                    "backend": "openai", "model": "qwen3-32b",
                    "url": "http://mac-studio.local:1234/v1",
                    "api_key_env": "STUDIO_KEY"}},
                    "default_profile": "studio"}, f)
            os.environ["STUDIO_KEY"] = "sekrit"
            try:
                p = resolve_profile("studio", d, paths=[cfg])
                self.assertEqual(p["url"], "http://mac-studio.local:1234/v1")
                self.assertEqual(p["api_key"], "sekrit")
                # default profile applies when none named
                self.assertEqual(resolve_profile(None, d, paths=[cfg])["model"],
                                 "qwen3-32b")
            finally:
                del os.environ["STUDIO_KEY"]

    def test_unknown_profile_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                resolve_profile("nope", d, paths=[])
            # no profile configured at all -> None, not an error
            self.assertIsNone(resolve_profile(None, d, paths=[]))


class TestImprove(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = self.dir.name

    def _seed_history(self):
        s = session.Session(self.root, meta={})
        s.log_message("user", "fix the parser")
        for _ in range(4):
            s.log_message("user", "TOOL_ERROR: could not parse your tool call")
        for _ in range(3):
            s.log_message("user", "TOOL_RESULT[edit_file]:\nERROR: `old` text "
                                  "not found. Read the file...")
        for _ in range(2):
            s.log_message("user", "VERIFY FAILED — the project's tests do not "
                                  "pass after your changes:\n$ pytest\nexit=1")
        s.log_event("tool_call", {"tool": "read_file"})

    def test_mine_and_distill(self):
        self._seed_history()
        stats, excerpts = improve.mine(self.root)
        self.assertEqual(stats["repairs"], 4)
        self.assertEqual(stats["edit_misses"], 3)
        self.assertEqual(stats["verify_fails"], 2)
        lessons = improve.lessons_from_stats(stats)
        joined = " ".join(lessons)
        self.assertIn("ONE clean JSON object", joined)
        self.assertIn("read_file first", joined)
        self.assertIn("run_tests BEFORE", joined)

    def test_learned_md_dedup_and_injection(self):
        added = improve.update_learned(self.root, ["Always run tests first."])
        self.assertEqual(added, 1)
        # re-adding the same lesson is a no-op
        self.assertEqual(
            improve.update_learned(self.root, ["always RUN tests first."]), 0)
        text = improve.learned_lessons(self.root)
        self.assertIn("Always run tests first.", text)
        # lessons reach the agent's system prompt
        cfg = AgentConfig(use_repo_map=False, git_checkpoints=False)
        agent = Agent(ScriptedAdapter([]), Tools(root=self.root), cfg)
        self.assertIn("Always run tests first.", agent.history[0]["content"])

    def test_lesson_cap(self):
        improve.update_learned(self.root, [f"lesson number {i}" for i in range(30)])
        text = improve.learned_lessons(self.root, budget_chars=100000)
        self.assertNotIn("lesson number 0", text)     # oldest evicted
        self.assertIn("lesson number 29", text)

    def test_reflect_parses_bullets(self):
        llm = ScriptedAdapter(["Here you go:\n- Always check the diff before "
                               "writing.\n- Prefer smaller edits over rewrites.\n"
                               "ignore this line"])
        lessons = improve.reflect_with_llm(llm, ["[edit-miss] ..."])
        self.assertEqual(len(lessons), 2)

    def test_plist_generation(self):
        p = improve.gen_plist("/usr/bin/python3", "/Users/k/proj", "/opt/anvil", 4)
        self.assertIn("dev.anvil.improve", p)
        self.assertIn("<integer>4</integer>", p)
        msg = improve.install_schedule("/usr/bin/python3", "/p", "/a",
                                       platform="linux")
        self.assertIn("cron", msg)


class TestProjectInstructions(unittest.TestCase):
    def test_anvil_md_injected(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ANVIL.md"), "w") as f:
                f.write("Use tabs, never spaces. Run `make lint` after edits.")
            cfg = AgentConfig(use_repo_map=False, git_checkpoints=False)
            agent = Agent(ScriptedAdapter([]), Tools(root=d), cfg)
            self.assertIn("make lint", agent.history[0]["content"])


if __name__ == "__main__":
    unittest.main()
