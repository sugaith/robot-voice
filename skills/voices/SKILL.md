---
name: voices
description: "Robot voice: list the active engine's voices, per language."
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot voices`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice voices <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
