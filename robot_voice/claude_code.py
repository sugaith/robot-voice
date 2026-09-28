"""Claude Code adapter: two hooks, wired up in hooks/hooks.json.

stop     -- Stop hook. Claude Code hands over the finished reply as
            `last_assistant_message`, so there is no transcript to parse and
            no race with the writer.
command  -- UserPromptExpansion hook on /robot-voice:use, :voice, :all,
            :tldr, :brief and :help. A valid command runs right
            here and its output replaces the model turn: no tokens, no
            interpretation. Anything else ("talk slower please", "mode loud")
            expands into the skill as usual and the model maps it.

Both always exit 0: a broken speaker must never break a turn.
"""
import json
import sys

from . import ctl, engine

PREFIX = "robot-voice:"


def _session(payload):
    sid = payload.get("session_id")
    return "claude:" + sid if sid else None


def stop(payload):
    if payload.get("stop_hook_active"):
        return
    engine.handle_reply(payload.get("last_assistant_message") or "",
                        _session(payload))


def command(payload):
    """JSON to print, or None to let the command expand normally."""
    name = payload.get("command_name") or ""
    if not name.startswith(PREFIX) or name[len(PREFIX):] not in ctl.SHORTCUTS:
        return None
    try:
        out = ctl.shortcut(name[len(PREFIX):], payload.get("command_args"), "/" + PREFIX,
                           session=_session(payload))
    except (ctl.CtlError, ValueError):
        return None  # plain words ("a female Portuguese voice"): the skill takes it
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
