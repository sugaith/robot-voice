"""Hermes Agent adapter: a post_llm_call hook and a native /robot command.

Hermes runs both inside its own process, so neither may wait on audio. Every
reply is spoken by a detached child running Hermes' own interpreter; the
command returns its text at once and Hermes shows it without a model turn.
"""
import logging
import shlex

from . import ctl, engine

logger = logging.getLogger(__name__)

DESCRIPTION = "Robot voice: speaks replies out loud -- /robot help"
ARGS_HINT = "[status|on|off|mode|use|lang|voice|random|repeat|say|help]"


def on_turn(assistant_response="", session_id="", platform="", **_):
    """post_llm_call: once per successful turn, after the tool loop."""
    if not isinstance(assistant_response, str) or not assistant_response.strip():
        return
    if platform not in engine.load_config().get("hermes_platforms", ()):
        return
    try:
        engine.spawn({"op": "reply", "text": assistant_response,
                      "session": "hermes-%s" % (session_id or "default")})
    except Exception as e:  # a broken speaker must never break a turn
        logger.debug("robot-voice: could not start speech: %s", e)
        engine.log("hermes hook: %s" % e)


def on_command(raw_args=""):
    try:
        argv = shlex.split(raw_args or "")
    except ValueError as e:
        return str(e)
    if argv[:1] == ["key"]:
        return ("Set GEMINI_API_KEY in ~/.hermes/.env (or the plugin's settings in "
                "Hermes Desktop), or run robot-voice key in a terminal.")
    try:
        return ctl.run(argv, detach=True)
    except ctl.CtlError as e:
        return str(e)


def register(ctx):
    ctx.register_hook("post_llm_call", on_turn)
    ctx.register_command("robot", handler=on_command, description=DESCRIPTION,
                         args_hint=ARGS_HINT)
