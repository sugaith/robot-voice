---
name: robot
description: "Robot voice: speaks Claude's replies out loud (TTS) in English and Portuguese, and replays them. Use when the user wants the voice on/off, shorter/longer, a different voice, engine or language, a random voice, or something said again. Sub-commands: status, on, off, stop, mode prose|brief|smart, use gemini|sano|kokoro|say, lang auto|pt|en, voice, voice <name>, voices, random on|off, model, style, test, reset, repeat, repeat all|brief|prose|smart|slow|<n>|list|show, say <words>."
allowed-tools: Bash(robot-voice:*)
---

# Robot voice

The robot-voice plugin speaks each finished reply out loud. This skill is its
control surface.

Exact sub-commands (`/robot off`, `/robot repeat 2`) never reach you: a hook
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
| "switch to X", "use X", "change the engine" | `use gemini`, `use sano`, `use kokoro` or `use say` |
| "fast local voice" | `use sano` |
| "best local voice", "offline but nicer" | `use kokoro` |
| "no API calls", "use the mac voice" | `use say` |
| "which one is it using?", "what's the voice now?" | `voice` |
| "different voice" | `voices`, then `voice <name>` |
| "surprise me", "a different voice each time" | `random on` |
| "always speak Portuguese" / "English" | `lang pt` / `lang en` |
| "detect the language" | `lang auto` |
| "sound calmer/excited/etc" (Gemini) | `style Say it <adjective>:` |
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
into the chat. Point them to `/plugin configure robot-voice@robot-voice`, or to
running `robot-voice key` in their own terminal, which stores it in the macOS
keychain.

## Engines

Tried in order; `status` shows the chain. macOS `say` is always the last resort.

- **gemini**: best voices, steerable via `style`, ~0.2 cents per reply, needs a key
- **sano**: tiny local model, answers in ~0.4 s, English and Portuguese
- **kokoro**: nicer local model, ~5 s per reply, English and Portuguese
- **say**: macOS built-in, free, robotic, always available

Each engine keeps one voice per language. With `lang auto` (the default), each
reply is detected as Portuguese or English and gets that language's voice.

## Modes

- **prose**: full reply, code blocks / tables / file paths stripped, capped ~600 chars
- **brief**: first sentence plus any closing question, capped ~220 chars (default)
- **smart**: a cheap Gemini call rewrites the reply into one spoken sentence

`status` ends with what actually spoke last, and what failed before it.
