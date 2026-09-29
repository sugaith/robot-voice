---
name: tldr
description: "Robot voice: a short summary of the last reply, 3 to 5 sentences on what was done and the result."
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

A hook normally answers `/robot-voice:tldr` before it reaches the model. You're
reading this because the arguments weren't valid as typed. Work out what the
user meant, run the matching `robot-voice <command>` (see `robot-voice help all`),
and report its output verbatim.
