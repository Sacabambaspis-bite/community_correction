"""Backend launcher: inject env vars then start uvicorn in same process.

Usage: python _start_backend.py
"""
import os

# Inject SenseVoice real ASR credentials BEFORE any import that reads os.environ.
# NOTE: use direct assignment (NOT setdefault) because Trae shell may pre-set these
# keys to empty strings, and setdefault would NOT override empty strings.
os.environ["SENSEVOICE_API_URL"] = "http://8.133.237.222:8000/recognize"
os.environ["SENSEVOICE_API_KEY"] = "jrIDYIV1cZKEj4wLqySenGo25AtLxS0XTORyGffyHZU"
# INTENTIONALLY NOT setting CAPTURE_FAKE -> real microphone capture
os.environ["APP_ENV"] = "development"

from app.analysis.providers import sensevoice_configured  # noqa: E402

print("=" * 55)
print("  Community Correction - Backend Launcher")
print("=" * 55)
print(f"  SENSEVOICE_API_URL  = {os.environ['SENSEVOICE_API_URL']}")
print(f"  SENSEVOICE_API_KEY   = {'(set)' if os.environ.get('SENSEVOICE_API_KEY') else '(MISSING)'}")
print(f"  sensevoice_configured = {sensevoice_configured()}")
print(f"  CAPTURE_FAKE = {os.environ.get('CAPTURE_FAKE', '(not set -> real)')}")
print()

import uvicorn  # noqa: E402

uvicorn.run("app.api.main:app", host="127.0.0.1", port=8000, log_level="info")
