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
    """Leading --detach / --session ID, for agents that call the CLI: speak in
    the background, and replay the caller's own session."""
    detach, session = False, None
    while argv[:1] and argv[0].startswith("--"):
        if argv[0] == "--detach":
            detach, argv = True, argv[1:]
        elif argv[0] == "--session" and len(argv) > 1:
            session, argv = argv[1], argv[2:]
        else:
            break
    return detach, session, argv


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_job"]:
        engine.run_job(json.load(sys.stdin))
        return 0
    detach, session, argv = _options(argv)
    try:
        if argv[:1] == ["key"]:
            out = set_key(argv[1:])
        else:
            out = ctl.run(argv, detach=detach, session=session)
    except (ctl.CtlError, RuntimeError, ValueError) as e:
        print(e, file=sys.stderr)
        return 1
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
