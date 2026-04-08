#!/usr/bin/env python3
"""
produce.py — Elite Shorts Production Pipeline
Features: ElevenLabs TTS + Whisper caption sync, parallel workers,
          hash caching, 4 animation styles, loudnorm, emoji injection, CLI

Whisper runs 100% locally after ElevenLabs generates the audio — free,
offline, word-level accuracy with zero per-character alignment fiddling.
"""

import argparse
import base64
import hashlib
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

# ── DEFAULTS ──────────────────────────────────────────────────────────────────

DEFAULT_STORY = (
    "So my roommate has been stealing my food for months. I labeled everything, "
    "talked to him twice, he still kept doing it. Last night I spent two hours "
    "making a lasagna, came back and he ate half of it straight from the dish. "
    "I finally lost it and told him he has two weeks to find somewhere else to live. "
    "Now my other roommates are saying I overreacted and that it was just food. But "
    "it's not just food — it's the fact that I've asked him repeatedly and he just "
    "doesn't care. My girlfriend says I did the right thing. Am I the asshole for "
    "kicking him out over this?"
)
DEFAULT_TITLE = "AITA for kicking out my roommate over food?"
DEFAULT_URL   = "https://www.youtube.com/watch?v=85z7jqGAGcc"
DEFAULT_VOICE = "tMvyQtpCVQ0DkixuYm6J"
DEFAULT_OUT   = "final_video.mp4"

TEMP  = Path("temp")
CACHE = TEMP / "cache"

# ── SUBTITLE STYLE ────────────────────────────────────────────────────────────

COLORS = [
    "&H0000FFFF",  # yellow
    "&H0000FF00",  # green
    "&H00FF00FF",  # magenta
    "&H000080FF",  # orange
    "&H009314FF",  # purple
    "&H007FFF00",  # spring green
    "&H0000D7FF",  # gold
    "&H00FF0080",  # hot pink
    "&H00FFFFFF",  # white
    "&H0080FFFF",  # light yellow
]

EMOJI_MAP = {
    "food": "🍕",       "lasagna": "🍝",      "roommate": "🏠",
    "roommates": "🏠",  "ate": "😤",           "eating": "😤",
    "stealing": "😱",   "steal": "😱",         "kicked": "🚪",
    "kicking": "🚪",    "wrong": "❌",          "right": "✅",
    "girlfriend": "💕", "overreacted": "😭",   "asshole": "💀",
    "labeled": "🏷️",   "asked": "🙏",          "care": "💔",
    "weeks": "📅",      "months": "📆",         "dish": "🍽️",
    "hours": "⏰",      "live": "🏃",           "mad": "😡",
    "angry": "😠",      "lost": "💥",           "finally": "⚡",
    "twice": "✌️",      "night": "🌙",          "found": "🔍",
    "home": "🏡",       "money": "💰",          "work": "💼",
}

ANIMATIONS = ["pop", "bounce", "zoom", "slam"]


# ── DATA CLASSES ──────────────────────────────────────────────────────────────

@dataclass
class WordCue:
    start: float
    end: float
    text: str


@dataclass
class Config:
    story: str
    title: str
    voice_id: str
    url: str
    output: str
    font_size: int = 13
    words_per_sub: int = 3
    avoid_edge_secs: int = 60
    whisper_model: str = "base"


# ── TTS ENGINE ────────────────────────────────────────────────────────────────

