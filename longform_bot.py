"""
longform_bot.py — Daily long-form YouTube video.
Scrapes top AITA stories → ElevenLabs TTS → Whisper captions → FFmpeg render → YouTube upload
Output: 16:9 1920x1080, 10-15 minutes, one video per run.
"""

import os
import time
import subprocess
import sys
import asyncio
import random
import hashlib
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

from reddit_scraper import RedditScraper
from orient import Orient
from youtube_uploader import upload_video

TEMP       = Path("temp")
CACHE      = TEMP / "cache"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

ELEVENLABS_KEY  = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE = "pNInz6obpgDQGcFmaJgB"  # Adam
WHISPER_MODEL   = os.getenv("WHISPER_MODEL", "base")
MC_PATH         = TEMP / "minecraft.mp4"

MIN_SCORE       = 1000
MIN_TEXT_LEN    = 300
MAX_WORDS       = 400   # per story
NUM_STORIES     = 7
TARGET_SUBREDDITS = ["AmItheAsshole", "relationship_advice", "tifu", "offmychest"]


# ── TTS ───────────────────────────────────────────────────────────────────────

def tts_elevenlabs(text: str, path: Path) -> bool:
    import requests
    key = hashlib.md5(f"{text}:{ELEVENLABS_VOICE}:lf1".encode()).hexdigest()
    cached = CACHE / f"{key}.mp3"
    if cached.exists():
        import shutil; shutil.copy(cached, path)
        return True
    try:
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
            headers={"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=120,
        )
        resp.raise_for_status()
        path.write_bytes(resp.content)
        cached.write_bytes(resp.content)
        return True
    except Exception as e:
        print(f"  [TTS] ElevenLabs failed: {e} — using edge_tts")
        return False


def tts_edge(text: str, path: Path) -> None:
    import edge_tts
    async def _run():
        comm = edge_tts.Communicate(text, voice="en-US-ChristopherNeural")
        await comm.save(str(path))
    asyncio.run(_run())


def generate_tts(text: str, path: Path) -> None:
    if ELEVENLABS_KEY and not tts_elevenlabs(text, path):
        tts_edge(text, path)
    elif not ELEVENLABS_KEY:
        tts_edge(text, path)


# ── WHISPER ───────────────────────────────────────────────────────────────────

def transcribe(audio_path: Path):
    import whisper
    print(f"  [Whisper] transcribing {audio_path.name}…")
    model = whisper.load_model(WHISPER_MODEL)
    result = model.transcribe(str(audio_path), word_timestamps=True, language="en")
    cues = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []):
            word = w.get("word", "").strip()
            if word:
                cues.append((float(w["start"]), float(w["end"]), word))
    return cues


# ── SUBTITLES ─────────────────────────────────────────────────────────────────

def ass_time(secs: float) -> str:
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    cs = int(round((secs % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_subtitles(cues: list, output_path: Path, offset: float = 0.0) -> None:
    header = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial Black,70,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,4,0,1,6,2,2,80,80,80,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    colors = ["&H0000FFFF", "&H0000FF00", "&H00FF00FF", "&H000080FF", "&H00FFFFFF"]
    for i in range(0, len(cues), 3):
        chunk = cues[i:i+3]
        start = ass_time(chunk[0][0] + offset)
        end   = ass_time(chunk[-1][1] + offset)
        text  = " ".join(c[2] for c in chunk).upper()
        color = colors[i % len(colors)]
        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{{\\c{color}}}{text}")
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


# ── AUDIO CONCAT ──────────────────────────────────────────────────────────────

def concat_audio(parts: list[Path], output: Path) -> float:
    list_file = TEMP / "concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in parts), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(output)],
        check=True, capture_output=True,
    )
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(output)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


# ── TITLE CARD ────────────────────────────────────────────────────────────────

def make_title_card(title: str, duration: float, output: Path) -> None:
    safe_title = title.replace("'", "\\'").replace(":", "\\:").replace("%", "\\%")[:60]
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:d={duration}",
         "-vf", (
             f"drawtext=text='{safe_title}':fontcolor=white:fontsize=60:"
             f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.8:boxborderw=20"
         ),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output)],
        check=True, capture_output=True,
    )


# ── RENDER ────────────────────────────────────────────────────────────────────

