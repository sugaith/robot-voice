---
name: use
description: "Robot voice: switch the speech engine."
argument-hint: "gemini|sano|kokoro|say"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot use`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice use <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
