"""Test environment defaults that never contain production credentials."""

import os

os.environ.setdefault("GEMINI_API_KEY", "ci-test-key")
