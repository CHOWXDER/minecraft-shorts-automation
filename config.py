import os

class Config:
    # API Keys
    API_KEY = os.environ.get('API_KEY')
    ANOTHER_API_KEY = os.environ.get('ANOTHER_API_KEY')

    # Subreddits to scrape
    SUBREDDITS = [
        'Minecraft',
        'MinecraftBuddies',
        'mcservers',
        # Add more subreddits as needed
    ]

    # Video settings
    VIDEO_SETTINGS = {
        'resolution': '1920x1080',  # Full HD
        'fps': 30,
        'bitrate': '5000k',
    }

    # Upload schedule (in UTC)
    UPLOAD_SCHEDULE = {
        'days': ['Monday', 'Wednesday', 'Friday'],
        'time': '14:00',  # 2 PM UTC
    }

    # Quality thresholds
    QUALITY_THRESHOLDS = {
        'min_views': 100,
        'max_duration': 600,  # 10 minutes in seconds
    }