class TTSEngine:
    """ElevenLabs TTS with MD5-based disk cache and exponential-backoff retry."""

    def __init__(self, api_key: str, voice_id: str):
        self.client   = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(f"{text}:{self.voice_id}:v3".encode()).hexdigest()

    def generate(self, text: str, audio_path: Path) -> None:
        """Generate TTS audio, using cache when available."""
        CACHE.mkdir(parents=True, exist_ok=True)
        key       = self._cache_key(text)
        cache_mp3 = CACHE / f"{key}.mp3"

        if cache_mp3.exists():
            print("  [TTS] cache hit — copying audio")
            shutil.copy(cache_mp3, audio_path)
            return

        print("  [TTS] calling ElevenLabs…")
        for attempt in range(3):
            try:
                response = self.client.text_to_speech.convert_with_timestamps(
                    voice_id=self.voice_id,
                    text=text,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                audio_bytes = base64.b64decode(response.audio_base_64)
                audio_path.write_bytes(audio_bytes)
                cache_mp3.write_bytes(audio_bytes)
                print("  [TTS] audio written")
                return
            except Exception as exc:
                wait = 2 ** attempt
                print(f"  [TTS] attempt {attempt + 1} failed: {exc} — retrying in {wait}s")
                time.sleep(wait)

        sys.exit("[TTS] ElevenLabs failed after 3 attempts")


# ── WHISPER ENGINE ────────────────────────────────────────────────────────────

class WhisperEngine:
    """
    Local OpenAI Whisper for perfect word-level caption timing.
    Free, offline, gold-standard accuracy — no API cost.

    Install once:  py -m pip install openai-whisper
    Model sizes:   tiny (~1s/min audio) → large (~8x slower, most accurate)
    'base' is the sweet spot for Shorts (fast + good enough).
    """

    def __init__(self, model_name: str = "base"):
        self.model_name = model_name
        self._model     = None  # lazy-loaded on first use

    def _load(self):
        if self._model is None:
            try:
                import whisper  # noqa: PLC0415
                print(f"  [Whisper] loading '{self.model_name}' model…")
                self._model = whisper.load_model(self.model_name)
            except ImportError:
                sys.exit(
                    "\n[Whisper] openai-whisper is not installed.\n"
                    "Fix:  py -m pip install openai-whisper\n"
                )
        return self._model

    def transcribe(self, audio_path: Path) -> list[WordCue]:
        """Return word-level cues from local Whisper transcription."""
        model  = self._load()
        print(f"  [Whisper] transcribing {audio_path.name}…")
        result = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",
        )
        cues: list[WordCue] = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                w = word.get("word", "").strip()
                if w:
                    cues.append(WordCue(
                        start=float(word["start"]),
                        end=float(word["end"]),
                        text=w,
                    ))
        print(f"  [Whisper] {len(cues)} word cues extracted")
        return cues


# ── SUBTITLE ENGINE ───────────────────────────────────────────────────────────

