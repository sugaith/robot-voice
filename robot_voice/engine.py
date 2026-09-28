"""Shaping replies for the ear, and speaking them.

Backends: gemini (Gemini API), say (macOS built-in), kokoro (local model).
Config and runtime state live in $ROBOT_VOICE_HOME (default ~/.robot-voice),
shared by every agent the adapters wire up, so they all speak with one voice.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import wave

from . import keys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME_DIR = os.environ.get("ROBOT_VOICE_HOME") or os.path.expanduser("~/.robot-voice")
CONFIG_PATH = os.path.join(HOME_DIR, "config.json")
LOG_PATH = os.path.join(HOME_DIR, "robot-voice.log")
PID_PATH = os.path.join(HOME_DIR, ".playing.pid")
OUT_WAV = os.path.join(HOME_DIR, ".out.wav")
OUT_KEY_PATH = os.path.join(HOME_DIR, ".out.key")
SESSIONS_DIR = os.path.join(HOME_DIR, "sessions")
LAST_SESSION_PATH = os.path.join(HOME_DIR, ".last-session")
# Where this project lived when it only spoke for Claude Code.
LEGACY_CONFIG = os.path.expanduser("~/.claude-speak/config.json")

STATE_TTL_DAYS = 30
HISTORY_LEN = 10
LOG_MAX_BYTES = 256 * 1024

DEFAULTS = {
    "enabled": True,
    "mode": "brief",            # prose | brief | smart | off
    "backend": "gemini",        # gemini | say | kokoro
    "gemini_model": "gemini-2.5-flash-preview-tts",
    "gemini_voice": "Kore",
    "summarizer_model": "gemini-2.5-flash-lite",
    "say_voice": "Samantha",
    "kokoro_voice": "af_heart",
    "kokoro_lang": "a",
    "max_chars_prose": 600,
    "max_chars_brief": 220,
    "style": "",               # e.g. "Say it calm and low-key: " (gemini only)
    # Hermes surfaces that run on this machine. A Telegram turn handled by a
    # gateway on this host should not come out of its speakers.
    "hermes_platforms": ["cli", "tui"],
}


def load_config():
    cfg = dict(DEFAULTS)
    path = CONFIG_PATH
    if not os.path.exists(path) and os.path.exists(LEGACY_CONFIG):
        path = LEGACY_CONFIG  # keep a claude-speak user's voice until they change it
    try:
        with open(path) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(HOME_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def log(message):
    """Append to robot-voice.log. Speech runs where nobody sees stderr, so a
    silent fallback to `say` would otherwise go unnoticed for weeks."""
    try:
        os.makedirs(HOME_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
            os.replace(LOG_PATH, LOG_PATH + ".1")
        with open(LOG_PATH, "a") as f:
            f.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except OSError:
        pass


def last_log_line(max_age_hours=24):
    try:
        if time.time() - os.path.getmtime(LOG_PATH) > max_age_hours * 3600:
            return None
        with open(LOG_PATH) as f:
            lines = f.read().strip().splitlines()
        return lines[-1] if lines else None
    except OSError:
        return None


# ---------------------------------------------------------------- session state

def session_id(explicit=None):
    """Per-session key, so concurrent sessions never replay each other.

    Hooks pass the id explicitly. Commands fall back to Claude Code's env var,
    then to whichever session spoke most recently -- Hermes hands a slash
    command nothing but its arguments.
    """
    if explicit:
        return explicit
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return os.environ["CLAUDE_CODE_SESSION_ID"]
    try:
        with open(LAST_SESSION_PATH) as f:
            return f.read().strip() or "default"
    except OSError:
        return "default"


def _safe(sid):
    return re.sub(r"[^\w.-]", "_", sid)


def _state_path(sid):
    return os.path.join(SESSIONS_DIR, _safe(sid) + ".json")


def load_state(sid=None):
    try:
        with open(_state_path(session_id(sid))) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(sid=None, **fields):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    sid = session_id(sid)
    state = load_state(sid)
    state.update(fields)
    with open(_state_path(sid), "w") as f:
        json.dump(state, f)
    _prune_states()


def _prune_states():
    cutoff = time.time() - STATE_TTL_DAYS * 86400
    try:
        for name in os.listdir(SESSIONS_DIR):
            path = os.path.join(SESSIONS_DIR, name)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
    except OSError:
        pass


def remember_reply(sid, raw):
    """Add a reply to this session's history. False if it is the one already
    on top -- Claude Code fires Stop again on /clear, resume and compact."""
    state = load_state(sid)
    history = state.get("history", [])
    if history and history[0] == raw:
        return False
    save_state(sid, history=[raw] + history[: HISTORY_LEN - 1], spoken="")
    try:
        with open(LAST_SESSION_PATH, "w") as f:
            f.write(sid)
    except OSError:
        pass
    return True


def history(sid=None):
    """This session's replies, newest first."""
    return load_state(sid).get("history", [])


