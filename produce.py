"""
produce.py — End-to-end Minecraft Shorts producer

Improvements over v1:
  - Word-timed subtitles from edge_tts (huge engagement boost for Shorts)
  - N-word subtitle grouping with bold styled burn-in
  - sys.executable for cross-platform yt_dlp (no "py" Windows-only hack)
  - Better yt_dlp format string (prefers MP4 to avoid remux failures)
  - CRF quality control instead of unconstrained encoding
  - Audio: 192k AAC, 44100 Hz normalised
  - Smarter clip start: avoids first/last AVOID_EDGE_SECS of the footage
  - Subtitle fallback: renders without subs if TTS timing data is empty
"""

import os
import re
import sys
import asyncio
import random
import subprocess

import edge_tts

# ── CONFIG ───────────────────────────────────────────────────────────────────

MANUAL_STORY = """So my roommate has been stealing my food for months. I labeled \
everything, talked to him twice, he still kept doing it. Last night I spent two \
hours making a lasagna, came back and he ate half of it straight from the dish. \
I finally lost it and told him he has two weeks to find somewhere else to live. \
Now my other roommates are saying I overreacted and that it was just food. But \
it's not just food — it's the fact that I've asked him repeatedly and he just \
doesn't care. My girlfriend says I did the right thing. Am I the asshole for \
kicking him out over this?"""

MINECRAFT_URL  = "https://www.youtube.com/watch?v=n8X9_MgEdCg"
OUTPUT_FILE    = "final_video.mp4"
VOICE          = "en-US-GuyNeural"
WORDS_PER_SUB  = 3    # words per subtitle card (2–4 works best for Shorts)
AVOID_EDGE_SECS = 60  # skip this many seconds at the start/end of footage

# ── SUBTITLE STYLE ────────────────────────────────────────────────────────────
# ASS force_style string — tune FontSize and MarginV to taste
SUB_STYLE = (
    "FontName=Arial,"
    "FontSize=85,"
    "Bold=1,"
    "PrimaryColour=&H00FFFFFF,"   # white fill
    "OutlineColour=&H00000000,"   # black outline
    "Outline=4,"
    "Shadow=2,"
    "Alignment=2,"                # centre-bottom
    "MarginV=120"                 # px from bottom edge
)

# ─────────────────────────────────────────────────────────────────────────────

os.makedirs("temp", exist_ok=True)

title     = "AITA for kicking out my roommate over food?"
full_text = f"{title}. {MANUAL_STORY}"
print(f"Story: {title}")


# ── AUDIO + WORD-TIMED SUBTITLES ──────────────────────────────────────────────

async def _generate(text: str) -> list[tuple[float, float, str]]:
    """
    Stream TTS audio to disk and return word-boundary cues as
    (start_sec, end_sec, word) tuples.

    WordBoundary offsets from edge_tts are in 100-nanosecond ticks.
    Avoids SubMaker entirely — works across all edge_tts versions.
    """
    communicate = edge_tts.Communicate(text, VOICE)
    cues: list[tuple[float, float, str]] = []

    with open("temp/voiceover.mp3", "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000          # ticks → seconds
                end   = (chunk["offset"] + chunk["duration"]) / 10_000_000
                cues.append((start, end, chunk["text"]))

    return cues


def _fmt_srt_time(secs: float) -> str:
    h  = int(secs // 3600)
    m  = int((secs % 3600) // 60)
    s  = int(secs % 60)
    ms = int(round((secs % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _build_srt(cues: list[tuple[float, float, str]]) -> str:
    """Group word cues into N-word SRT chunks, uppercased for impact."""
    if not cues:
        return ""

    blocks = []
    for i in range(0, len(cues), WORDS_PER_SUB):
        chunk = cues[i : i + WORDS_PER_SUB]
        start = _fmt_srt_time(chunk[0][0])
        end   = _fmt_srt_time(chunk[-1][1])
        text  = " ".join(c[2] for c in chunk).upper()
        blocks.append(f"{i // WORDS_PER_SUB + 1}\n{start} --> {end}\n{text}\n")

    return "\n".join(blocks)


print("Generating voiceover + subtitles…")
cues = asyncio.run(_generate(full_text))
srt  = _build_srt(cues)

if srt:
    with open("temp/subtitles.srt", "w", encoding="utf-8") as f:
        f.write(srt)
    print(f"  {srt.count('-->')} subtitle cues written")
    has_subs = True
else:
    print("  [warn] No subtitle timing data — rendering without subtitles")
    has_subs = False


# ── AUDIO DURATION ────────────────────────────────────────────────────────────

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "temp/voiceover.mp3"],
    capture_output=True, text=True,
)
if not probe.stdout.strip():
    sys.exit("ffprobe failed on voiceover — check edge-tts output")
audio_duration = float(probe.stdout.strip())
print(f"Audio duration: {audio_duration:.1f}s")


# ── DOWNLOAD ──────────────────────────────────────────────────────────────────

if not os.path.exists("temp/minecraft.mp4"):
    print("Downloading Minecraft footage…")
    subprocess.run(
        [
            sys.executable, "-m", "yt_dlp",
            "--cookies-from-browser", "firefox",
            "-o", "temp/minecraft.mp4",
            # prefer a single MP4 file to avoid ffmpeg remux surprises
            "-f", "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
            MINECRAFT_URL,
        ],
        check=True,
    )
else:
    print("Minecraft footage cached — skipping download")


# ── CLIP SELECTION ────────────────────────────────────────────────────────────

mc_probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
     "-of", "default=noprint_wrappers=1:nokey=1", "temp/minecraft.mp4"],
    capture_output=True, text=True,
)
if not mc_probe.stdout.strip():
    sys.exit("ffprobe failed on minecraft.mp4 — download may have failed")

mc_duration = float(mc_probe.stdout.strip())
avoid       = min(AVOID_EDGE_SECS, mc_duration * 0.1)
max_start   = max(avoid, mc_duration - audio_duration - avoid)
start_time  = random.uniform(avoid, max_start)
print(f"Minecraft clip: {start_time:.1f}s → {start_time + audio_duration:.1f}s")


# ── RENDER ────────────────────────────────────────────────────────────────────

if has_subs:
    # Single -vf pass: crop → scale → burn subtitles
    sub_path   = "temp/subtitles.srt"
    vf = (
        f"[0:v]crop=ih*9/16:ih,scale=1080:1920,"
        f"subtitles={sub_path}:force_style='{SUB_STYLE}'[vout]"
    )
else:
    vf = "[0:v]crop=ih*9/16:ih,scale=1080:1920[vout]"

print("Rendering final video…")
try:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(start_time), "-t", str(audio_duration + 1),
            "-i", "temp/minecraft.mp4",
            "-i", "temp/voiceover.mp3",
            "-filter_complex", vf,
            "-map", "[vout]", "-map", "1:a",
            "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-shortest",
            OUTPUT_FILE,
        ],
        check=True,
    )
    print(f"\nDone! → {OUTPUT_FILE}")
except subprocess.CalledProcessError:
    sys.exit("FFmpeg failed — check input files and ffmpeg installation")
