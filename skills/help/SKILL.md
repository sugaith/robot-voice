---
name: help
description: "Robot voice: the commands, in a few lines."
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

A hook normally answers `/robot-voice:help` before it reaches the model. You're
reading this because the arguments weren't valid as typed. Work out what the
user meant, run the matching `robot-voice <command>` (see `robot-voice help all`),
and report its output verbatim.
