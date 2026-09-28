---
name: robot-voice
description: "Your replies are spoken out loud by robot-voice (TTS, English and Portuguese). Use when the user wants the voice on/off, shorter/longer, a different voice, engine or language, a random voice, something said again, or asks whether you can speak."
---

# Robot voice

Every reply you finish is spoken out loud: robot-voice shapes it for the ear
(no code, tables or paths), detects Portuguese or English, and plays it. You
don't need to do anything for that to happen. This skill is how you change
how it sounds, or replay something.

Run the CLI that ships with this skill (the path is relative to this file):

```
../../../bin/robot-voice <command>
```

Report its output verbatim. `help` lists every command, `repeat help` the
replay ones. The user can also type `/robot <command>` themselves: exact
commands run instantly without you, and anything else reaches you here.

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
| "female/male voice" | `voices`, pick one, `voice <name>` |
| "surprise me", "a different voice each time" | `random on` |
| "always speak Portuguese" / "English" | `lang pt` / `lang en` |
| "detect the language" | `lang auto` |
| "sound calmer/excited/etc" (Gemini) | `style Say it <adjective>:` |
| "test it" | `test` |
| "repeat", "say that again", "I missed that" | `repeat` |
| "read the whole thing again", "all of it" | `repeat all` |
| "slower", "I couldn't follow" | `repeat slow` |
| "what did you say before that" | `repeat 2` (or `3`, ...) |
| "what have you been saying" | `repeat list` |
| "say <something>" | `say <something>` |

## Voices worth knowing

- **sano** (fast, ~0.3 s): English `heart` (female), `hfc`, `amy`, `kristin`;
  Portuguese only `pt-cadu` (male).
- **kokoro** (~5 s): Portuguese `pf_dora` (female), `pm_alex`, `pm_santa` (male);
  English `af_heart`, `af_bella` and more.
- **say** (instant, robotic): Portuguese `Luciana`, `Flo (Portuguese (Brazil))`,
  `Eddy (Portuguese (Brazil))`...; English `Samantha` and more.
- **gemini** (best, needs a key): multilingual voices like `Kore`, `Puck`, `Leda`.

Each engine keeps one voice per language: `voice pf_dora` lands in the
Portuguese slot, `voice en af_bella` sets English explicitly.

## Never handle the API key

Don't ask the user to paste a Gemini key into the chat. Tell them to run
`robot-voice key` in their own terminal (it stores it in the macOS keychain),
or to set `GEMINI_API_KEY`.
