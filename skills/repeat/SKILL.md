---
name: repeat
description: "Robot voice: say a reply again."
argument-hint: "[all|brief|prose|smart|slow|<n>|list|show]"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot repeat`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice repeat <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
