---
name: vol
description: "Robot voice: how loud replies are spoken, 0 to 10 (5 is normal, 10 twice as loud, 0 silent)."
argument-hint: "[0-10]"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

A hook normally answers `/robot-voice:vol` before it reaches the model. You're
reading this because the arguments weren't valid as typed. Work out the level
the user meant on the 0 to 10 scale ("louder" is a step or two above the
current one, see `robot-voice vol`), run `robot-voice vol <level>`, and report
its output verbatim.
