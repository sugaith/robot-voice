---
name: lang
description: "Robot voice: detect the language per reply, or pin one."
argument-hint: "auto|pt|en"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot lang`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice lang <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
