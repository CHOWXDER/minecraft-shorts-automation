import os


class Config:
    # ── Everything runs locally / free ───────────────────────────────────────
    # No API keys required for the core pipeline.
    # YouTube upload is the only external service — needs client_secrets.json.

    # ── Optional upgrade: ElevenLabs (premium voice) ──────────────────────────
    # Leave blank to use edge_tts (free, Microsoft neural voices).
    ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "tMvyQtpCVQ0DkixuYm6J")

    # ── Production defaults ───────────────────────────────────────────────────
    MINECRAFT_FOOTAGE_URL = os.environ.get(
        "MINECRAFT_FOOTAGE_URL", "https://www.youtube.com/watch?v=85z7jqGAGcc"
    )
    WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
    OUTPUT_DIR    = os.environ.get("OUTPUT_DIR", "output")

    # ── Ollama (local AI scoring) ─────────────────────────────────────────────
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3")

    # ── Subreddits to scrape (anonymous, no account needed) ───────────────────
    SUBREDDITS = [
        "Minecraft",
        "MinecraftStories",
        "MinecraftBuddies",
        "mcservers",
        "MinecraftMemes",
    ]

    # ── Video settings ────────────────────────────────────────────────────────
    VIDEO_SETTINGS = {
        "resolution":        "1920x1080",
        "fps":               30,
        "bitrate":           "5000k",
        "output_resolution": "1080x1920",
    }

    # ── Upload schedule (UTC) ─────────────────────────────────────────────────
    UPLOAD_SCHEDULE = {
        "days": ["Monday", "Wednesday", "Friday"],
        "time": "14:00",
    }

    # ── Quality thresholds ────────────────────────────────────────────────────
    QUALITY_THRESHOLDS = {
        "min_score":    500,
        "min_views":    100,
        "max_duration": 60,
        "min_velocity": 10,
    }

    # ── OODA Loop settings ────────────────────────────────────────────────────
    OODA = {
        "cycle_interval_minutes":      60,
        "max_decisions_per_cycle":     3,
        "viability_threshold":         62,
        "recency_bonus_hours":         6,
        "scrape_limit_per_subreddit":  25,
        "scrape_time_filter":          "day",
    }
