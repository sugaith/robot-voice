---
name: mode
description: "Robot voice: how much of each reply gets spoken."
argument-hint: "brief|prose|smart|off"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot mode`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice mode <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
