"""robot-voice: speaks an agent's replies out loud.

The core is agent-agnostic and stdlib-only. Each agent gets a thin adapter that
answers two questions -- when did a reply finish, and what did it say -- and
hands the text to `engine.handle_reply`.
"""