def render(audio: Path, subs: Path, duration: float, output: Path) -> None:
    mc_dur  = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(MC_PATH)],
        capture_output=True, text=True, check=True,
    ).stdout.strip())

    start = random.uniform(60, max(60, mc_dur - duration - 60))

    try:
        subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, check=True,
        )
        codec = "h264_nvenc"
        codec_flags = ["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "19", "-preset", "p4", "-b:v", "0"]
    except Exception:
        codec = "libx264"
        codec_flags = ["-c:v", "libx264", "-crf", "19", "-preset", "medium"]

    print(f"  [Render] {duration:.0f}s video  codec={codec}")

    try:
        sub_path = str(subs.resolve().relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        sub_path = str(subs.resolve()).replace("\\", "/").replace(":", "\\:")

    subprocess.run(
        ["ffmpeg", "-y",
         "-ss", str(start), "-t", str(duration + 2), "-i", str(MC_PATH),
         "-i", str(audio),
         "-filter_complex",
         f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
         f"eq=saturation=1.4:contrast=1.1,ass={sub_path}[vout];"
         f"[1:a]loudnorm=I=-14:LRA=11:TP=-1.5[a]",
         "-map", "[vout]", "-map", "[a]",
         *codec_flags,
         "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
         "-shortest", str(output)],
        check=True, capture_output=True,
    )
    print(f"  [Render] done → {output}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def run():
    print("\n" + "=" * 60)
    print("  LONG-FORM BOT START")
    print("=" * 60)

    if not MC_PATH.exists():
        sys.exit("[ERROR] temp/minecraft.mp4 not found. Run the shorts bot first.")

    # Scrape stories
    print("\n[1/5] Scraping Reddit for top AITA stories…")
    scraper = RedditScraper()
    orient  = Orient()
    all_posts = []
    for sub in TARGET_SUBREDDITS:
        posts = scraper.get_top_posts(sub)
        all_posts.extend(posts)
        print(f"  r/{sub}: {len(posts)} posts")

    # Filter quality posts
    quality = [
        p for p in all_posts
        if p.get("score", 0) >= MIN_SCORE and len(p.get("text", "")) >= MIN_TEXT_LEN
    ]
    scored  = orient.analyse(quality) if quality else []
    stories = scored[:NUM_STORIES] if scored else []

    if len(stories) < 3:
        print(f"  Only {len(stories)} quality stories found — using story bank to fill")
        from story_bank import STORIES as BANK
        needed = NUM_STORIES - len(stories)
        for s in random.sample(BANK, min(needed, len(BANK))):
            stories.append({"title": s["title"], "text": s["text"], "ai_score": 10})

    print(f"  {len(stories)} stories selected")

    # Generate TTS for each story
    print("\n[2/5] Generating voiceovers…")
    audio_parts = []
    for i, story in enumerate(stories):
        words = story["text"].split()[:MAX_WORDS]
        text  = f"{story['title']}. " + " ".join(words)
        path  = TEMP / f"lf_story_{i}.mp3"
        print(f"  Story {i+1}/{len(stories)}: {story['title'][:50]}")
        generate_tts(text, path)
        audio_parts.append(path)
        time.sleep(0.5)

    # Concatenate all audio
    print("\n[3/5] Stitching audio…")
    full_audio = TEMP / "lf_full_audio.mp3"
    total_dur  = concat_audio(audio_parts, full_audio)
    print(f"  Total duration: {total_dur:.0f}s ({total_dur/60:.1f} min)")

    # Whisper transcription
    print("\n[4/5] Transcribing with Whisper…")
    cues = transcribe(full_audio)
    subs_path = TEMP / "lf_subtitles.ass"
    build_subtitles(cues, subs_path)
    print(f"  {len(cues)} word cues → subtitles built")

    # Render
    print("\n[5/5] Rendering video…")
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"longform_{timestamp}.mp4"
    render(full_audio, subs_path, total_dur, output_path)

    # Upload
    titles_preview = " | ".join(s["title"][:30] for s in stories[:3])
    yt_title = f"Reddit AITA Compilation #{timestamp[-6:]} 🔥"
    description = (
        f"Today's most viral AITA stories from Reddit.\n\n"
        + "\n".join(f"• {s['title']}" for s in stories)
        + "\n\nDrop your verdicts in the comments 👇\n\n"
        "#AITA #Reddit #AmITheAsshole #RedditStories #Storytime #Drama"
    )
    print(f"\n  Uploading: {yt_title}")
    upload_video(
        file=str(output_path),
        title=yt_title,
        description=description,
        tags=["aita", "reddit", "am i the asshole", "reddit stories", "storytime",
              "drama", "relationship advice", "reddit compilation", "viral reddit"],
    )

    os.startfile(os.path.abspath(output_path))
    print(f"\n  Done → {output_path}")


if __name__ == "__main__":
    run()
