"""The commands behind /speak, in every agent.

`run(argv)` returns the text to show and raises CtlError for bad input, so
each surface decides how to display it: the terminal prints, Claude Code's
command hook shows it in place of a model turn, Hermes returns it from its
slash command.
"""
import shutil
import subprocess

from . import engine, keys

GEMINI_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi",
    "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]

MODES = ("prose", "brief", "smart", "off")
BACKENDS = ("gemini", "say", "kokoro")
BACKEND_CMDS = ("use", "backend", "provider", "engine")
# Bare-name shortcut for engines. `say` is left out: it means "say these words".
BACKEND_NAMES = ("gemini", "kokoro")
REPLAY_CMDS = ("repeat", "again")
REPLAY_MODES = ("brief", "prose", "smart")

USAGE = """usage: robot-voice <command>

  status                 show current settings
  on | off               enable / disable spoken replies
  mode prose|brief|smart set how much gets spoken
  use gemini|say|kokoro  switch TTS engine (aliases: backend, provider, engine;
                         or just name it: `gemini`, `kokoro`)
  voice <name>           set voice for the active engine
  voices                 list voices for the active engine
  model <id>             set the Gemini TTS model
  style <text>           Gemini delivery style, e.g. "Say it calm:" ("" clears)
  lang pt|en             shortcut: switch voice+lang for Portuguese/English
  test [text]            speak a sample now
  stop                   stop playback
  reset                  restore defaults
  key                    store a Gemini API key in the keychain (terminal only)

  repeat [command]       say a reply again (alias: again) -- `repeat help`
  say <words>            speak arbitrary words"""

REPEAT_USAGE = """usage: robot-voice repeat [command]

  (none)        say the last spoken line again, verbatim
  all           the full last reply, uncapped
  brief         first sentence of the last reply
  prose         the last reply, cleaned and capped
  smart         one-sentence summary of the last reply
  slow          the last spoken line, slower
  <n>           n replies back (1 = last, 2 = the one before, ...)
  back <n>      same as <n>
  list          show the last few replies without speaking
  show [cmd]    print what would be spoken, without speaking it"""

SLOW = {"style": "Say this slowly and clearly, with pauses: ", "say_rate": 145}

# Every first word `run` understands. Claude Code's command hook answers these
# directly; anything else ("talk slower please") goes to the model instead.
COMMANDS = frozenset(
    ("status", "show", "help", "on", "off", "mode", "voice", "voices", "model",
     "style", "lang", "test", "stop", "reset", "key", "say")
    + MODES + BACKEND_CMDS + BACKEND_NAMES + REPLAY_CMDS)


class CtlError(Exception):
    pass


def understands(argv):
    return not argv or argv[0].lower() in COMMANDS


def run(argv, detach=False, session=None):
    """Execute one command. With `detach`, speech plays in the background and
    this returns at once -- for hosts that must not block on audio."""
    cfg = engine.load_config()
    cmd = (argv[0] if argv else "status").lower()
    arg = " ".join(argv[1:]).strip()

    if cmd in ("status", "show"):
        return status(cfg)
    if cmd == "help":
        return USAGE
    if cmd == "voices":
        return list_voices(cfg)
    if cmd == "stop":
        engine.stop_playing()
        return "playback stopped"
    if cmd in REPLAY_CMDS:
        return repeat(argv[1:], cfg, detach, session)
    if cmd == "say":
        if not arg:
            raise CtlError("need something to say")
        _speak(arg, cfg, detach)
        return arg
    if cmd == "test":
        sample = arg or "Robot voice is live. This is how your replies will sound."
        _speak(sample, cfg, detach)
        return "speaking via %s: %s" % (cfg["backend"], sample)
    if cmd == "key":
        return ("Run `robot-voice key` in a terminal. A key typed into the agent's "
                "prompt would end up in its history.")

    if cmd == "on":
        cfg["enabled"] = True
        if cfg["mode"] == "off":
            cfg["mode"] = "brief"
    elif cmd == "off":
        cfg["enabled"] = False
    elif cmd == "mode" or cmd in MODES:
        mode = cmd if cmd in MODES else arg
        if mode not in MODES:
            raise CtlError("mode must be one of: " + ", ".join(MODES))
        cfg["mode"] = mode
        cfg["enabled"] = mode != "off"
    elif cmd in BACKEND_CMDS or cmd in BACKEND_NAMES:
        backend = cmd if cmd in BACKEND_NAMES else arg.lower()
        if backend not in BACKENDS:
            raise CtlError("engine must be one of: " + ", ".join(BACKENDS))
        cfg["backend"] = backend
    elif cmd == "voice":
        if not arg:
            raise CtlError("need a voice name -- `voices` lists them")
        cfg[_voice_key(cfg)] = arg
    elif cmd == "model":
        if not arg:
            raise CtlError("need a model id, e.g. gemini-2.5-flash-preview-tts")
        cfg["gemini_model"] = arg
    elif cmd == "style":
        cfg["style"] = (arg + " ") if arg else ""
    elif cmd == "lang":
        if arg.lower() in ("pt", "pt-br", "portuguese"):
            cfg["say_voice"], cfg["kokoro_voice"], cfg["kokoro_lang"] = \
                "Luciana", "pf_dora", "p"
        else:
            cfg["say_voice"], cfg["kokoro_voice"], cfg["kokoro_lang"] = \
                "Samantha", "af_heart", "a"
    elif cmd == "reset":
        cfg = dict(engine.DEFAULTS)
    else:
        raise CtlError(USAGE)

    engine.save_config(cfg)
    return status(cfg)


