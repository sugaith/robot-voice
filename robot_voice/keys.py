"""Where the Gemini API key comes from.

First hit wins:
  1. CLAUDE_PLUGIN_OPTION_GEMINI_API_KEY -- Claude Code's plugin config, which
     asks for the key when the plugin is enabled and keeps it in the keychain
  2. GEMINI_API_KEY, then GOOGLE_API_KEY -- the environment, which is also
     where Hermes loads its .env secrets; the Gemini API takes either name
  3. the macOS keychain, written by `robot-voice key`
  4. `gemini_api_key` in config.json
"""
import os
import shutil
import subprocess
import sys

KEYCHAIN_SERVICE = "robot-voice"
KEYCHAIN_ACCOUNT = "gemini"
PLUGIN_OPTION_ENV = "CLAUDE_PLUGIN_OPTION_GEMINI_API_KEY"


def _has_keychain():
    return sys.platform == "darwin" and shutil.which("security") is not None


def keychain_get():
    if not _has_keychain():
        return None
    try:
        res = subprocess.run(
            ["security", "find-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT, "-w"],
            capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def keychain_set(key):
    """Store the key without it ever appearing in a process's argv.

    `security add-generic-password -w <key>` would show up in `ps`, so the
    command goes through `security -i`, which reads it from stdin.
    """
    if not _has_keychain():
        raise RuntimeError("no macOS keychain here -- set GEMINI_API_KEY instead")
    if '"' in key or "\n" in key:
        raise ValueError("that doesn't look like an API key")
    cmd = ('add-generic-password -U -s %s -a %s -w "%s"\n'
           % (KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, key))
    res = subprocess.run(["security", "-i"], input=cmd, capture_output=True,
                         text=True, timeout=10)
    if res.returncode != 0 or "error" in (res.stderr + res.stdout).lower():
        raise RuntimeError("keychain refused the key: "
                           + (res.stderr or res.stdout).strip())


def keychain_delete():
    if not _has_keychain():
        return False
    res = subprocess.run(
        ["security", "delete-generic-password",
         "-s", KEYCHAIN_SERVICE, "-a", KEYCHAIN_ACCOUNT],
        capture_output=True, text=True, timeout=5)
    return res.returncode == 0


def _sources(cfg):
    yield "Claude Code plugin config", lambda: os.environ.get(PLUGIN_OPTION_ENV)
    yield "GEMINI_API_KEY", lambda: os.environ.get("GEMINI_API_KEY")
    yield "GOOGLE_API_KEY", lambda: os.environ.get("GOOGLE_API_KEY")
    yield "keychain", keychain_get
    yield "config.json", lambda: cfg.get("gemini_api_key")


def find(cfg):
    """(key, where_it_came_from), or (None, None)."""
    for name, read in _sources(cfg):
        value = (read() or "").strip()
        if value:
            return value, name
    return None, None


def gemini_key(cfg):
    key, _ = find(cfg)
    if not key:
        raise RuntimeError("no Gemini API key -- run `robot-voice key`, or set GEMINI_API_KEY")
    return key