class SubtitleEngine:
    """
    Builds an ASS subtitle file from WordCues.
    Per-card: random animation, cycling colour, emoji injection.
    """

    ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,4,2,5,30,30,0,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

    def __init__(self, font_size: int = 13, words_per_sub: int = 3):
        self.font_size     = font_size
        self.words_per_sub = words_per_sub

    @staticmethod
    def _ass_time(secs: float) -> str:
        h  = int(secs // 3600)
        m  = int((secs % 3600) // 60)
        s  = int(secs % 60)
        cs = int(round((secs % 1) * 100))
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _anim_tags(style: str) -> str:
        if style == "pop":
            return r"{\fscx130\fscy130\t(0,100,\fscx100\fscy100)}"
        if style == "bounce":
            return r"{\fscx85\fscy85\t(0,70,\fscx115\fscy115)\t(70,140,\fscx100\fscy100)}"
        if style == "zoom":
            return r"{\fscx40\fscy40\t(0,130,\fscx100\fscy100)}"
        if style == "slam":
            return r"{\fscx160\fscy160\t(0,80,\fscx95\fscy95)\t(80,140,\fscx100\fscy100)}"
        return ""

    @staticmethod
    def _inject_emoji(word: str) -> str:
        clean = word.lower().rstrip(".,!?;:")
        emoji = EMOJI_MAP.get(clean, "")
        return f"{word} {emoji}" if emoji else word

    def build(self, cues: list[WordCue], output_path: Path) -> None:
        header    = self.ASS_HEADER.format(fontsize=self.font_size)
        events: list[str] = []
        color_idx = 0

        for i in range(0, len(cues), self.words_per_sub):
            chunk = cues[i : i + self.words_per_sub]
            start = self._ass_time(chunk[0].start)
            end   = self._ass_time(chunk[-1].end)

            words = [c.text for c in chunk]
            # Sentence capitalisation
            words[0] = words[0].capitalize()
            # Emoji injection
            words = [self._inject_emoji(w) for w in words]

            color     = COLORS[color_idx % len(COLORS)]
            color_idx += 1
            anim_tag  = self._anim_tags(random.choice(ANIMATIONS))
            color_tag = f"{{\\c{color}}}"

            text = " ".join(words).upper()
            line = (
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
                f"{anim_tag}{color_tag}{text}"
            )
            events.append(line)

        output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
        print(f"  [Subs] {len(events)} subtitle cards → {output_path.name}")


# ── FOOTAGE ENGINE ────────────────────────────────────────────────────────────

class FootageEngine:
    """Download and cache Minecraft footage via yt_dlp."""

    def __init__(self, url: str, output_path: Path):
        self.url         = url
        self.output_path = output_path

    def ensure(self) -> None:
        if self.output_path.exists():
            print("  [Footage] cached — skipping download")
            return
        print("  [Footage] downloading…")
        subprocess.run(
            [
                sys.executable, "-m", "yt_dlp",
                "--js-runtimes", "node",
                "--cookies-from-browser", "firefox",
                "-o", str(self.output_path),
                "-f", "299+140/136+140/18",
                self.url,
            ],
            check=True,
        )


# ── RENDERER ──────────────────────────────────────────────────────────────────

class Renderer:
    """FFmpeg: crop→scale→burn ASS subs, loudnorm audio, CRF 19."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @staticmethod
    def _probe_duration(path: Path) -> float:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(r.stdout.strip())

    @staticmethod
    def _safe_path(path: Path) -> str:
        """
        Return an FFmpeg-safe path for the ASS filter.
        Prefer a relative path — it has no drive-letter colon, which newer
        FFmpeg (8.x) misparses as an option separator.
        """
        try:
            rel = path.resolve().relative_to(Path.cwd())
            return str(rel).replace("\\", "/")
        except ValueError:
            # File is outside cwd — fall back to absolute with colon escaped
            return str(path.resolve()).replace("\\", "/").replace(":", "\\:")

    def render(self, footage: Path, audio: Path, subs: Path, output: Path) -> None:
        audio_dur  = self._probe_duration(audio)
        mc_dur     = self._probe_duration(footage)
        avoid      = min(self.cfg.avoid_edge_secs, mc_dur * 0.1)
        max_start  = max(avoid, mc_dur - audio_dur - avoid)
        start_time = random.uniform(avoid, max_start)

        sub_path = self._safe_path(subs)
        vf = (
            f"[0:v]crop=ih*9/16:ih,scale=1080:1920,"
            f"ass={sub_path}[vout]"
        )
        af = "[1:a]loudnorm=I=-14:LRA=11:TP=-1.5[a]"

        print(f"  [Render] clip {start_time:.1f}s → {start_time + audio_dur:.1f}s")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(start_time), "-t", str(audio_dur + 1),
                "-i", str(footage),
                "-i", str(audio),
                "-filter_complex", f"{vf};{af}",
                "-map", "[vout]", "-map", "[a]",
                "-c:v", "libx264", "-crf", "19", "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                "-shortest",
                str(output),
            ],
            check=True,
        )
        print(f"\n  Done! → {output}")


# ── PRODUCER ──────────────────────────────────────────────────────────────────

class Producer:
    """OODA-phase orchestrator with parallel asset acquisition."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        api_key  = os.getenv("ELEVENLABS_API_KEY", "")
        if not api_key:
            sys.exit(
                "ELEVENLABS_API_KEY not set.\n"
                "Add it to .env  OR  run:  setx ELEVENLABS_API_KEY your_key"
            )
        self.tts      = TTSEngine(api_key, cfg.voice_id)
        self.whisper  = WhisperEngine(cfg.whisper_model)
        self.subs     = SubtitleEngine(cfg.font_size, cfg.words_per_sub)
        self.footage  = FootageEngine(cfg.url, TEMP / "minecraft.mp4")
        self.renderer = Renderer(cfg)

    @staticmethod
    def _phase(name: str) -> None:
        print(f"\n{'=' * 52}\n  {name}\n{'=' * 52}")

    def _tts_job(self, text: str, path: Path, done: threading.Event) -> None:
        try:
            self.tts.generate(text, path)
        finally:
            done.set()

    def _dl_job(self, done: threading.Event) -> None:
        try:
            self.footage.ensure()
        finally:
            done.set()

    def run(self) -> None:
        TEMP.mkdir(exist_ok=True)

        full_text  = f"{self.cfg.title}. {self.cfg.story}"
        audio_path = TEMP / "voiceover.mp3"
        subs_path  = TEMP / "subtitles.ass"
        mc_path    = TEMP / "minecraft.mp4"

        # OBSERVE ── parallel TTS + footage download ──────────────────────────
        self._phase("OBSERVE  Acquiring Assets (parallel)")
        tts_done = threading.Event()
        dl_done  = threading.Event()
        t1 = threading.Thread(
            target=self._tts_job, args=(full_text, audio_path, tts_done), daemon=True
        )
        t2 = threading.Thread(
            target=self._dl_job, args=(dl_done,), daemon=True
        )
        t1.start(); t2.start()
        t1.join();  t2.join()

        # ORIENT ── Whisper word-level timing ─────────────────────────────────
        self._phase("ORIENT  Whisper Caption Sync")
        cues = self.whisper.transcribe(audio_path)
        if not cues:
            sys.exit("[Whisper] No word cues returned — is the audio file valid?")

        # DECIDE ── build subtitle cards ───────────────────────────────────────
        self._phase("DECIDE  Building Subtitles")
        self.subs.build(cues, subs_path)

        # ACT ── render ────────────────────────────────────────────────────────
        self._phase("ACT  Rendering Final Video")
        self.renderer.render(mc_path, audio_path, subs_path, Path(self.cfg.output))


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

def _parse_args() -> Config:
    p = argparse.ArgumentParser(
        description="Elite Minecraft Shorts Producer with Whisper caption sync"
    )
    p.add_argument("--story",         default=DEFAULT_STORY,  help="Story text")
    p.add_argument("--title",         default=DEFAULT_TITLE,  help="Story title")
    p.add_argument("--voice",         default=DEFAULT_VOICE,  help="ElevenLabs voice ID")
    p.add_argument("--url",           default=DEFAULT_URL,    help="Minecraft footage URL")
    p.add_argument("--output",        default=DEFAULT_OUT,    help="Output file path")
    p.add_argument("--font-size",     type=int, default=13,   help="ASS font size")
    p.add_argument("--words",         type=int, default=3,    help="Words per subtitle card")
    p.add_argument("--whisper-model", default="base",
                   choices=["tiny", "base", "small", "medium", "large"],
                   help="Whisper model (larger = slower + more accurate)")
    args = p.parse_args()
    return Config(
        story=args.story,
        title=args.title,
        voice_id=args.voice,
        url=args.url,
        output=args.output,
        font_size=args.font_size,
        words_per_sub=args.words,
        whisper_model=args.whisper_model,
    )


# ── PROGRAMMATIC ENTRY POINT (used by OODA act.py) ───────────────────────────

def make_video(
    story: str,
    title: str,
    output: str,
    voice_id: str = DEFAULT_VOICE,
    url: str = DEFAULT_URL,
    whisper_model: str = "base",
) -> str:
    """
    Callable from other modules — no argparse, no sys.argv.
    Returns output path on success, raises on failure.
    """
    cfg = Config(
        story=story,
        title=title,
        voice_id=voice_id,
        url=url,
        output=output,
        whisper_model=whisper_model,
    )
    Producer(cfg).run()
    return output


if __name__ == "__main__":
    Producer(_parse_args()).run()
