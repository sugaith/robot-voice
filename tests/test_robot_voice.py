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
            return [line.rstrip("\n").split("\t", 2) for line in f if line.strip()]
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
        for name in ("config.json", "spoken.log", ".last-session", ".last-voice.json"):
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
        self.assertIn("/robot", engine.clean("Run /robot off to mute."))


class ClaudeCode(Base):
    def test_stop_speaks_last_assistant_message(self):
        claude_code.stop({"session_id": "s1", "last_assistant_message": REPLY})
        self.assertEqual(spoken(), [["say", "Samantha", "I fixed the race in. Want me to open a PR?"]])

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

    def cmd(self, name, args=""):
        return claude_code.command({"command_name": "robot-voice:" + name,
                                    "command_args": args, "session_id": "s4"})

    def test_use_sets_engine_and_voice_without_the_model(self):
        out = self.cmd("use", "kokoro pf_dora")
        self.assertEqual(out["decision"], "block")
        self.assertIn("engine   kokoro", out["reason"])
        self.assertIn("pt pf_dora", out["reason"])

    def test_use_with_a_voice_alone_picks_its_engine(self):
        self.assertIn("engine   sano", self.cmd("use", "heart")["reason"])

    def test_use_in_plain_words_goes_to_the_model(self):
        self.assertIsNone(self.cmd("use", "uma voz feminina em portugues"))

    def test_replays(self):
        engine.handle_reply("First sentence here. Then a lot more text follows. Ok?", "s4")
        open(SPOKEN, "w").close()
        self.assertIn("Then a lot more", self.cmd("all")["reason"])
        self.assertEqual(self.cmd("brief")["reason"], "First sentence here. Ok?")
        self.assertTrue(self.cmd("tldr")["reason"])  # Gemini, or the brief line without a key
        self.assertEqual(len(wait_for_speech(3)), 3)

    def test_voice_and_help(self):
        self.assertIn("en       Samantha", self.cmd("voice")["reason"])
        self.assertIn("/robot-voice:use <engine> [voice]", self.cmd("help")["reason"])

    def test_the_umbrella_and_other_commands_are_gone(self):
        for name in ("robot-voice:robot", "robot", "robot-voice:status", "status"):
            self.assertIsNone(claude_code.command({"command_name": name,
                                                   "command_args": "status"}), name)

    def test_skills_matcher_and_commands_agree(self):
        from robot_voice import ctl as control
        import re
        self.assertEqual(set(os.listdir(os.path.join(ROOT, "skills"))), set(control.SHORTCUTS))
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as f:
            matcher = json.load(f)["hooks"]["UserPromptExpansion"][0]["matcher"]
        for name in control.SHORTCUTS:
            self.assertTrue(re.search(matcher, "robot-voice:" + name), name)
        self.assertFalse(re.search(matcher, "robot-voice:robot"))
        with open(os.path.join(ROOT, "pi", "extension.ts")) as f:
            pi_src = f.read()
        for name in control.SHORTCUTS:
            self.assertIn("\n\t%s: " % name, pi_src, name)

    def test_hook_script_end_to_end(self):
        payload = json.dumps({"session_id": "s5", "last_assistant_message": "Done. Tests pass."})
        res = subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "claude.py"), "stop"],
                             input=payload, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(spoken(), [["say", "Samantha", "Done."]])

    def test_hook_script_never_fails_on_garbage(self):
        res = subprocess.run([sys.executable, os.path.join(ROOT, "hooks", "claude.py"), "stop"],
                             input="not json", capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


class Hermes(Base):
    def test_local_turn_is_spoken_in_the_background(self):
        hermes.on_turn(assistant_response="Deployed. Anything else?",
                       session_id="h1", platform="cli")
        self.assertEqual(wait_for_speech(1), [["say", "Samantha", "Deployed. Anything else?"]])

    def test_gateway_turn_stays_silent(self):
        hermes.on_turn(assistant_response="Hi from Telegram.", session_id="h2",
                       platform="telegram")
        time.sleep(0.5)
        self.assertEqual(spoken(), [])

    def test_commands_return_text_directly(self):
        self.assertIn("engine   say", hermes.command("use")(""))
        self.assertIn("engine   kokoro", hermes.command("use")("kokoro"))
        self.assertIn("/robot:use", hermes.command("help")(""))

    def test_plain_words_point_to_the_chat(self):
        self.assertIn("Ask in the chat", hermes.command("use")("a female voice"))

    def test_registers_every_command_and_a_prompt_section(self):
        registered = {}

        class Ctx:
            def register_hook(self, *a): pass
            def register_command(self, name, handler, description, args_hint):
                registered[name] = handler
            def register_system_prompt_section(self, id, content, max_chars):
                registered["prompt"] = content()

        hermes.register(Ctx())
        self.assertEqual(set(registered) - {"prompt"},
                         {"robot:" + n for n in ctl.SHORTCUTS})
        self.assertIn("bin/robot-voice", registered["prompt"])
        self.assertLessEqual(len(registered["prompt"]), 900)

    def test_repeat_uses_the_session_that_spoke_last(self):
        hermes.on_turn(assistant_response="First. Then more.", session_id="h3",
                       platform="tui")
        wait_for_speech(1)
        self.assertEqual(hermes.command("all")(""), "First. Then more.")


class Cli(Base):
    def test_agent_flags_pick_session_and_detach(self):
        engine.handle_reply("From pi. Anything else?", "pi-7")
        engine.handle_reply("From somewhere else.", "other")
        res = subprocess.run([sys.executable, "-m", "robot_voice", "--detach", "--session",
                              "pi-7", "repeat", "show"], cwd=ROOT, capture_output=True,
                             text=True)
        self.assertEqual(res.stdout.strip(), "From pi. Anything else?", res.stderr)


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


class Routing(Base):
    def test_portuguese_reply_gets_the_portuguese_voice(self):
        engine.handle_reply("Corrigi o bug no hook. Quer que eu abra o PR?", "l1")
        self.assertEqual(spoken()[0][:2], ["say", "Luciana"])

    def test_english_reply_gets_the_english_voice(self):
        engine.handle_reply("Fixed the bug in the hook. Want the PR?", "l2")
        self.assertEqual(spoken()[0][:2], ["say", "Samantha"])

    def test_reply_with_no_signal_keeps_the_previous_language(self):
        engine.handle_reply("Corrigi o bug. Quer o PR?", "l3")
        engine.handle_reply("OK.", "l3")
        self.assertEqual([line[1] for line in spoken()], ["Luciana", "Luciana"])

    def test_pinned_language_wins(self):
        ctl.run(["lang", "pt"])
        engine.handle_reply("Fixed the bug in the hook.", "l4")
        self.assertEqual(spoken()[0][1], "Luciana")

    def test_words_shared_with_english_do_not_count_as_portuguese(self):
        from robot_voice import voices
        self.assertEqual(voices.detect("Fixed both in pi; committed as d57f2bd."), "en")
        self.assertEqual(voices.detect("No, do it as planned."), "en")
        self.assertFalse(voices.PT_WORDS & voices.EN_WORDS)

    def test_code_terms_do_not_tip_portuguese_to_english(self):
        from robot_voice import voices
        self.assertEqual(voices.detect(
            "O hook do Stop agora recebe o last_assistant_message direto."), "pt")


class Engines(Base):
    def test_say_is_always_last(self):
        for backend, fallbacks, expected in (
                ("sano", ["sano", "kokoro"], ["sano", "kokoro", "say"]),
                ("gemini", ["say", "sano"], ["gemini", "sano", "say"]),
                ("say", ["sano"], ["say"]),
                ("kokoro", [], ["kokoro", "say"])):
            cfg = dict(engine.DEFAULTS, backend=backend, fallbacks=fallbacks)
            self.assertEqual(engine.chain(cfg), expected, backend)

    def test_failed_engine_falls_through_and_is_reported(self):
        calls = []

        def broken(text, cfg, voice):
            raise RuntimeError("not installed")

        def ok(text, cfg, voice):
            calls.append(voice)

        saved = dict(engine.BACKENDS)
        dryrun = os.environ.pop("ROBOT_VOICE_DRYRUN")
        engine.BACKENDS.update(sano=broken, kokoro=broken, say=ok)
        try:
            cfg = dict(engine.load_config(), backend="sano")
            self.assertEqual(engine.speak("All done here.", cfg), "say")
        finally:
            engine.BACKENDS.update(saved)
            os.environ["ROBOT_VOICE_DRYRUN"] = dryrun
        self.assertEqual(calls, ["Samantha"])
        status = ctl.run(["status"])
        self.assertIn("last     say Samantha (en)", status)
        self.assertIn("sano: not installed", status)

    def test_engine_names_switch_directly(self):
        self.assertIn("engine   sano → kokoro → say", ctl.run(["sano"]))
        self.assertIn("pt pm_alex", ctl.run(["kokoro", "pm_alex"]))


class Voices(Base):
    def test_voice_name_lands_in_its_language_slot(self):
        ctl.run(["use", "kokoro"])
        ctl.run(["voice", "pm_alex"])
        cfg = engine.load_config()
        self.assertEqual(cfg["voices"]["kokoro"], {"pt": "pm_alex"})
        self.assertIn("pt       pm_alex", ctl.run(["voice"]))
        self.assertIn("en       af_heart", ctl.run(["voice"]))

    def test_explicit_language_for_unknown_names(self):
        with self.assertRaises(ctl.CtlError):
            ctl.run(["voice", "Nobody Here"])
        ctl.run(["voice", "en", "Nobody Here"])
        self.assertEqual(engine.load_config()["voices"]["say"]["en"], "Nobody Here")

    def test_gemini_voice_serves_both_languages(self):
        ctl.run(["use", "gemini"])
        ctl.run(["voice", "Puck"])
        self.assertEqual(engine.load_config()["voices"]["gemini"], {"en": "Puck", "pt": "Puck"})

    def test_random_draws_from_the_catalog(self):
        from robot_voice import voices
        ctl.run(["use", "kokoro"])
        self.assertIn("voice    random", ctl.run(["random", "on"]))
        for i in range(5):
            engine.handle_reply("Reply number %d is here." % i, "v1")
        used = {line[1] for line in spoken()}
        self.assertTrue(used <= set(voices.catalog("kokoro", "en")), used)
        self.assertIn("en       af_heart", ctl.run(["voice"]))  # the slot is untouched
        self.assertIn("random   on", ctl.run(["voice"]))
        ctl.run(["random", "off"])
        self.assertFalse(engine.load_config()["random"])

    def test_voices_marks_the_selected_one(self):
        ctl.run(["use", "sano"])
        out = ctl.run(["voices"])
        self.assertIn("*heart", out)
        self.assertIn("*pt-cadu", out)

    def test_old_single_voice_keys_migrate(self):
        with open(os.path.join(HOME, "config.json"), "w") as f:
            json.dump({"backend": "gemini", "gemini_voice": "Puck", "say_voice": "Alex",
                       "kokoro_voice": "pf_dora", "kokoro_lang": "p"}, f)
        cfg = engine.load_config()
        self.assertEqual(cfg["voices"], {"gemini": {"en": "Puck", "pt": "Puck"},
                                         "say": {"en": "Alex"},
                                         "kokoro": {"pt": "pf_dora"}})
        self.assertNotIn("kokoro_lang", cfg)


if __name__ == "__main__":
    unittest.main()
