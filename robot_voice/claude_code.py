"""Claude Code adapter: two hooks, wired up in hooks/hooks.json.

stop     -- Stop hook. Claude Code hands over the finished reply as
            `last_assistant_message`, so there is no transcript to parse and
            no race with the writer.
command  -- UserPromptExpansion hook on /speak. A valid command runs right
            here and its output replaces the model turn: no tokens, no
            interpretation. Anything else ("talk slower please", "mode loud")
            expands into the skill as usual and the model maps it.

Both always exit 0: a broken speaker must never break a turn.
"""
import json
import shlex
import sys

from . import ctl, engine

SKILL_NAMES = ("speak", "robot-voice:speak")


def stop(payload):
    if payload.get("stop_hook_active"):
        return
    engine.handle_reply(payload.get("last_assistant_message") or "",
                        payload.get("session_id"))


def command(payload):
    """JSON to print, or None to let the command expand normally."""
    if payload.get("command_name") not in SKILL_NAMES:
        return None
    try:
        argv = shlex.split(payload.get("command_args") or "")
    except ValueError:
        return None  # unbalanced quotes: let the model make sense of it
    if not ctl.understands(argv):
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
