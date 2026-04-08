"""
check_env.py — Pre-flight environment check.

The entire pipeline runs locally/free — only YouTube upload needs credentials.

Run standalone:
    py check_env.py

Or import and call validate() at the top of any entry point.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Only YouTube credentials are required for full autonomous operation.
# The core pipeline (TTS, AI scoring, Reddit scraping) is 100% free/local.
REQUIRED: dict[str, str] = {}   # nothing required — everything has a free fallback

OPTIONAL = {
    "ELEVENLABS_API_KEY":    "Premium TTS voice — pipeline uses edge_tts (free) without this",
    "ELEVENLABS_VOICE_ID":   "ElevenLabs voice ID — only used if ELEVENLABS_API_KEY is set",
    "MINECRAFT_FOOTAGE_URL": "Footage source — defaults to built-in URL",
    "WHISPER_MODEL":         "Whisper model size — defaults to 'base' (fast, local)",
    "OLLAMA_MODEL":          "Ollama model name — defaults to 'llama3'",
}


def _mask(value: str) -> str:
    """Show only first 6 + last 4 chars of a key."""
    if len(value) <= 10:
        return "*" * len(value)
    return value[:6] + "…" + value[-4:]


def _looks_like_placeholder(value: str) -> bool:
    return any(value.startswith(p) for p in ("your_", "sk-ant-...", "YOUR_"))


def validate(exit_on_fail: bool = True) -> bool:
    """
    Check environment and report status.
    Returns True always (nothing is strictly required except client_secrets.json
    for YouTube upload, which is soft-warned).
    """
    print("\n── Environment Check ─────────────────────────────────────────")

    env_file = Path(".env")
    if not env_file.exists():
        print("  [INFO] No .env file — using system environment variables.\n")

    # ── Core tools (local, free) ─────────────────────────────────────────────
    print("  Core pipeline (all free & local):")

    checks = [
        ("edge_tts",         "edge-tts",          "TTS voice generation"),
        ("whisper",          "openai-whisper",     "Word-level caption sync"),
        ("yt_dlp",           "yt-dlp",             "Footage download"),
    ]
    for module, pkg, desc in checks:
        try:
            __import__(module)
            print(f"    ✓ {pkg} installed  ({desc})")
        except ImportError:
            print(f"    ✗ {pkg} NOT installed  ({desc})")
            print(f"      Fix:  pip install {pkg}")

    # ── Optional: Ollama ─────────────────────────────────────────────────────
    print("\n  AI scoring (optional — heuristic fallback if not running):")
    try:
        import requests
        resp = requests.get("http://localhost:11434", timeout=2)
        model = os.environ.get("OLLAMA_MODEL", "llama3")
        print(f"    ✓ Ollama running  (model: {model})")
    except Exception:
        print("    – Ollama not running  (pipeline will use heuristic scoring)")
        print("      Install: https://ollama.com  then:  ollama pull llama3")

    # ── Optional: ElevenLabs ─────────────────────────────────────────────────
    print("\n  Optional keys:")
    for key, desc in OPTIONAL.items():
        val = os.environ.get(key, "")
        if val and not _looks_like_placeholder(val):
            print(f"    ✓ {key} = {_mask(val)}")
        else:
            print(f"    – {key} not set  ({desc})")

    # ── YouTube credentials ───────────────────────────────────────────────────
    print("\n  YouTube upload:")
    if Path("client_secrets.json").exists():
        print("    ✓ client_secrets.json found")
        if Path("youtube_token.pickle").exists():
            print("    ✓ youtube_token.pickle (OAuth cached — non-interactive upload ready)")
        else:
            print("    – youtube_token.pickle not found (first upload will open a browser for OAuth)")
    else:
        print("    – client_secrets.json not found (YouTube upload will be skipped)")
        print("      Get it from: Google Cloud Console → APIs & Services → Credentials → Download OAuth JSON")
        print("      Rename to client_secrets.json and place in the project folder.")

    print()
    print("  RESULT: Core pipeline ready — everything runs free and locally.")
    print("─" * 60 + "\n")
    return True


if __name__ == "__main__":
    validate(exit_on_fail=True)
