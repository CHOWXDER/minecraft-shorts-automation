import os


class Config:
    # ── API Keys ────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    REDDIT_CLIENT_ID = os.environ.get('REDDIT_CLIENT_ID')
    REDDIT_CLIENT_SECRET = os.environ.get('REDDIT_CLIENT_SECRET')
    REDDIT_USER_AGENT = os.environ.get('REDDIT_USER_AGENT', 'MinecraftShortsBot/1.0')

    # ── Subreddits to scrape ─────────────────────────────────────────────────
    SUBREDDITS = [
        'Minecraft',
        'MinecraftStories',
        'MinecraftBuddies',
        'mcservers',
        'MinecraftMemes',
    ]

    # ── Video settings ────────────────────────────────────────────────────────
    VIDEO_SETTINGS = {
        'resolution': '1920x1080',
        'fps': 30,
        'bitrate': '5000k',
        'output_resolution': '1080x1920',  # vertical for Shorts
    }

    # ── Upload schedule (UTC) ─────────────────────────────────────────────────
    UPLOAD_SCHEDULE = {
        'days': ['Monday', 'Wednesday', 'Friday'],
        'time': '14:00',  # 2 PM UTC
    }

    # ── Quality thresholds ────────────────────────────────────────────────────
    QUALITY_THRESHOLDS = {
        'min_score': 500,
        'min_views': 100,
        'max_duration': 60,      # Shorts max (seconds)
        'min_velocity': 10,      # upvotes/hour minimum
    }

    # ── OODA Loop settings ────────────────────────────────────────────────────
    OODA = {
        'cycle_interval_minutes': 60,
        'max_decisions_per_cycle': 3,
        'viability_threshold': 62,        # minimum AI composite score (0-100)
        'recency_bonus_hours': 6,         # posts younger than this get a momentum bonus
        'scrape_limit_per_subreddit': 20,
        'scrape_time_filter': 'day',      # praw time_filter: hour|day|week|month
    }
