# robot-voice

Your coding agent reads its replies out loud, in English or Portuguese.

When the agent finishes a turn, robot-voice takes the reply, strips everything
that sounds terrible spoken (code blocks, tables, file paths, emoji), shortens
it to what you'd want to hear, works out whether it's Portuguese or English,
and speaks it in that language's voice. `/robot-voice:use`, `:voice`, `:all`,
`:tldr`, `:brief` and `:help` control it and replay what was said.

| Agent | How it hooks in | commands |
|---|---|---|
| **Claude Code** | plugin: `Stop` hook | `/robot-voice:<command>`, answered by a hook |
| **Hermes Agent** | plugin: `post_llm_call` hook | `/robot:<command>`, native |
| **pi** | package: `agent_end` + `agent_settled` | `/robot:<command>`, native |
| anything else | `robot-voice` CLI | `robot-voice <command>` |

One repo is all three plugins. Settings live in `~/.robot-voice/`, in layers:
global, then per agent, then per session. Two sessions of the same CLI can
speak with different voices, and one agent's change doesn't touch another's.
Replies from every agent play through one queue, so nobody cuts anybody off.

## Engines

| engine | sounds | time to first audio | cost | needs |
|---|---|---|---|---|
| `gemini` | best, steerable with `style` | 1–5 s (network) | ~$0.002/reply | an API key |
| `sano` | good for its size | ~0.3 s EN, ~1.8 s PT | free, offline | the local env |
| `kokoro` | nicer local voices | ~5 s | free, offline | the local env |
| `say` | robotic | instant | free, offline | macOS |

If the chosen engine fails, the next one in the chain takes over, and macOS
`say` is always the last resort. The default chain is
`gemini → sano → kokoro → say`. Choosing `say` directly means only `say`.
`robot-voice status` shows the chain and what actually spoke last, including what
failed before it.

