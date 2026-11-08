---
name: style
description: "Robot voice: how replies are delivered (Gemini) -- serious-tech, desperate-doomer, sarcastic-ahole, your own words, or off."
argument-hint: "[serious-tech|desperate-doomer|sarcastic-ahole|<words>|off]"
disable-model-invocation: true
allowed-tools: Bash(robot-voice:*)
---

A hook normally answers `/robot-voice:style` before it reaches the model. You're
reading this because the hook didn't run. Run `robot-voice style <arguments>`
(bare `robot-voice style` lists the presets) and report its output verbatim.
