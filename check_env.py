"""
check_env.py — Pre-flight health check.
Run: py check_env.py
"""

import sys
from pathlib import Path


def validate() -> None:
    print("\n── Free Mode Health Check ────────────────────────────────────")

    # Ollama
    try:
        from ollama_vault import is_running
        if is_running():
            print("  ✓ Ollama is running  (AI scoring active)")
        else:
            print("  – Ollama not running  (will use heuristic scoring)")
            print("    Fix: open the Ollama app, then run: ollama serve")
    except Exception as e:
        print(f"  ✗ Ollama check failed: {e}")

    # edge-tts
    try:
        import edge_tts
        print("  ✓ edge-tts installed  (TTS voice ready)")
    except ImportError:
        print("  ✗ edge-tts MISSING")
        print("    Fix: pip install edge-tts")

    # Whisper
    try:
        import whisper
        print("  ✓ openai-whisper installed  (caption sync ready)")
    except ImportError:
        print("  ✗ openai-whisper MISSING")
        print("    Fix: pip install openai-whisper")

    # yt-dlp
    try:
        import yt_dlp
        print("  ✓ yt-dlp installed  (footage download ready)")
    except ImportError:
        print("  ✗ yt-dlp MISSING")
        print("    Fix: pip install yt-dlp")

    # FFmpeg
    import subprocess
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        print("  ✓ FFmpeg found")
    except Exception:
        print("  ✗ FFmpeg NOT found")
        print("    Fix: https://ffmpeg.org/download.html  (add to PATH)")

    # YouTube
    print()
    if Path("client_secrets.json").exists():
        print("  ✓ client_secrets.json found  (YouTube upload ready)")
        if Path("youtube_token.pickle").exists():
            print("  ✓ youtube_token.pickle cached  (non-interactive upload ready)")
        else:
            print("  – youtube_token.pickle missing  (first upload will open browser)")
    else:
        print("  – client_secrets.json not found  (YouTube upload will be skipped)")
        print("    Get it: Google Cloud Console → APIs & Services → Credentials → Download OAuth JSON")

    # Footage shortcut hint
    mc = Path("temp") / "minecraft.mp4"
    print()
    if mc.exists():
        print(f"  ✓ temp/minecraft.mp4 found  ({mc.stat().st_size // 1024 // 1024} MB)")
    else:
        print("  – temp/minecraft.mp4 not found")
        print("    Optional: place a Minecraft .mp4 there to skip downloading every run")

    print("\n  To start the bot:  py ooda_loop.py")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    validate()
