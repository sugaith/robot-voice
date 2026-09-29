"""Hermes Agent adapter: a post_llm_call hook and native /robot:<command>s.

Hermes runs both inside its own process, so neither may wait on audio. Every
reply is spoken by a detached child running Hermes' own interpreter; the
command returns its text at once and Hermes shows it without a model turn.
"""
import logging
import os

from . import ctl, engine

logger = logging.getLogger(__name__)

PREFIX = "/robot:"
DESCRIPTIONS = {
    "use": "Robot voice: switch engine or voice",
    "voice": "Robot voice: show or set the voice",
    "all": "Robot voice: say the last reply again, all of it",
    "tldr": "Robot voice: a short summary of the last reply (2-3 sentences)",
    "brief": "Robot voice: the last reply's first sentence again",
    "vol": "Robot voice: how loud, 0 to 10 (5 is normal)",
    "help": "Robot voice: the commands",
}
ARGS_HINTS = {"use": "<engine> [voice] | <voice>", "voice": "[name]", "vol": "[0-10]"}

# Hermes has no skill index for plugins, so the agent learns about its voice here.
PROMPT = (
    "Your replies are spoken out loud by the robot-voice plugin (it detects "
    "Portuguese or English per reply). When the user asks to change the voice, "
    "engine, language or how much is spoken, or to hear something again, run "
    "`%s --session %s <command>` and report its output. Changes apply to this "
    "session; put `agent` or `global` right after the command to widen them. Commands: use <engine> [voice] "
    "(gemini, sano, kokoro, say), voice [name], voices, on, off, mode "
    "brief|prose|smart, vol 0-10 (5 normal), lang auto|pt|en, random on|off, repeat [all|smart|slow|<n>], "
    "status; `help all` lists everything. Female Portuguese voice: kokoro pf_dora "
    "or say Luciana. Never ask for an API key in chat."
)


def on_turn(assistant_response="", session_id="", platform="", **_):
    """post_llm_call: once per successful turn, after the tool loop."""
    if not isinstance(assistant_response, str) or not assistant_response.strip():
        return
    if platform not in engine.load_config().get("hermes_platforms", ()):
        return
    try:
        engine.spawn({"op": "reply", "text": assistant_response,
                      "session": "hermes:%s" % (session_id or "default")})
    except Exception as e:  # a broken speaker must never break a turn
        logger.debug("robot-voice: could not start speech: %s", e)
        engine.log("hermes hook: %s" % e)


def command(name):
    """The handler for /robot:<name>."""
    def handler(raw_args=""):
        try:
            # A Hermes command gets only its arguments: act on the Hermes
            # session that spoke last.
            return ctl.shortcut(name, raw_args, PREFIX,
                                session=engine.session_id(agent="hermes"))
        except (ctl.CtlError, ValueError):
            # A Hermes command can only return text, not hand words to the agent.
            return ("Not a command as typed. Ask in the chat instead, e.g. "
                    "\"use a female Portuguese voice\": the agent knows robot-voice. "
                    "%shelp lists the commands." % PREFIX)
    return handler


def prompt_section(info=None):
    sid = (info or {}).get("session_id") or "default"
    return PROMPT % (os.path.join(engine.ROOT, "bin", "robot-voice"), "hermes:" + sid)


def register(ctx):
    ctx.register_hook("post_llm_call", on_turn)
    for name, desc in DESCRIPTIONS.items():
        ctx.register_command(PREFIX.lstrip("/") + name, handler=command(name),
                             description=desc, args_hint=ARGS_HINTS.get(name, ""))
    ctx.register_system_prompt_section("robot-voice", prompt_section, max_chars=1100)