Measured on an M3 Max, from a fresh process with the models downloaded.
[sanoTTS](https://github.com/Ampixa/sanoTTS) is a 1.5–2.3M-parameter model;
[Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) has 82M parameters and loads
PyTorch on every reply, which is where its 5 seconds go.

## Portuguese and English

With `lang auto` (the default), each reply is classified by counting function
words that exist in only one of the two languages ("que", "não", "você" versus
"the", "is", "you"), with Portuguese accents weighing double. It costs
microseconds and needs no model. English code terms inside a Portuguese reply
don't tip it, because the sentence's own glue words outnumber them. A reply
with no signal either way ("OK.") keeps the language of the one before it.

Every engine keeps one voice per language:

| engine | en | pt |
|---|---|---|
| `gemini` | Kore (multilingual) | Kore |
| `sano` | heart | pt-cadu |
| `kokoro` | af_heart | pf_dora |
| `say` | Samantha | Luciana |

`robot-voice lang pt` or `lang en` pins one language instead.

## Install

### Claude Code

```
/plugin marketplace add sugaith/robot-voice
/plugin install robot-voice@robot-voice
```

Installing from `/plugin` asks for a Gemini API key: the field is masked and
stored in the system keychain, not in `settings.json`. Leave it empty to use
the local engines. Installing with `claude plugin install` in a terminal skips
that prompt; set it later with `/plugin configure robot-voice@robot-voice`.

### Hermes Agent

```bash
hermes plugins install sugaith/robot-voice --enable
```

Hermes reads the key from `GEMINI_API_KEY` or `GOOGLE_API_KEY` in
`~/.hermes/.env`. If Hermes already talks to Gemini, you're set. It speaks
turns from the CLI and TUI only: a Telegram message handled by a gateway on the
same machine stays silent (`hermes_platforms` in the config). Don't combine it
with Hermes' own `/voice tts`, or every reply is spoken twice.

### pi

```bash
pi install git:github.com/sugaith/robot-voice
```

or `pi install ./robot-voice` from a clone, which loads it in place. The
package is `pi/extension.ts`, declared in `package.json`. It remembers the
reply at `agent_end` and speaks it at `agent_settled`, once pi won't continue
on its own, in the interactive TUI only, so `pi -p` scripts stay quiet.
`/robot:<command>` shows its answer as a notification. `/robot:use` in plain
words (`/robot:use a female Portuguese voice`) goes to the agent through the
bundled `robot-voice` skill, which also tells the agent that its replies are
spoken and how to change the voice. The extension puts `robot-voice` on the
PATH pi's tools inherit. The key comes from the environment or
the keychain, like any other agent.

### The local engines (sano, Kokoro)

They need numpy, and Kokoro needs PyTorch, so they live in their own Python
environment instead of whatever `python3` your agent runs hooks with:

```bash
conda create -n robot-voice python=3.12
conda run -n robot-voice pip install sanotts kokoro soundfile phonemizer-fork espeakng-loader
brew install espeak-ng
```

robot-voice finds `~/.robot-voice/venv`, or a conda env named `robot-voice`,
by itself. Anywhere else, set `local_python` in the config or `ROBOT_VOICE_PYTHON`.
Only `sanotts` is needed for sano. The Portuguese sano voice (pt-cadu, 3 MB) isn't
in the pip package yet; it downloads from Hugging Face on first use.

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

## Commands

The same six commands in every agent. Claude Code puts the plugin's name
before the colon, Hermes and pi use `robot`:

| Claude Code | Hermes, pi | does |
|---|---|---|
| `/robot-voice:use kokoro pf_dora` | `/robot:use kokoro pf_dora` | switch engine, and optionally the voice |
| `/robot-voice:use heart` | `/robot:use heart` | a voice name alone also picks its engine |
| `/robot-voice:use <plain words>` | `/robot:use <plain words>` | "a female Portuguese voice": the agent maps it |
| `/robot-voice:voice [name]` | `/robot:voice [name]` | show the current voices, or set one |
| `/robot-voice:all` | `/robot:all` | say the last reply again, all of it |
| `/robot-voice:tldr` | `/robot:tldr` | ...as one short sentence (Gemini; without a key, the first one) |
| `/robot-voice:brief` | `/robot:brief` | ...its first sentence and closing question |
| `/robot-voice:help` | `/robot:help` | these, in a few lines |

Exact commands never reach the model: they run locally and show their answer in
place of a turn, with no tokens and no interpretation. Claude Code labels those
answers "blocked by hook". That's the mechanism, not an error. `use` in plain
words goes to the agent: in Claude Code and pi through the bundled skill; in
Hermes, whose plugin commands can only return text, you ask in the chat, and
the agent knows about robot-voice from a short section the plugin adds to its
prompt. In all three, the agent also knows its replies are spoken, so "fala
mais devagar" or "use the Mac voice" in a normal message works too.

Everything else lives in the CLI, `robot-voice <command>`, which the agents run
for you:

```
robot-voice status                    # engine chain, voices, what spoke last
robot-voice on | off
robot-voice mode prose|brief|smart    # how much gets spoken
robot-voice lang auto|pt|en
robot-voice voice en Zarvox           # set a voice for one language explicitly
robot-voice voices                    # the active engine's voices, per language
robot-voice random on|off             # a random voice for every reply
robot-voice model <id>                # Gemini TTS model
robot-voice style Say it calm:        # Gemini delivery direction ("" clears)
robot-voice test [text]
robot-voice stop                      # kill playback
robot-voice reset
robot-voice repeat [slow|<n>|list|show]
robot-voice say hello there           # arbitrary words
robot-voice key                       # store a Gemini key in the keychain
robot-voice help all                  # every command
```

## The Gemini key

Without one, Gemini is skipped and the next engine in the chain speaks. The
first source found wins:

1. Claude Code's plugin config (`/plugin configure robot-voice@robot-voice`)
2. `GEMINI_API_KEY`, then `GOOGLE_API_KEY`, in the environment
3. the macOS keychain: run `robot-voice key` in a terminal to store it there
4. `gemini_api_key` in `~/.robot-voice/config.json`

Never type the key into an agent's prompt. The agents are told to refuse it, because the prompt ends up in the agent's history.

Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
Measured on a typical reply (137 chars, ~9s of audio) with
`gemini-2.5-flash-preview-tts`: about $0.0023 per reply. There is a free tier.

## Modes

| mode | what you hear |
|---|---|
| `brief` | first sentence plus any closing question, ~220 chars (default) |
| `prose` | the whole reply, cleaned, ~600 chars |
| `smart` | a cheap Gemini call rewrites it into one spoken sentence |
| `off` | nothing (replies are still remembered for `repeat`) |

## Sessions, agents, and global

Every setting a command changes (engine, voice, language, mode, random,
on/off, style) is saved in one of three layers, and the most specific wins:

| layer | set with | reaches |
|---|---|---|
| session | `/robot-voice:use kokoro` (the default inside a session) | this session only |
| agent | `/robot-voice:use agent kokoro` | every session of this agent |
| global | `/robot-voice:use global kokoro`, or any command from a bare terminal | every agent |

A session that picks only its Portuguese voice keeps following every other
global voice. `robot-voice status` ends with `set by`, naming what this session
takes from its agent and what it sets itself; `reset`, `reset agent` and
`reset global` clear one layer. When an agent runs `robot-voice` itself, it
acts on its own session: Claude Code's session id reaches it through the
environment, the pi extension exports one, and the Hermes prompt section names
it.

## Config

`~/.robot-voice/config.json` (override the location with `ROBOT_VOICE_HOME`)
holds the global layer and each agent's layer (`agents`); each session keeps
its own under `sessions/`. It also holds `fallbacks` (the chain after the
chosen engine), `local_python`, `max_chars_prose`, `max_chars_brief`,
`summarizer_model` and `hermes_platforms`. Engine failures go to
`~/.robot-voice/robot-voice.log`.

## How it works

```
robot_voice/
  engine.py       cleanup, shaping, the engine chain, playback, per-session history
  voices.py       language detection, voice catalogs, per-language and random picks
  local_tts.py    sano and Kokoro, run inside the local Python environment
  ctl.py          the commands and the six slash-command shortcuts, as text for any surface
  keys.py         where the Gemini key comes from
  claude_code.py  Claude Code hooks: stop, command
  hermes.py       Hermes hook and slash command
pi/extension.ts   pi extension: speech at agent_settled, /robot:<command>
pi/skills/        the skill pi's agent uses for loosely phrased requests
package.json      pi package manifest
hooks/hooks.json  Claude Code hook wiring  → hooks/claude.py
.claude-plugin/   Claude Code plugin + marketplace manifests
skills/           one per /robot-voice:<command>; `use` is also the one Claude sees
plugin.yaml       Hermes manifest          → __init__.py
bin/robot-voice   the CLI (on Claude's Bash PATH while the plugin is enabled)
```

- **Claude Code** hands the finished reply to the `Stop` hook as
  `last_assistant_message`, so nothing reads the transcript and nothing races
  its writer. The hook runs `async`, so speech never blocks a turn.
- **Hermes** runs hooks and commands inside its own process, so the adapter
  never waits on audio. Every reply and every replay is spoken by a
  detached child using Hermes' own interpreter, so no `python3` is needed on
  `PATH`.
- **The core is stdlib-only.** sano and Kokoro run as a subprocess in the local
  environment, so the hook's own `python3` never needs numpy or PyTorch.
- Every reply is remembered per session even while muted, so `repeat` works
  after `off`, and five sessions at once each replay their own. A reply that's
  identical to the last one isn't spoken again; Claude Code re-fires `Stop` on
  `/clear`, resume and compact.
- Playback goes through one queue for every agent and session: a reply that
  finishes while another is being spoken waits its turn. `stop` ends the
  current clip and drops the queue.
- Each utterance gets its own clip under `~/.robot-voice/clips/` (the last 20
  are kept), so a queued one is never overwritten before its turn, and saying
  an identical line again replays it from disk. Changing the engine, voice,
  model or style re-synthesizes.

macOS only for now: playback uses `afplay` and the last fallback is `say`.

## Adding an agent

An adapter answers two questions (when did a reply finish, and what did it
say) and calls:

```python
from robot_voice import engine, ctl

engine.handle_reply(reply_text, session_id)     # shapes and speaks; blocks while playing
engine.spawn({"op": "reply", "text": reply_text, "session": session_id})  # same, detached
ctl.shortcut("use", "kokoro pf_dora", "/robot:")  # a slash command → text to show
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
description: Speaks each finished reply out loud in English and Portuguese (Gemini, local sano/Kokoro, or macOS say), with /robot:<command> to control and replay it.
maintainer: sugaith
tier: community
category: voice
requires_hermes: ">=0.20.0"
version: "0.2.0"
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

`ROBOT_VOICE_DRYRUN=<file>` writes what would be spoken (engine, voice, text)
to that file instead of playing it. Headless `claude -p` kills async hooks
when it exits, so the `Stop` hook can't be observed there. Test it in an
interactive session, or with `async` off in a scratch copy.

## License

MIT
