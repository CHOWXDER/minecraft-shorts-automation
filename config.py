import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    OLLAMA_MODEL             = os.getenv("OLLAMA_MODEL", "llama3")
    ELEVENLABS_API_KEY       = os.getenv("ELEVENLABS_API_KEY", "")
    MINECRAFT_FOOTAGE_URL    = os.getenv("MINECRAFT_FOOTAGE_URL", "https://www.youtube.com/watch?v=85z7jqGAGcc")
    GTA_FOOTAGE_URL          = os.getenv("GTA_FOOTAGE_URL", "")
    WHISPER_MODEL            = os.getenv("WHISPER_MODEL", "base")
    OUTPUT_DIR               = os.getenv("OUTPUT_DIR", "output")
    SUBREDDITS               = ["AmItheAsshole", "relationship_advice", "tifu", "offmychest", "confessions"]
    MIN_SCORE                = 500
    CYCLE_INTERVAL_MINUTES   = 60