def last_spoken(sid=None):
    return load_state(sid).get("spoken", "")


# ---------------------------------------------------------------- text cleanup

FENCE_RE = re.compile(r"```.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`([^`]*)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
HEADING_RE = re.compile(r"^#{1,6}\s*")
BULLET_RE = re.compile(r"^\s*[-*+]\s+|^\s*\d+[.)]\s+")
EMPHASIS_RE = re.compile(r"\*\*([^*]+)\*\*|\*([^*]+)\*|__([^_]+)__")
# Paths, but not slash-commands: /speak survives, /Users/me/x.py does not.
PATHY_RE = re.compile(
    r"(?<!\w)[\w.-]+(?:/[\w.-]+)*"
    r"\.(?:py|ts|tsx|js|jsx|json|md|sh|go|rs|java|yml|yaml)\b"
    r"|(?<!\w)(?:~|\.{1,2})/[\w.~/-]+"
    r"|(?<!\w)/[\w.~-]*[/.][\w.~/-]*")
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF←-⇿☀-➿⬀-⯿️]")
URL_RE = re.compile(r"https?://\S+")


def clean(text):
    """Strip everything that sounds terrible when read aloud."""
    text = FENCE_RE.sub(" ", text)
    text = URL_RE.sub(" link ", text)
    text = LINK_RE.sub(r"\1", text)
    text = INLINE_CODE_RE.sub(r"\1", text)
    text = EMPHASIS_RE.sub(lambda m: next(g for g in m.groups() if g), text)

    lines = []
    for line in text.splitlines():
        if TABLE_ROW_RE.match(line):
            continue
        if set(line.strip()) <= {"-", "|", ":", " "} and line.strip():
            continue
        line = HEADING_RE.sub("", line)
        line = BULLET_RE.sub("", line)
        lines.append(line)
    text = "\n".join(lines)

    text = PATHY_RE.sub(" ", text)
    text = EMOJI_RE.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,;:!?])", r"\1", text)  # "fixed it in ." once a path is gone
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def to_brief(text, cap):
    """First sentence, plus a trailing question if the reply ends with one."""
    parts = [p.strip() for p in SENT_SPLIT_RE.split(text) if p.strip()]
    if not parts:
        return ""
    out = [parts[0]]
    if len(parts) > 1 and parts[-1].endswith("?"):
        out.append(parts[-1])
    return truncate(" ".join(out), cap)


def truncate(text, cap):
    if len(text) <= cap:
        return text
    cut = text[:cap]
    dot = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    return cut[: dot + 1] if dot > cap * 0.5 else cut.rstrip() + "."


def _gemini_url(model, cfg):
    return ("https://generativelanguage.googleapis.com/v1beta/models/"
            "%s:generateContent?key=%s" % (model, keys.gemini_key(cfg)))


