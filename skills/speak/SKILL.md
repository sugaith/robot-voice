---
name: speak
description: "Speak Claude's replies out loud (TTS), and replay them. Use when the user wants the voice on/off, quieter/shorter/longer, a different voice or engine, or something said again. Sub-commands: status, on, off, stop, mode prose|brief|smart, use gemini|say|kokoro, voice, voices, model, style, lang, test, reset, repeat, repeat all, repeat brief|prose|smart, repeat slow, repeat <n>, repeat list, repeat show, say <words>."
allowed-tools: Bash(robot-voice:*)
---

# Speak

The robot-voice plugin speaks each finished reply out loud. This skill is its
control surface.

Exact sub-commands (`/speak off`, `/speak repeat 2`) never reach you: a hook
runs them directly. You only see this skill when the user phrased it loosely,
or when you decide on your own that a request is about the voice. Map it to a
command and run:

```
robot-voice <sub-command>
```

Report its output verbatim. `robot-voice help` lists everything,
`robot-voice repeat help` the replay commands.

## Mapping what the user says

| User says | Command |
|---|---|
| "speak", "voice on", "talk to me" | `on` |
| "quiet", "stop talking", "voice off" | `off` |
| "shut up" (mid-playback) | `stop` |
| "read the whole thing" | `mode prose` |
| "just the gist", "one line" | `mode brief` |
| "summarize it properly" | `mode smart` |
| "switch to X", "use X", "change the engine" | `use gemini`, `use say` or `use kokoro` |
| "use a local/offline voice" | `use kokoro` |
| "no API calls", "use the mac voice" | `use say` |
| "which one is it using?" | `status` |
| "different voice" | `voices`, then `voice <name>` |
| "speak Portuguese" | `lang pt` |
| "sound calmer/excited/etc" | `style Say it <adjective>:` |
| "test it" | `test` |
| "repeat", "say that again", "I missed that" | `repeat` |
| "read the whole thing again", "all of it" | `repeat all` |
| "slower", "I couldn't follow" | `repeat slow` |
| "summarize what you said" | `repeat smart` |
| "what did you say before that" | `repeat 2` (or `3`, ...) |
| "what have you been saying" | `repeat list` |
| "don't say it, just show me" | `repeat show` |
| "say <something>" | `say <something>` |

## Never handle the API key

If the user wants to set or change the Gemini key, do not ask them to paste it
into the chat. Point them to `/plugin` (robot-voice, configure), or to running
`robot-voice key` in their own terminal, which stores it in the macOS keychain.

## Modes

- **prose**: full reply, code blocks / tables / file paths stripped, capped ~600 chars
- **brief**: first sentence plus any closing question, capped ~220 chars (default)
- **smart**: a cheap Gemini call rewrites the reply into one spoken sentence

## Engines

- **gemini** (default): best voices, steerable via `style`, ~0.2 cents per reply, needs a key
- **say**: macOS built-in, free, offline, automatic fallback if the others fail
- **kokoro**: local open model; needs `pip install kokoro soundfile` and `brew install espeak-ng`

If the user asks which to pick: gemini sounds best and costs fractions of a
cent per reply; say is free but robotic; kokoro is free and offline but its
Portuguese voices are weak.

`status` shows where the key came from, or MISSING when replies are falling
back to say, plus the most recent problem from the log.
