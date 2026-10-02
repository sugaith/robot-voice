"""The commands behind robot-voice, in every agent.

`run(argv)` returns the text to show and raises CtlError for bad input, so
each surface decides how to display it: the terminal prints, Claude Code's
command hook shows it in place of a model turn, Hermes returns it from its
slash command.
"""
import copy
import shlex

from . import engine, keys, voices

MODES = ("prose", "brief", "smart", "off")
BACKENDS = engine.ENGINES
BACKEND_CMDS = ("use", "backend", "provider", "engine")
# Bare-name shortcut for engines. `say` is left out: it means "say these words".
BACKEND_NAMES = ("gemini", "sano", "kokoro")
REPLAY_CMDS = ("repeat", "again")
REPLAY_MODES = ("brief", "prose", "smart")
VOLUME_CMDS = ("volume", "vol")
ON = ("on", "yes", "true", "1")
OFF = ("off", "no", "false", "0")

USAGE = """usage: robot-voice <command>

  status                   settings, and what actually spoke last
  on | off                 enable / disable spoken replies
  mode prose|brief|smart   how much gets spoken
  use gemini|sano|kokoro|say
                           switch engine (or just name it: robot-voice sano)
  lang auto|pt|en          auto picks per reply; pt / en pin one language
  voice                    the current voices, and the one heard last
  voice <name>             set a voice (pt or en slot, from the name)
  voice pt|en <name>       set the voice for one language explicitly
  voices                   list the active engine's voices, per language
  random [on|off]          a random voice for every reply
  model <id>               the Gemini TTS model
  style <text>             Gemini delivery style, e.g. "Say it calm:" ("" clears)
  test [text]              speak a sample now
  stop                     stop playback
  reset                    restore defaults
  key                      (terminal only) store a Gemini API key in the keychain

  repeat [command]         say a reply again (alias: again) -- `repeat help`
  say <words>              speak arbitrary words

Engines fall back in order (see status); macOS say is always the last resort."""

REPEAT_USAGE = """usage: robot-voice repeat [command]

  (none)        say the last spoken line again, verbatim
  all           the full last reply, uncapped
  brief         first sentence of the last reply
  prose         the last reply, cleaned and capped
  smart         a short summary of the last reply (3-5 sentences)
  slow          the last spoken line, slower
  <n>           n replies back (1 = last, 2 = the one before, ...)
  back <n>      same as <n>
  list          show the last few replies without speaking
  show [cmd]    print what would be spoken, without speaking it"""

SLOW = {"style": "Say this slowly and clearly, with pauses: ", "say_rate": 145,
        "length_scale": 1.3}

# Every first word `run` understands. Claude Code's command hook answers these
# directly; anything else ("talk slower please") goes to the model instead.
COMMANDS = frozenset(
    ("status", "show", "help", "on", "off", "mode", "voice", "voices", "model",
     "style", "lang", "random", "test", "stop", "reset", "key", "say")
    + VOLUME_CMDS
    + MODES + BACKEND_CMDS + BACKEND_NAMES + REPLAY_CMDS)


# Commands that change a setting, and so take a scope.
SETTINGS = frozenset(("on", "off", "mode", "voice", "lang", "random", "model", "style",
                      "reset") + VOLUME_CMDS + MODES + BACKEND_CMDS + BACKEND_NAMES)


class CtlError(Exception):
    pass


def understands(argv):
    return not argv or argv[0].lower() in COMMANDS


HELP = """robot-voice speaks every reply out loud (pt/en detected per reply).

  {p}use <engine> [voice]   gemini | sano | kokoro | say, e.g. {p}use kokoro pf_dora
  {p}use <voice>            a voice name alone also picks its engine
  {p}use <anything else>    in plain words: "a female Portuguese voice"
  {p}voice [name]           show the current voices, or set one
  {p}all                    say the last reply again, all of it
  {p}tldr                   ...as a short summary: what was done, and the result
  {p}brief                  ...its first sentence, then every question it asks
  {p}vol [0-10]             how loud: 5 is normal, 10 twice as loud, 0 silent
  {p}help                   this

Changes stay in this session. Add `agent` (every session of this agent) or
`global` (every agent) after the command: {p}use global kokoro

Everything else (on/off, mode, lang, random, status...): robot-voice help all"""


def help_text(prefix="/robot-voice:"):
    return HELP.format(p=prefix)


# The slash commands every agent exposes, each as <prefix><name>: Claude Code
# /robot-voice:use, Hermes and pi /robot:use. Each maps onto the CLI's argv.
SHORTCUTS = {
    "use": ["use"],
    "voice": ["voice"],
    "all": ["repeat", "all"],
    "tldr": ["repeat", "smart"],
    "brief": ["repeat", "brief"],
    "vol": ["volume"],
    "help": ["help"],
}