def to_smart(text, cfg):
    """One spoken line via a cheap Gemini call. Falls back to brief on failure."""
    prompt = (
        "Rewrite this assistant reply as ONE short spoken sentence (max 20 words) "
        "a developer would want to hear out loud. State the outcome and any question "
        "asked. No markdown, no code, no file paths. Reply with the sentence only.\n\n"
        + text[:4000]
    )
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200,
                                 "thinkingConfig": {"thinkingBudget": 0}}}
    try:
        req = urllib.request.Request(_gemini_url(cfg["summarizer_model"], cfg),
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        res = json.load(urllib.request.urlopen(req, timeout=25))
        parts = res["candidates"][0]["content"]["parts"]
        line = "".join(p.get("text", "") for p in parts).strip()
        return line or to_brief(text, cfg["max_chars_brief"])
    except Exception as e:
        log("smart summary failed (%s); spoke the brief line instead" % _redact(e))
        return to_brief(text, cfg["max_chars_brief"])


def shape(text, cfg, mode=None):
    mode = mode or cfg["mode"]
    body = clean(text)
    if not body:
        return ""
    if mode == "prose":
        return truncate(body, cfg["max_chars_prose"])
    if mode == "smart":
        return to_smart(body, cfg)
    return to_brief(body, cfg["max_chars_brief"])


def _redact(err):
    """Error text without the API key, which rides in the request URL."""
    return re.sub(r"key=[\w-]+", "key=***", str(err))


# ------------------------------------------------------------------- playback

def stop_playing():
    try:
        with open(PID_PATH) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass


def _run_player(argv):
    stop_playing()
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        with open(PID_PATH, "w") as f:
            f.write(str(proc.pid))
    except OSError:
        pass
    proc.wait()


def play(path):
    if not shutil.which("afplay"):
        raise RuntimeError("no audio player (afplay) found")
    _run_player(["afplay", path])


WAV_BACKENDS = ("gemini", "kokoro")


def audio_key(text, cfg, backend=None):
    """Identifies the audio .out.wav holds: the words *and* their delivery.

    Voice, model and style all change how the same sentence comes out, so any
    of them changing has to miss the cache.
    """
    name = backend or cfg["backend"]
    parts = [name, text]
    if name == "gemini":
        parts += [cfg.get("gemini_voice", ""), cfg.get("gemini_model", ""),
                  cfg.get("style") or ""]
    else:
        parts += [cfg.get("kokoro_voice", ""), cfg.get("kokoro_lang", "")]
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()


def remember_audio(text, cfg, backend=None):
    """Tag the wav just written, so an identical line can replay it."""
    try:
        with open(OUT_KEY_PATH, "w") as f:
            f.write(audio_key(text, cfg, backend))
    except OSError:
        pass


def replay(text, cfg, backend=None):
    """Play the cached wav if it is exactly this audio. True if it played.

    Saying the same line again is otherwise a second round trip to the TTS
    backend for a file already sitting on disk.
    """
    name = backend or cfg["backend"]
    if name not in WAV_BACKENDS or not os.path.exists(OUT_WAV):
        return False
    try:
        with open(OUT_KEY_PATH) as f:
            if f.read().strip() != audio_key(text, cfg, name):
                return False
    except OSError:
        return False
    if os.environ.get("ROBOT_VOICE_DRYRUN"):
        _dry_run("replay", text)
        return True
    play(OUT_WAV)
    return True


def write_wav(pcm, path, rate=24000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


# ------------------------------------------------------------------- backends

def speak_gemini(text, cfg):
    prompt = (cfg.get("style") or "") + text
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": cfg["gemini_voice"]}}},
        },
    }
    req = urllib.request.Request(_gemini_url(cfg["gemini_model"], cfg),
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req, timeout=60))
    inline = res["candidates"][0]["content"]["parts"][0]["inlineData"]
    rate = 24000
    m = re.search(r"rate=(\d+)", inline.get("mimeType", ""))
    if m:
        rate = int(m.group(1))
    os.makedirs(HOME_DIR, exist_ok=True)
    write_wav(base64.b64decode(inline["data"]), OUT_WAV, rate)
    play(OUT_WAV)


