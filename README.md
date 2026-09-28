# robot-voice

Your coding agent reads its replies out loud.

When the agent finishes a turn, robot-voice takes the reply, strips everything
that sounds terrible spoken (code blocks, tables, file paths, emoji), shortens
it to what you'd want to hear, and speaks it. `/speak` controls it and replays
anything already said.

| Agent | How it hooks in | `/speak` |
|---|---|---|
| **Claude Code** | plugin: `Stop` hook | answered by a hook, no model turn |
| **Hermes Agent** | plugin: `post_llm_call` hook | native slash command, no model turn |
| anything else | `robot-voice` CLI | `robot-voice <command>` |

One repo is both plugins. Config and voice live once in `~/.robot-voice/`, so
every agent speaks with the same voice.

## Install

### Claude Code

```
/plugin marketplace add sugaith/robot-voice
/plugin install robot-voice@robot-voice
```

Claude Code asks for a Gemini API key when you enable it. The field is masked
and stored in the system keychain, not in `settings.json`. Leave it empty to
use the free macOS voice. Change it later from `/plugin`.

### Hermes Agent

```bash
hermes plugins install sugaith/robot-voice --enable
```

Hermes reads the key from `GEMINI_API_KEY` or `GOOGLE_API_KEY` in
`~/.hermes/.env`. If Hermes already talks to Gemini, you're set. The plugin
declares the key as a `secret` setting, so Hermes Desktop shows a masked field
for it under Capabilities → Plugins.

It speaks turns from the CLI and TUI only. A Telegram message handled by a
gateway on the same machine stays silent. Set `hermes_platforms` in the config
to change that. Don't combine it with Hermes' own `/voice tts`, or every reply
is spoken twice.

### Anything else

```bash
git clone https://github.com/sugaith/robot-voice.git
robot-voice/bin/robot-voice test
```