def shortcut(name, args, prefix, detach=True, session=None):
    """Run /<prefix><name> <args>. Raises CtlError when the arguments aren't a
    command as typed -- plain words the agent should take instead."""
    argv = SHORTCUTS[name] + shlex.split(args or "")
    if name == "help":
        return USAGE if argv[1:2] == ["all"] else help_text(prefix)
    if name == "use" and len(argv) == 1:
        return status(engine.config_for(session), session)
    return run(argv, detach=detach, session=session)


def _scope(rest, session):
    """(scope, remaining args). A leading `session`, `agent` or `global` after
    the command picks where a change is saved. Without one, a change made from
    inside a session stays in that session; from a bare terminal it's global."""
    if rest and rest[0].lower() in engine.SCOPES:
        scope, rest = rest[0].lower(), rest[1:]
    else:
        scope = "session" if session else "global"
    if scope in ("session", "agent") and not session:
        raise CtlError("no session here to scope that to -- use `global`")
    if scope == "agent" and not engine.agent_of(session):
        raise CtlError("can't tell which agent this session belongs to")
    return scope, rest


def run(argv, detach=False, session=None):
    """Execute one command. With `detach`, speech plays in the background and
    this returns at once -- for hosts that must not block on audio."""
    session = engine.session_id(session)
    cfg = engine.config_for(session)
    cmd = (argv[0] if argv else "status").lower()
    rest = argv[1:]
    scope = None
    if cmd in SETTINGS:
        scope, rest = _scope(rest, session)
    arg = " ".join(rest).strip()
    before = copy.deepcopy(cfg)

    if cmd in ("status", "show"):
        return status(cfg, session)
    if cmd == "help":
        return USAGE if rest[:1] == ["all"] else help_text("robot-voice ")
    if cmd == "voices":
        return list_voices(cfg)
    if cmd == "voice" and not rest:
        return current_voice(cfg)
    if cmd == "stop":
        engine.stop_playing()
        return "playback stopped"
    if cmd in REPLAY_CMDS:
        return repeat(rest, cfg, detach, session)
    if cmd == "say":
        if not arg:
            raise CtlError("need something to say")
        _speak(arg, cfg, detach, session=session)
        return arg
    if cmd == "test":
        sample = arg or {"pt": "O robô está no ar. É assim que as respostas vão soar.",
                         "en": "Robot voice is live. This is how your replies will sound."
                         }[cfg["lang"] if cfg["lang"] in voices.LANGS else "en"]
        _speak(sample, cfg, detach, session=session)
        return "speaking: " + sample
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
    elif cmd in BACKEND_NAMES:
        cfg["backend"] = cmd
        if rest:
            set_voice(cfg, rest)
    elif cmd in BACKEND_CMDS:
        use(cfg, rest)
    elif cmd == "lang":
        lang = arg.lower() or "auto"
        lang = {"portuguese": "pt", "pt-br": "pt", "english": "en"}.get(lang, lang)
        if lang not in ("auto",) + voices.LANGS:
            raise CtlError("lang must be auto, pt or en")
        cfg["lang"] = lang
    elif cmd == "voice":
        set_voice(cfg, rest)
    elif cmd in VOLUME_CMDS:
        if not arg:
            return "volume   %s/10" % _level(cfg)
        try:
            level = float(arg.replace(",", "."))
        except ValueError:
            raise CtlError("volume is 0 to 10 (5 is normal, 10 twice as loud)")
        if not 0 <= level <= 10:
            raise CtlError("volume is 0 to 10 (5 is normal, 10 twice as loud)")
        cfg["volume"] = int(level) if level == int(level) else level
    elif cmd == "random":
        choice = arg.lower()
        if choice and choice not in ON + OFF:
            raise CtlError("random on|off")
        cfg["random"] = (not cfg.get("random")) if not choice else choice in ON
    elif cmd == "model":
        if not arg:
            raise CtlError("need a model id, e.g. gemini-2.5-flash-preview-tts")
        cfg["gemini_model"] = arg
    elif cmd == "style":
        cfg["style"] = (arg + " ") if arg else ""
    elif cmd == "reset":
        engine.save_layer(scope, session, {}, reset=True)
        return status(engine.config_for(session), session)
    else:
        raise CtlError(USAGE)

    engine.save_layer(scope, session, _changes(before, cfg))
    return status(engine.config_for(session), session)


def _changes(before, after):
    """What a command changed, down to single voice slots, so a session that
    only picked its Portuguese voice still follows every other global voice."""
    changed = {}
    for key in engine.LAYERED:
        if key == "voices":
            slots = {}
            for eng, langs in (after.get("voices") or {}).items():
                for lang, name in langs.items():
                    if (before.get("voices") or {}).get(eng, {}).get(lang) != name:
                        slots.setdefault(eng, {})[lang] = name
            if slots:
                changed["voices"] = slots
        elif before.get(key) != after.get(key):
            changed[key] = after.get(key)
    return changed


