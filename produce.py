#!/usr/bin/env python3
"""
produce.py — Free/Local Shorts Production Pipeline
edge_tts → Whisper word-sync → ASS subtitles → FFmpeg render
No API keys required.
"""

import asyncio
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

TEMP  = Path("temp")
CACHE = TEMP / "cache"

DEFAULT_URL     = "https://www.youtube.com/watch?v=85z7jqGAGcc"
DEFAULT_GTA_URL = ""

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
ANIMATIONS = ["pop", "bounce", "zoom", "slam"]

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


# ── DATA ──────────────────────────────────────────────────────────────────────

@dataclass
class Config:
    story:          str
    title:          str
    voice_id:       str  = ""    # optional — kept for API compat (edge_tts ignores it)
    url:            str  = DEFAULT_URL
    gta_url:        str  = DEFAULT_GTA_URL
    output:         str  = "final_video.mp4"
    font_size:      int  = 90
    words_per_sub:  int  = 2
    avoid_edge_secs: int = 60
    whisper_model:  str  = "base"
    max_duration:   int  = 58   # hard cap — YouTube Shorts must be ≤60s

# Alias so ooda / act code can also use VideoConfig name internally
VideoConfig = Config


# ── TTS ───────────────────────────────────────────────────────────────────────

class TTSEngine:
    FALLBACK_VOICE    = "en-US-ChristopherNeural"   # edge_tts
    ELEVENLABS_VOICE  = "pNInz6obpgDQGcFmaJgB"      # Adam — deep male voice

    def __init__(self, api_key: str = "", voice_id: str = ""):
        self.api_key  = api_key
        self.voice_id = voice_id or self.ELEVENLABS_VOICE

    def _cache_key(self, text: str) -> str:
        import hashlib
        return hashlib.md5(f"{text}:{self.voice_id}:v3".encode()).hexdigest()

    def generate(self, text: str, audio_path: Path) -> None:
        import shutil
        CACHE.mkdir(parents=True, exist_ok=True)
        key       = self._cache_key(text)
        cache_mp3 = CACHE / f"{key}.mp3"

        if cache_mp3.exists():
            print("  [TTS] cache hit")
            shutil.copy(cache_mp3, audio_path)
            return

        # Optional ElevenLabs if key provided — direct REST API, no SDK
        if self.api_key:
            import requests as _req, time as _time
            print("  [TTS] calling ElevenLabs…")
            for attempt in range(3):
                try:
                    url  = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
                    resp = _req.post(url,
                        headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                        json={"text": text, "model_id": "eleven_multilingual_v2",
                              "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
                        timeout=60,
                    )
                    resp.raise_for_status()
                    audio_path.write_bytes(resp.content)
                    cache_mp3.write_bytes(resp.content)
                    print("  [TTS] ElevenLabs audio written")
                    return
                except Exception as exc:
                    wait = 2 ** attempt
                    print(f"  [TTS] attempt {attempt+1} failed: {exc!s:.120} — retry in {wait}s")
                    _time.sleep(wait)
            print("  [TTS] ElevenLabs failed — falling back to edge_tts")

        self._edge_tts(text, audio_path)
        shutil.copy(audio_path, cache_mp3)

    def _edge_tts(self, text: str, path: Path) -> None:
        try:
            import edge_tts
        except ImportError:
            sys.exit("edge-tts not installed. Run: pip install edge-tts")

        async def _run():
            comm = edge_tts.Communicate(text, voice=self.FALLBACK_VOICE)
            await comm.save(str(path))

        print(f"  [TTS] edge_tts → {self.FALLBACK_VOICE}")
        asyncio.run(_run())
        print("  [TTS] done")


# ── SUBTITLE ENGINE ───────────────────────────────────────────────────────────

@dataclass
class WordCue:
    start: float
    end:   float
    text:  str


class SubtitleEngine:
    # Clean, modern Shorts style — white text, thick black border, subtle shadow
    ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial Black,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H96000000,1,0,0,0,100,100,4,0,1,7,2,5,80,80,320,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

    # Flanking emojis — pick based on card index for variety
    SIDE_EMOJIS = [
        ("😤", "😤"), ("🔥", "🔥"), ("💀", "💀"), ("😱", "😱"),
        ("⚡", "⚡"), ("💥", "💥"), ("👀", "👀"), ("😭", "😭"),
        ("🚨", "🚨"), ("😤", "💀"), ("🔥", "😱"), ("⚡", "💥"),
    ]

    def __init__(self, font_size: int = 90, words_per_sub: int = 2):
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
        if style == "pop":    return r"{\fscx130\fscy130\t(0,80,\fscx100\fscy100)}"
        if style == "bounce": return r"{\fscx80\fscy80\t(0,60,\fscx110\fscy110)\t(60,120,\fscx100\fscy100)}"
        if style == "zoom":   return r"{\fscx30\fscy30\t(0,120,\fscx100\fscy100)}"
        if style == "slam":   return r"{\fscx170\fscy170\t(0,70,\fscx95\fscy95)\t(70,130,\fscx100\fscy100)}"
        return ""

    @staticmethod
    def _inject_emoji(word: str) -> str:
        clean = word.lower().rstrip(".,!?;:")
        emoji = EMOJI_MAP.get(clean, "")
        return f"{word}{emoji}" if emoji else word

    def build(self, cues: list[WordCue], output_path: Path) -> None:
        header    = self.ASS_HEADER.format(fontsize=self.font_size)
        events    = []
        color_idx = 0

        for i in range(0, len(cues), self.words_per_sub):
            chunk = cues[i:i + self.words_per_sub]
            start = self._ass_time(chunk[0].start)
            end   = self._ass_time(chunk[-1].end)

            words = [c.text for c in chunk]
            words[0] = words[0].capitalize()
            words = [self._inject_emoji(w) for w in words]
            text  = " ".join(words).upper()

            # Flanking emojis on each side
            left_e, right_e = self.SIDE_EMOJIS[color_idx % len(self.SIDE_EMOJIS)]

            color    = COLORS[color_idx % len(COLORS)]
            anim     = self._anim_tags(random.choice(ANIMATIONS))
            color_tag = f"{{\\c{color}}}"

            # Smaller emoji flanks — 60% of main font size
            emoji_size = int(self.font_size * 0.6)
            left_tag  = f"{{\\fs{emoji_size}\\c&H00FFFFFF&}}{left_e} "
            right_tag = f" {{\\fs{emoji_size}\\c&H00FFFFFF&}}{right_e}"

            line = (
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,"
                f"{anim}{left_tag}{{\\fs{self.font_size}}}{color_tag}{text}{right_tag}"
            )
            events.append(line)
            color_idx += 1

        output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
        print(f"  [Subs] {len(events)} cards → {output_path.name}")


# ── WHISPER ───────────────────────────────────────────────────────────────────

class WhisperEngine:
    def __init__(self, model_name: str = "base"):
        self.model_name = model_name

    def transcribe(self, audio_path: Path) -> list[WordCue]:
        try:
            import whisper
        except ImportError:
            sys.exit("openai-whisper not installed. Run: pip install openai-whisper")

        print(f"  [Whisper] loading '{self.model_name}' model…")
        model  = whisper.load_model(self.model_name)
        result = model.transcribe(str(audio_path), word_timestamps=True, language="en")
        cues: list[WordCue] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                word = w.get("word", "").strip()
                if word:
                    cues.append(WordCue(float(w["start"]), float(w["end"]), word))
        print(f"  [Whisper] {len(cues)} word cues")
        return cues


# ── FOOTAGE ───────────────────────────────────────────────────────────────────

def ensure_footage(url: str, mc_path: Path) -> None:
    if mc_path.exists():
        print(f"  [Footage] using cached {mc_path.name}")
        return
    print(f"  [Footage] downloading {mc_path.name}…")
    subprocess.run(
        [sys.executable, "-m", "yt_dlp",
         "--cookies-from-browser", "firefox",
         "--js-runtimes", r"node:C:\Program Files\nodejs\node.exe",
         "-o", str(mc_path),
         "-f", "best[ext=mp4]/best",
         url],
        check=True,
    )


# ── RENDERER ──────────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, cfg: Config = None):
        self.cfg = cfg or Config(story="", title="", output="")

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
        try:
            return str(path.resolve().relative_to(Path.cwd())).replace("\\", "/")
        except ValueError:
            return str(path.resolve()).replace("\\", "/").replace(":", "\\:")

    @staticmethod
    def _detect_video_codec() -> str:
        try:
            subprocess.run(
                ["ffmpeg", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
                 "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True, check=True,
            )
            print("  [Render] GPU detected → h264_nvenc")
            return "h264_nvenc"
        except Exception:
            print("  [Render] No GPU → libx264")
            return "libx264"

    def render(self, footage: Path, audio: Path, subs: Path, output: Path,
               gta: Path | None = None) -> None:
        audio_dur  = min(self._probe_duration(audio), self.cfg.max_duration)
        mc_dur     = self._probe_duration(footage)
        avoid      = min(self.cfg.avoid_edge_secs, mc_dur * 0.1)
        max_start  = max(avoid, mc_dur - audio_dur - avoid)
        start_time = random.uniform(avoid, max_start)
        print(f"  [Render] capping at {audio_dur:.0f}s")

        codec    = self._detect_video_codec()
        sub_path = self._safe_path(subs)

        if codec == "h264_nvenc":
            codec_flags = ["-c:v", "h264_nvenc", "-rc", "vbr", "-cq", "19", "-preset", "p4", "-b:v", "0"]
        else:
            codec_flags = ["-c:v", "libx264", "-crf", "19", "-preset", "medium"]

        split_screen = gta is not None and gta.exists()

        if split_screen:
            # GTA start at a random point too
            gta_dur   = self._probe_duration(gta)
            gta_avoid = min(self.cfg.avoid_edge_secs, gta_dur * 0.1)
            gta_start = random.uniform(gta_avoid, max(gta_avoid, gta_dur - audio_dur - gta_avoid))

            # Top half: Minecraft (960px), Bottom half: GTA (960px) → 1080×1920
            # scale to fill then crop — avoids squeezing regardless of source ratio
            vf = (
                f"[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[top];"
                f"[2:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[bot];"
                f"[top][bot]vstack=inputs=2,"
                f"eq=saturation=1.5:contrast=1.15:brightness=0.04,"
                f"vignette=PI/4,"
                f"ass={sub_path},"
                f"drawtext=text='FOLLOW FOR MORE ↑':fontcolor=white:fontsize=50:fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
                f"x=(w-text_w)/2:y=h-120:"
                f"enable='gte(t,{audio_dur-3})':"
                f"box=1:boxcolor=black@0.5:boxborderw=10[vout]"
            )
            af  = "[1:a]loudnorm=I=-14:LRA=11:TP=-1.5[a]"
            inputs = [
                "-ss", str(start_time), "-t", str(audio_dur + 1), "-i", str(footage),
                "-i", str(audio),
                "-ss", str(gta_start), "-t", str(audio_dur + 1), "-i", str(gta),
            ]
            print(f"  [Render] split-screen ON  mc={start_time:.1f}s  gta={gta_start:.1f}s  codec={codec}")
        else:
            vf = (
                f"[0:v]crop=ih*9/16:ih,scale=1080:1920,"
                f"eq=saturation=1.5:contrast=1.15:brightness=0.04,"
                f"vignette=PI/4,"
                f"ass={sub_path},"
                f"drawtext=text='FOLLOW FOR MORE ↑':fontcolor=white:fontsize=50:fontfile='C\\:/Windows/Fonts/arialbd.ttf':"
                f"x=(w-text_w)/2:y=h-120:"
                f"enable='gte(t,{audio_dur-3})':"
                f"box=1:boxcolor=black@0.5:boxborderw=10[vout]"
            )
            af  = "[1:a]loudnorm=I=-14:LRA=11:TP=-1.5[a]"
            inputs = [
                "-ss", str(start_time), "-t", str(audio_dur + 1), "-i", str(footage),
                "-i", str(audio),
            ]
            print(f"  [Render] {start_time:.1f}s → {start_time+audio_dur:.1f}s  codec={codec}")

        try:
            subprocess.run(
                ["ffmpeg", "-y", *inputs,
                 "-filter_complex", f"{vf};{af}",
                 "-map", "[vout]", "-map", "[a]",
                 *codec_flags,
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                 "-shortest", str(output)],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode(errors="replace").strip()
            relevant = next(
                (ln for ln in reversed(stderr.splitlines()) if ln.strip()),
                stderr[-300:] if stderr else "no stderr",
            )
            raise RuntimeError(
                f"FFmpeg render failed (exit {exc.returncode}).\n"
                f"  Codec   : {codec}\n"
                f"  Sub path: {sub_path}\n"
                f"  Error   : {relevant}"
            ) from exc

        print(f"  [Render] done → {output}")


# ── PRODUCER (orchestrates all phases) ───────────────────────────────────────

class Producer:
    def __init__(self, cfg: Config):
        self.cfg      = cfg
        api_key       = os.getenv("ELEVENLABS_API_KEY", "")
        self.tts      = TTSEngine(api_key, cfg.voice_id)
        self.whisper  = WhisperEngine(cfg.whisper_model)
        self.subs     = SubtitleEngine(cfg.font_size, cfg.words_per_sub)
        self.renderer = Renderer(cfg)

    def run(self) -> None:
        import threading
        TEMP.mkdir(exist_ok=True)
        CACHE.mkdir(exist_ok=True)

        full_text  = self.cfg.story  # skip title prefix — jump straight into drama
        audio_path = TEMP / "voiceover.mp3"
        subs_path  = TEMP / "subtitles.ass"
        # Pick a random clip from temp/minecraft/ folder, fall back to temp/minecraft.mp4
        mc_clips = sorted((TEMP / "minecraft").glob("*.mp4")) if (TEMP / "minecraft").exists() else []
        mc_path  = random.choice(mc_clips) if mc_clips else TEMP / "minecraft.mp4"

        gta_clips = sorted((TEMP / "gta").glob("*.mp4")) if (TEMP / "gta").exists() else []
        gta_path  = random.choice(gta_clips) if gta_clips else TEMP / "gta.mp4"

        # Parallel: TTS + footage downloads
        print("\n[1/4] Acquiring assets (parallel TTS + footage)…")
        if mc_clips:
            print(f"  [Footage] picked {mc_path.name} from {len(mc_clips)} minecraft clips")
        if gta_clips:
            print(f"  [Footage] picked {gta_path.name} from {len(gta_clips)} gta clips")
        tts_err = []
        dl_err  = []

        def _tts():
            try:
                self.tts.generate(full_text, audio_path)
            except Exception as e:
                tts_err.append(e)

        def _dl():
            try:
                if not mc_clips:
                    ensure_footage(self.cfg.url, mc_path)
                if self.cfg.gta_url and not gta_clips and not gta_path.exists():
                    ensure_footage(self.cfg.gta_url, gta_path)
            except Exception as e:
                dl_err.append(e)

        t1 = threading.Thread(target=_tts, daemon=True)
        t2 = threading.Thread(target=_dl,  daemon=True)
        t1.start(); t2.start()
        t1.join();  t2.join()

        if not audio_path.exists():
            sys.exit(f"[ERROR] Audio not created. {tts_err[0] if tts_err else 'Check TTS.'}")
        if not mc_path.exists():
            sys.exit(f"[ERROR] Footage missing. {dl_err[0] if dl_err else 'Place minecraft.mp4 in temp/.'}")

        print("\n[2/4] Whisper caption sync…")
        cues = self.whisper.transcribe(audio_path)
        if not cues:
            sys.exit("[ERROR] Whisper returned no word cues")

        print("\n[3/4] Building subtitles…")
        self.subs.build(cues, subs_path)

        gta = gta_path if gta_path.exists() else None
        if gta:
            print("  [Subs] adjusting margins for split-screen…")
            # Rewrite subtitle file with adjusted vertical margin for split screen
            content = subs_path.read_text(encoding="utf-8")
            # Move subtitles to center seam (MarginV 320 → 0 centers them at split line)
            content = content.replace(
                "Style: Default,Arial Black",
                "Style: Default,Arial Black"
            ).replace(",80,80,320,1", ",80,80,10,1")
            subs_path.write_text(content, encoding="utf-8")

        print("\n[4/4] Rendering…")
        self.renderer.render(mc_path, audio_path, subs_path, Path(self.cfg.output), gta=gta)
        print(f"\n  Done → {self.cfg.output}")


# ── PUBLIC ENTRY POINT ────────────────────────────────────────────────────────

def make_video(
    story:         str,
    title:         str,
    output:        str,
    voice_id:      str = "",
    url:           str = DEFAULT_URL,
    gta_url:       str = "",
    whisper_model: str = "base",
) -> str:
    """Called by ooda_loop.py — returns output path on success."""
    cfg = Config(
        story=story, title=title, voice_id=voice_id,
        url=url, gta_url=gta_url, output=output, whisper_model=whisper_model,
    )
    Producer(cfg).run()
    return output


# ── STANDALONE ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = make_video(
        story=(
            "So my roommate has been stealing my food for months. I labeled everything, "
            "talked to him twice, he still kept doing it. Last night I made a lasagna, "
            "came back and he ate half of it straight from the dish. I finally snapped "
            "and told him he has two weeks to find somewhere else to live. Now my other "
            "roommates are saying I overreacted. Am I the asshole?"
        ),
        title="AITA for kicking out my roommate over food?",
        output="final_video.mp4",
    )
    print(f"\nDone: {result}")
