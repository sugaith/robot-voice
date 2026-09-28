"""python3 -m unittest discover tests -- runs silent, in a throwaway home."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HOME = tempfile.mkdtemp(prefix="robot-voice-test-")
SPOKEN = os.path.join(HOME, "spoken.log")
os.environ["ROBOT_VOICE_HOME"] = HOME
os.environ["ROBOT_VOICE_DRYRUN"] = SPOKEN
os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "CLAUDE_PLUGIN_OPTION_GEMINI_API_KEY"):
    os.environ.pop(var, None)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from robot_voice import claude_code, ctl, engine, hermes  # noqa: E402

REPLY = ("I fixed the race in `stop-hook.py`.\n\n```py\nx = 1\n```\n\n"
         "| a | b |\n|---|---|\n| 1 | 2 |\n\nWant me to open a PR?")


def spoken():
    try:
        with open(SPOKEN) as f:
            return [line.rstrip("\n").split("\t", 1) for line in f if line.strip()]
    except OSError:
        return []


def wait_for_speech(count, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(spoken()) >= count:
            return spoken()
        time.sleep(0.05)
    return spoken()


class Base(unittest.TestCase):
    def setUp(self):
        for name in ("config.json", "spoken.log", ".last-session"):
            try:
                os.remove(os.path.join(HOME, name))
            except OSError:
                pass
        engine.save_config(dict(engine.DEFAULTS, backend="say"))


class Shaping(Base):
    def test_brief_keeps_first_sentence_and_closing_question(self):
        line = engine.shape(REPLY, engine.load_config(), "brief")
        self.assertEqual(line, "I fixed the race in. Want me to open a PR?")

    def test_clean_drops_code_tables_and_paths(self):
        text = engine.clean(REPLY)
        self.assertNotIn("x = 1", text)
        self.assertNotIn("|", text)
        self.assertNotIn("stop-hook.py", text)

    def test_slash_commands_survive(self):
        self.assertIn("/speak", engine.clean("Run /speak off to mute."))


class ClaudeCode(Base):
    def test_stop_speaks_last_assistant_message(self):
        claude_code.stop({"session_id": "s1", "last_assistant_message": REPLY})
        self.assertEqual(spoken(), [["say", "I fixed the race in. Want me to open a PR?"]])

    def test_stop_again_with_same_reply_is_silent(self):
        payload = {"session_id": "s2", "last_assistant_message": REPLY}
        claude_code.stop(payload)
        claude_code.stop(payload)  # /clear, resume and compact re-fire Stop
        self.assertEqual(len(spoken()), 1)

    def test_muted_reply_is_still_remembered_for_repeat(self):
        ctl.run(["off"])
        claude_code.stop({"session_id": "s3", "last_assistant_message": "Muted reply."})
        self.assertEqual(spoken(), [])
        self.assertEqual(ctl.run(["repeat", "show"], session="s3"), "Muted reply.")

    def test_known_subcommand_is_answered_without_the_model(self):
        out = claude_code.command({"command_name": "robot-voice:speak",
                                   "command_args": "mode prose", "session_id": "s4"})
        self.assertEqual(out["decision"], "block")
        self.assertIn("mode     prose", out["reason"])
        self.assertEqual(engine.load_config()["mode"], "prose")

    def test_loose_phrasing_goes_to_the_model(self):
        self.assertIsNone(claude_code.command(
            {"command_name": "speak", "command_args": "talk a bit slower please"}))

    def test_other_commands_are_ignored(self):
        self.assertIsNone(claude_code.command({"command_name": "speakeasy",
                                               "command_args": "status"}))

    def test_known_word_that_is_not_a_command_goes_to_the_model(self):
        for args in ("mode loud", "repeat that but slower"):
            self.assertIsNone(claude_code.command({"command_name": "speak",
                                                   "command_args": args}), args)

    def test_key_is_never_taken_through_the_prompt(self):
        out = claude_code.command({"command_name": "speak", "command_args": "key"})
        self.assertIn("in a terminal", out["reason"])

    def test_hook_script_end_to_end(self):
        payload = json.dumps({"session_id": "s5", "last_assistant_message": "Done. Tests pass."})
        res = subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "claude.py"), "stop"],
                             input=payload, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(spoken(), [["say", "Done."]])

    def test_hook_script_never_fails_on_garbage(self):
        res = subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "claude.py"), "stop"],
                             input="not json", capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


class Hermes(Base):
    def test_local_turn_is_spoken_in_the_background(self):
        hermes.on_turn(assistant_response="Deployed. Anything else?",
                       session_id="h1", platform="cli")
        self.assertEqual(wait_for_speech(1), [["say", "Deployed. Anything else?"]])

    def test_gateway_turn_stays_silent(self):
        hermes.on_turn(assistant_response="Hi from Telegram.", session_id="h2",
                       platform="telegram")
        time.sleep(0.5)
        self.assertEqual(spoken(), [])

    def test_command_returns_text_directly(self):
        self.assertIn("backend  say", hermes.on_command(""))
        self.assertIn("mode must be one of", hermes.on_command("mode loud"))

    def test_command_refuses_to_take_a_key(self):
        self.assertIn("GEMINI_API_KEY", hermes.on_command("key abc123"))

    def test_repeat_uses_the_session_that_spoke_last(self):
        hermes.on_turn(assistant_response="First. Then more.", session_id="h3",
                       platform="tui")
        wait_for_speech(1)
        self.assertEqual(hermes.on_command("repeat show all"), "First. Then more.")


class Repeat(Base):
    def test_numbered_history(self):
        for text in ("One.", "Two.", "Three."):
            engine.handle_reply(text, "r1")
        self.assertEqual(ctl.run(["repeat", "show", "2"], session="r1"), "Two.")
        self.assertIn("3. One.", ctl.run(["repeat", "list"], session="r1"))

    def test_sessions_do_not_share_history(self):
        engine.handle_reply("Mine.", "r2")
        engine.handle_reply("Theirs.", "r3")
        self.assertEqual(ctl.run(["repeat", "show"], session="r2"), "Mine.")


class Status(Base):
    def test_missing_key_is_called_out(self):
        engine.save_config(dict(engine.DEFAULTS))
        out = ctl.run(["status"])
        if "keychain" not in out:  # this machine may have a real key stored
            self.assertIn("key      MISSING", out)

    def test_plugin_option_wins(self):
        engine.save_config(dict(engine.DEFAULTS))
        os.environ["CLAUDE_PLUGIN_OPTION_GEMINI_API_KEY"] = "test-key"
        try:
            self.assertIn("key      Claude Code plugin config", ctl.run(["status"]))
        finally:
            del os.environ["CLAUDE_PLUGIN_OPTION_GEMINI_API_KEY"]


if __name__ == "__main__":
    unittest.main()