def use(cfg, rest):
    """use <engine> [voice] | use <voice>: a known voice name alone switches to
    the engine it belongs to. Anything else is not a command (CtlError), so an
    agent can take it as plain words instead."""
    if not rest:
        raise CtlError("engine must be one of: " + ", ".join(BACKENDS))
    head = rest[0].lower()
    if head in BACKENDS:
        cfg["backend"] = head
        if rest[1:]:
            set_voice(cfg, rest[1:])
        return
    name = " ".join(rest)
    for backend in BACKENDS:
        if voices.lang_of_voice(backend, name) and name in (
                voices.catalog(backend, "en") + voices.catalog(backend, "pt")):
            cfg["backend"] = backend
            set_voice(cfg, rest)
            return
    raise CtlError("not an engine or a voice: %s" % name)


def set_voice(cfg, rest):
    name_args = rest
    lang = None
    if rest and rest[0].lower() in voices.LANGS:
        lang, name_args = rest[0].lower(), rest[1:]
    name = " ".join(name_args).strip()
    if not name:
        raise CtlError("need a voice name -- `voices` lists them")
    if name.lower() == "random":
        cfg["random"] = True
        return
    backend = cfg["backend"]
    slots = cfg.setdefault("voices", {}).setdefault(backend, {})
    cfg["random"] = False
    if lang is None and backend == "gemini":
        slots["en"] = slots["pt"] = name  # Gemini voices speak both languages
        return
    if lang is None:
        lang = voices.lang_of_voice(backend, name)
    if lang is None:
        if cfg["lang"] in voices.LANGS:
            lang = cfg["lang"]
        else:
            raise CtlError("which language is %s for? use `voice pt %s` or `voice en %s`"
                           % (name, name, name))
    slots[lang] = name


def _speak(text, cfg, detach, overrides=None, session=None):
    if detach:
        engine.spawn({"op": "say", "text": text, "overrides": overrides or {},
                      "session": session})
        return
    use = dict(cfg)
    use.update(overrides or {})
    engine.say_again(text, use)


def _voice_line(cfg):
    backend = cfg["backend"]
    if cfg.get("random"):
        return "random"
    return "en %s · pt %s" % (voices.configured(cfg, backend, "en"),
                              voices.configured(cfg, backend, "pt"))


def _last_line():
    last = engine.last_voice()
    if not last:
        return None
    line = "%s %s (%s) at %s" % (last.get("engine"), last.get("voice"),
                                 last.get("lang"), last.get("at"))
    if last.get("failed"):
        line += " -- after " + "; ".join(last["failed"])
    return line


def _where(session):
    """Which settings this session gets from its agent or sets itself."""
    if not session:
        return None
    agent_layer, session_layer = engine.layers(session)

    def names(layer):
        out = []
        for key, value in layer.items():
            if key == "voices":
                out += ["voice %s.%s" % (e, l) for e, ls in value.items() for l in ls]
            elif key in engine.LAYERED:
                out.append(key)
        return ", ".join(out)
    parts = []
    if names(agent_layer):
        parts.append("%s: %s" % (engine.agent_of(session), names(agent_layer)))
    if names(session_layer):
        parts.append("this session: " + names(session_layer))
    return " · ".join(parts) or None


def _level(cfg):
    level = cfg.get("volume", engine.VOLUME_NORMAL)
    return int(level) if float(level) == int(float(level)) else level


def status(cfg, session=None):
    state = "on" if cfg["enabled"] and cfg["mode"] != "off" else "off"
    lines = [
        "speech   " + state,
        "mode     " + cfg["mode"],
        "volume   %s/10" % _level(cfg),
        "engine   " + " → ".join(engine.chain(cfg)),
        "lang     " + cfg.get("lang", "auto"),
        "voice    " + _voice_line(cfg),
    ]
    if cfg["backend"] == "gemini" or cfg["mode"] == "smart":
        lines.append("model    " + cfg["gemini_model"])
        if cfg.get("style"):
            lines.append("style    " + cfg["style"].strip())
        _, source = keys.find(cfg)
        lines.append("key      " + (source or "MISSING -- Gemini will be skipped "
                                     "(run `robot-voice key`)"))
    where = _where(session)
    if where:
        lines.append("set by   " + where)
    last = _last_line()
    if last:
        lines.append("last     " + last)
    return "\n".join(lines)


def current_voice(cfg):
    backend = cfg["backend"]
    lines = ["engine   " + backend]
    for lang in voices.LANGS:
        lines.append("%s       %s" % (lang, voices.configured(cfg, backend, lang)))
    lines.append("random   " + ("on" if cfg.get("random") else "off"))
    last = _last_line()
    if last:
        lines.append("last     " + last)
    return "\n".join(lines)


def list_voices(cfg):
    backend = cfg["backend"]
    out = []
    for lang in voices.LANGS:
        current = voices.configured(cfg, backend, lang)
        names = voices.catalog(backend, lang)
        marked = ["*" + n if n == current else n for n in names]
        out.append("%s: %s" % (lang, " ".join(marked) or "(none installed)"))
    out.append("(* = selected)")
    return "\n".join(out)


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
        _speak(text, cfg, detach, overrides, session=session)
    return text