def _voice_key(cfg):
    return {"gemini": "gemini_voice", "say": "say_voice",
            "kokoro": "kokoro_voice"}[cfg["backend"]]


def _speak(text, cfg, detach, overrides=None):
    if detach:
        engine.spawn({"op": "say", "text": text, "overrides": overrides or {}})
        return
    use = dict(cfg)
    use.update(overrides or {})
    engine.say_again(text, use)


def status(cfg):
    state = "on" if cfg["enabled"] and cfg["mode"] != "off" else "off"
    lines = [
        "speech   " + state,
        "mode     " + cfg["mode"],
        "backend  " + cfg["backend"],
        "voice    " + cfg[_voice_key(cfg)],
    ]
    if cfg["backend"] == "gemini" or cfg["mode"] == "smart":
        lines.append("model    " + cfg["gemini_model"])
        if cfg.get("style"):
            lines.append("style    " + cfg["style"].strip())
        _, source = keys.find(cfg)
        lines.append("key      " + (source or "MISSING -- replies fall back to say "
                                     "(run `robot-voice key`)"))
    issue = engine.last_log_line()
    if issue:
        lines.append("last     " + issue)
    return "\n".join(lines)


def list_voices(cfg):
    if cfg["backend"] == "gemini":
        return "\n".join(GEMINI_VOICES)
    if cfg["backend"] == "say":
        if not shutil.which("say"):
            return "macOS `say` isn't available here"
        res = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
        return res.stdout.rstrip()
    return ("english: af_heart af_bella am_michael bf_emma bm_george\n"
            "pt-br:   pf_dora pm_alex pm_santa")


# ---------------------------------------------------------------------- repeat

def _nth(n, session):
    replies = engine.history(session)
    if not replies:
        raise CtlError("nothing to repeat yet")
    if n < 1 or n > len(replies):
        raise CtlError("only %d replies remembered in this session" % len(replies))
    return replies[n - 1]


def _resolve(argv, cfg, session):
    """(text_to_speak, config_overrides)."""
    cmd = (argv[0] if argv else "").lower()
    arg = " ".join(argv[1:]).strip()

    if not cmd:
        return engine.last_spoken(session) or engine.shape(_nth(1, session), cfg), {}
    if cmd == "all":
        return engine.clean(_nth(1, session)), {}
    if cmd in REPLAY_MODES:
        return engine.shape(_nth(1, session), cfg, cmd), {}
    if cmd == "slow":
        return engine.last_spoken(session) or engine.shape(_nth(1, session), cfg), SLOW
    if cmd == "back":
        cmd = arg
    if cmd.isdigit():
        return engine.shape(_nth(int(cmd), session), cfg), {}
    raise CtlError(REPEAT_USAGE)


def repeat(argv, cfg, detach=False, session=None):
    head = argv[0].lower() if argv else ""
    if head in ("help", "-h", "--help"):
        return REPEAT_USAGE
    if head == "list":
        replies = engine.history(session)[:5]
        if not replies:
            return "nothing said yet in this session"
        return "\n".join("%d. %s" % (i, engine.truncate(engine.clean(r), 90))
                         for i, r in enumerate(replies, 1))

    show_only = head == "show"
    if show_only:
        argv = argv[1:]
    text, overrides = _resolve(argv, cfg, session)
    if not text.strip():
        raise CtlError("nothing to repeat yet")
    if not show_only:
        _speak(text, cfg, detach, overrides)
    return text
