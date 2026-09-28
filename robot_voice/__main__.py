"""`robot-voice` on the command line: python3 -m robot_voice <command>."""
import getpass
import json
import sys

from . import ctl, engine, keys


def set_key(argv):
    if argv and argv[0] in ("--clear", "clear", "rm"):
        return "removed from keychain" if keys.keychain_delete() else "no key in the keychain"
    if not sys.stdin.isatty():
        raise ctl.CtlError("`key` needs a terminal to ask for the key")
    key = getpass.getpass("Gemini API key (from aistudio.google.com/apikey): ").strip()
    if not key:
        raise ctl.CtlError("no key entered; nothing changed")
    keys.keychain_set(key)
    _, source = keys.find(engine.load_config())
    note = "" if source == "keychain" else " (note: %s takes precedence)" % source
    return "saved to the macOS keychain" + note


def _options(argv):
    """Leading flags for agents that call the CLI: --detach (speak in the
    background), --session ID (replay the caller's own session), and
    --shortcut NAME --prefix P (run the agent's /<P><NAME> slash command)."""
    opts = {"detach": False, "session": None, "shortcut": None, "prefix": "robot-voice "}
    while argv[:1] and argv[0].startswith("--"):
        flag = argv[0][2:]
        if flag == "detach":
            opts["detach"], argv = True, argv[1:]
        elif flag in ("session", "shortcut", "prefix") and len(argv) > 1:
            opts[flag], argv = argv[1], argv[2:]
        else:
            break
    return opts, argv


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_job"]:
        engine.run_job(json.load(sys.stdin))
        return 0
    opts, argv = _options(argv)
    try:
        if opts["shortcut"] in ctl.SHORTCUTS:
            out = ctl.shortcut(opts["shortcut"], " ".join(argv), opts["prefix"],
                               detach=opts["detach"], session=opts["session"])
        elif argv[:1] == ["key"]:
            out = set_key(argv[1:])
        else:
            out = ctl.run(argv, detach=opts["detach"], session=opts["session"])
    except (ctl.CtlError, RuntimeError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
