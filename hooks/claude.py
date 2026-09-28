#!/usr/bin/env python3
"""Entry point for the Claude Code hooks: claude.py stop|command."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from robot_voice.claude_code import main  # noqa: E402

sys.exit(main(sys.argv[1:]))
