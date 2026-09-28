---
name: tldr
description: "Robot voice: say the last reply again as one short sentence."
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

A hook normally answers `/robot-voice:tldr` before it reaches the model. You're
reading this because the arguments weren't valid as typed. Work out what the
user meant, run the matching `robot-voice <command>` (see `robot-voice help all`),
and report its output verbatim.
