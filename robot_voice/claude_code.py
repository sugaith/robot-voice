"""Claude Code adapter: two hooks, wired up in hooks/hooks.json.

stop     -- Stop hook. Claude Code hands over the finished reply as
            `last_assistant_message`, so there is no transcript to parse and
            no race with the writer.
command  -- UserPromptExpansion hook on /robot-voice:robot and its shortcuts
            (/robot-voice:use, :voice, :repeat...). A valid command runs right
            here and its output replaces the model turn: no tokens, no
            interpretation. Anything else ("talk slower please", "mode loud")
            expands into the skill as usual and the model maps it.

Both always exit 0: a broken speaker must never break a turn.
"""
import json
import shlex
import sys

from . import ctl, engine

PLUGIN = "robot-voice"
# /robot-voice:<name> shortcuts, one skill each: /robot-voice:use sano is
# /robot-voice:robot use sano. Keep in step with skills/ and hooks/hooks.json.
SHORTCUTS = ("status", "on", "off", "stop", "use", "voice", "voices", "lang",
             "mode", "random", "repeat", "say", "test")


def to_argv(command_name, command_args):
    """The robot-voice argv a slash command stands for, or None if it isn't ours."""
    name = command_name or ""
    if name.startswith(PLUGIN + ":"):
        name = name[len(PLUGIN) + 1:]
    elif name != "robot":
        return None  # a bare /status or /voice belongs to someone else
    args = shlex.split(command_args or "")
    if name == "robot":
        return args
    if name in SHORTCUTS:
        return [name] + args
    return None


def stop(payload):
    if payload.get("stop_hook_active"):
        return
    engine.handle_reply(payload.get("last_assistant_message") or "",
                        payload.get("session_id"))


def command(payload):
    """JSON to print, or None to let the command expand normally."""
    try:
        argv = to_argv(payload.get("command_name"), payload.get("command_args"))
    except ValueError:
        return None  # unbalanced quotes: let the model make sense of it
    if argv is None or not ctl.understands(argv):
        return None
    try:
        out = ctl.run(argv, detach=True, session=payload.get("session_id"))
    except ctl.CtlError:
        return None  # "repeat that but slower": a known word, not a command
    return {"decision": "block", "reason": out}


def main(argv):
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        payload = {}
    try:
        if argv[:1] == ["stop"]:
            stop(payload)
        elif argv[:1] == ["command"]:
            result = command(payload)
            if result:
                print(json.dumps(result))
    except Exception as e:
        engine.log("claude-code %s hook: %s" % (argv[:1], e))
    return 0
