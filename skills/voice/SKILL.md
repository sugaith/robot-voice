---
name: voice
description: "Robot voice: show the current voice, or set one."
argument-hint: "[en|pt] [name|random]"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot voice`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice voice <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
