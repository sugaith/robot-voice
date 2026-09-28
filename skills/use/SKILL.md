---
name: use
description: "Robot voice: your replies are spoken out loud (TTS, English and Portuguese). Use to switch engine or voice, or for anything about the voice: on/off, shorter/longer, language, random voice, say something again. /robot-voice:use <engine> [voice] | <voice> | plain words."
argument-hint: "<engine> [voice] | <voice> | plain words"
allowed-tools: Bash(robot-voice:*)
---

# Robot voice

Every reply you finish is spoken out loud by the robot-voice plugin. You don't
need to do anything for that. This skill is how the voice gets changed.

`/robot-voice:use kokoro pf_dora`, `/robot-voice:use sano` or
`/robot-voice:use heart` are answered by a hook before they reach you. You see
this skill when the user phrased it in plain words, or when you decide on your
own that a request is about the voice. Map it to a command and run:

```
robot-voice <command>
```

Report its output verbatim. `robot-voice help all` lists every command.

Changes apply to this session only. When the user wants every Claude session
to change, put `agent` right after the command (`robot-voice use agent
kokoro`); for every agent (Claude, Hermes, pi), put `global`.

## Mapping what the user says

| User says | Command |
|---|---|
| "switch to X", "use X" (an engine) | `use gemini`, `use sano`, `use kokoro` or `use say` |
| "use the voice X" | `use <voice>`, which also picks its engine |
| "fast local voice" | `use sano` |
| "best local voice", "offline but nicer" | `use kokoro` |
| "no API calls", "use the mac voice" | `use say` |
| "female Portuguese voice" | `use kokoro pf_dora`, or `use say Luciana` for instant |
| "which one is it using?", "what's the voice now?" | `voice` |
| "different voice" | `voices`, then `voice <name>` |
| "surprise me", "a different voice each time" | `random on` |
| "speak", "voice on" / "quiet", "voice off" | `on` / `off` |
| "shut up" (mid-playback) | `stop` |
| "read the whole thing" / "just the gist" | `mode prose` / `mode brief` |
| "always speak Portuguese" / "English" / "detect it" | `lang pt` / `lang en` / `lang auto` |
| "sound calmer/excited/etc" (Gemini) | `style Say it <adjective>:` |
| "say that again" / "all of it" / "in short" | `repeat` / `repeat all` / `repeat smart` |
| "louder" / "quieter" / "too loud" | `vol <0-10>` (5 is normal; check `vol` first) |
| "slower" | `repeat slow` |
| "what did you say before that" | `repeat 2` (or `3`, ...) |
| "say <something>" | `say <something>` |
| "is it working?", "status" | `status` |

## Voices worth knowing

- **sano** (fast, ~0.3 s): English `heart` (female), `hfc`, `amy`, `kristin`;
  Portuguese only `pt-cadu` (male).
- **kokoro** (~5 s): Portuguese `pf_dora` (female), `pm_alex`, `pm_santa` (male);
  English `af_heart`, `af_bella` and more.
- **say** (instant, robotic): Portuguese `Luciana`; English `Samantha` and more.
- **gemini** (best, needs a key): multilingual, e.g. `Kore`, `Puck`, `Leda`.

## Never handle the API key

Don't ask the user to paste a Gemini key into the chat. Point them to
`/plugin configure robot-voice@robot-voice`, or to running `robot-voice key` in
their own terminal (it stores it in the macOS keychain).