Any agent with an "on reply finished" hook can pipe the reply in; see
[Adding an agent](#adding-an-agent).

### Coming from claude-speak

robot-voice reads `~/.claude-speak/config.json` until you change a setting, so
your voice carries over. Remove the old wiring or every reply is spoken twice:

- the `Stop` hook pointing at `claude-speak/stop-hook.py` in each `settings.json`
- the `speak` symlink in each config dir's `skills/`

## The Gemini key

Of the engines, only `gemini` needs a key. Without one, speech falls back to
macOS `say`, and `/speak status` tells you so:

```
key      MISSING -- replies fall back to say (run `robot-voice key`)
```

The first source found wins:

1. Claude Code's plugin config (the prompt shown when you enable the plugin)
2. `GEMINI_API_KEY`, then `GOOGLE_API_KEY`, in the environment
3. the macOS keychain: run `robot-voice key` in a terminal to store it there
4. `gemini_api_key` in `~/.robot-voice/config.json`

Never type the key into an agent's prompt. `/speak key` refuses it and points
you here, because the prompt ends up in the agent's history.

Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
Measured on a typical reply (137 chars, ~9s of audio) with
`gemini-2.5-flash-preview-tts`: about $0.0023 per reply. There is a free tier.

## Commands

```
/speak                          # status: what's it set to, and where the key comes from
/speak on | off
/speak mode prose|brief|smart   # how much gets spoken
/speak use gemini|say|kokoro    # engine (or just /speak kokoro)
/speak voice Puck               # voice for the active engine; /speak voices lists them
/speak model <id>               # Gemini TTS model
/speak style Say it calm:       # Gemini delivery direction ("" clears)
/speak lang pt|en
/speak test [text]
/speak stop                     # kill playback
/speak reset

/speak repeat                   # last spoken line again, verbatim
/speak repeat all               # the full last reply, uncapped
/speak repeat brief|prose|smart # re-shape the last reply
/speak repeat slow
/speak repeat 3                 # three replies back
/speak repeat list              # recent replies, without speaking
/speak repeat show [cmd]        # print instead of speaking
/speak say hello there          # arbitrary words
```

In Claude Code, an exact command like `/speak off` never reaches the model: a
`UserPromptExpansion` hook runs it and shows the result in place of a turn,
with no tokens and no interpretation. Anything else, like `/speak talk a bit
slower`, goes to the model, which maps it through the skill. Claude Code labels
the direct answers "blocked by hook". That's the mechanism, not an error.

The same commands work as `robot-voice <command>` in a terminal, plus
`robot-voice key`.

## Modes and engines

| mode | what you hear |
|---|---|
| `brief` | first sentence plus any closing question, ~220 chars (default) |
| `prose` | the whole reply, cleaned, ~600 chars |
| `smart` | a cheap Gemini call rewrites it into one spoken sentence |
| `off` | nothing (replies are still remembered for `repeat`) |

| engine | quality | cost | offline |
|---|---|---|---|
| `gemini` (default) | best, steerable with `style` | ~$0.002/reply | no |
| `say` | robotic; much better with a downloaded neural voice | free | yes |
| `kokoro` | decent English, weak Portuguese | free | yes |

Kokoro is a local 82M-parameter model: `pip install kokoro soundfile` and
`brew install espeak-ng`. Any engine failure falls back to `say`, and the
reason goes to `~/.robot-voice/robot-voice.log`; `status` shows the latest one.

## Config

`~/.robot-voice/config.json` (override the location with `ROBOT_VOICE_HOME`).
It holds everything the commands set, plus `max_chars_prose`,
`max_chars_brief`, `summarizer_model` and `hermes_platforms`.

## How it works

```
robot_voice/
  engine.py       cleanup, shaping, engines, playback, per-session history
  ctl.py          the /speak commands, returning text for any surface to show
  keys.py         where the Gemini key comes from
  claude_code.py  Claude Code hooks: stop, command
  hermes.py       Hermes hook and slash command
hooks/hooks.json  Claude Code hook wiring  → hooks/claude.py
.claude-plugin/   Claude Code plugin + marketplace manifests
skills/speak/     the skill Claude uses for loosely phrased requests
plugin.yaml       Hermes manifest          → __init__.py
bin/robot-voice   the CLI (on Claude's Bash PATH while the plugin is enabled)
```

- **Claude Code** hands the finished reply to the `Stop` hook as
  `last_assistant_message`, so nothing reads the transcript and nothing races
  its writer. The hook runs `async`, so speech never blocks a turn.
- **Hermes** runs hooks and commands inside its own process, so the adapter
  never waits on audio. Every reply and every `/speak test` is spoken by a
  detached child using Hermes' own interpreter, so no `python3` is needed on
  `PATH`.
- Every reply is remembered per session even while muted, so `repeat` works
  after `off`, and five sessions at once each replay their own. A reply that's
  identical to the last one isn't spoken again; Claude Code re-fires `Stop` on
  `/clear`, resume and compact.
- Saying an identical line again replays the clip already on disk. Changing
  the voice, model or style re-synthesizes.

The core is stdlib-only Python. macOS only for now: playback uses `afplay` and
the fallback voice is `say`.

## Adding an agent

An adapter answers two questions (when did a reply finish, and what did it
say) and calls:

```python
from robot_voice import engine, ctl

engine.handle_reply(reply_text, session_id)     # shapes and speaks; blocks while playing
engine.spawn({"op": "reply", "text": reply_text, "session": session_id})  # same, detached
ctl.run(argv, detach=True, session=session_id)  # a /speak command → text to show
```

From outside Python, pipe the reply into a detached `python3 -m robot_voice _job`
with `{"op": "reply", "text": ..., "session": ...}` on stdin, with the repo root
on `PYTHONPATH`.

## Publishing to the Hermes catalog

`hermes plugins install robot-voice`, by bare name, needs an entry in the
curated catalog: a PR to `NousResearch/hermes-agent` adding
`plugin-catalog/robot-voice.yaml`, pinned to an exact commit:

```yaml
name: robot-voice
repo: https://github.com/sugaith/robot-voice
sha: <40-hex commit sha>
description: Speaks each finished reply out loud (Gemini, macOS say, or local Kokoro), with /speak to control and replay it.
maintainer: sugaith
tier: community
category: voice
requires_hermes: ">=0.20.0"
version: "0.1.0"
platforms: [macos]
docs_url: https://github.com/sugaith/robot-voice#readme
capabilities:
  provides_tools: []
  provides_hooks: [post_llm_call]
  provides_middleware: []
  requires_env: []
```

`hermes plugins validate .` is the admission gate the catalog CI runs.

## Development

```bash
python3 -m unittest discover tests   # silent: runs in a throwaway home
claude plugin validate .             # Claude Code plugin + marketplace
hermes plugins validate .            # Hermes catalog admission checks
claude --plugin-dir .                # try it without installing
```

`ROBOT_VOICE_DRYRUN=<file>` writes what would be spoken to that file instead of
playing it. Headless `claude -p` kills async hooks when it exits, so the `Stop`
hook can't be observed there. Test it in an interactive session, or with
`async` off in a scratch copy.

## License

MIT