def speak_say(text, cfg):
    if not shutil.which("say"):
        raise RuntimeError("macOS `say` not found")
    argv = ["say", "-v", cfg["say_voice"]]
    if cfg.get("say_rate"):
        argv += ["-r", str(cfg["say_rate"])]
    _run_player(argv + [text])


def speak_kokoro(text, cfg):
    try:
        import numpy as np
        from kokoro import KPipeline
    except ImportError:
        raise RuntimeError("kokoro not installed. Run: pip install kokoro soundfile "
                           "&& brew install espeak-ng")
    pipe = KPipeline(lang_code=cfg["kokoro_lang"])
    chunks = [audio for _, _, audio in pipe(text, voice=cfg["kokoro_voice"])]
    if not chunks:
        return
    audio = np.concatenate(chunks)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    os.makedirs(HOME_DIR, exist_ok=True)
    write_wav(pcm, OUT_WAV, 24000)
    play(OUT_WAV)


BACKENDS = {"gemini": speak_gemini, "say": speak_say, "kokoro": speak_kokoro}


def _dry_run(backend, text):
    """ROBOT_VOICE_DRYRUN=<file>: record what would be spoken instead of
    playing it. Lets tests and adapters run end to end in silence."""
    with open(os.environ["ROBOT_VOICE_DRYRUN"], "a") as f:
        f.write("%s\t%s\n" % (backend, text))


def speak(text, cfg, backend=None):
    """Speak text, falling back to macOS `say` if the chosen backend fails."""
    name = backend or cfg["backend"]
    if os.environ.get("ROBOT_VOICE_DRYRUN"):
        _dry_run(name, text)
        return
    try:
        BACKENDS[name](text, cfg)
    except Exception as e:
        if name == "say":
            log("say failed: %s" % e)
            raise
        log("%s failed (%s); fell back to say" % (name, _redact(e)))
        speak_say(text, cfg)
        return
    if name in WAV_BACKENDS:
        remember_audio(text, cfg, name)


def say_again(text, cfg):
    """Speak text, reusing the cached clip when it is exactly this audio."""
    if not replay(text, cfg):
        speak(text, cfg)


# ------------------------------------------------------------------- adapters

def handle_reply(raw, sid=None):
    """What every adapter calls when its agent finishes a reply.

    The reply is remembered even while muted, so `repeat` still works after
    `off`. Returns the line spoken, if any.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    sid = session_id(sid)
    if not remember_reply(sid, raw):
        return None
    cfg = load_config()
    if not cfg.get("enabled") or cfg.get("mode") == "off":
        return None
    line = shape(raw, cfg)
    if not line:
        return None
    save_state(sid, spoken=line)
    speak(line, cfg)
    return line


def spawn(job):
    """Run a job in a detached process and return at once.

    For hosts that must not wait on audio: Hermes runs hooks and slash commands
    inside its own process, and a Claude Code command hook holds the prompt.
    Runs with the host's own interpreter, so Hermes needs no python3 on PATH.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.Popen([sys.executable, "-m", "robot_voice", "_job"],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True,
                            env=env, cwd=ROOT)
    proc.stdin.write(json.dumps(job).encode())
    proc.stdin.close()
    # Reap it when it ends, or a long-lived host collects zombies.
    threading.Thread(target=proc.wait, daemon=True).start()


def run_job(job):
    """The detached half of `spawn`."""
    op = job.get("op")
    if op == "reply":
        handle_reply(job.get("text", ""), job.get("session"))
    elif op == "say":
        cfg = load_config()
        cfg.update(job.get("overrides") or {})
        say_again(job.get("text", ""), cfg)
