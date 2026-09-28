---
name: stop
description: "Robot voice: stop the audio playing right now."
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

Shortcut for `/robot-voice:robot stop`. A hook normally answers it before it
reaches the model. You're reading this because the arguments weren't a valid
command as typed.

Work out what the user meant, using the robot skill's mapping, and run:

```
robot-voice stop <arguments>
```

Report its output verbatim. `robot-voice help` lists every command.
