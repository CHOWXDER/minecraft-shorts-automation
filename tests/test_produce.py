"""
TDD test suite for produce.py
RED → GREEN → REFACTOR

Covers: SubtitleEngine, TTSEngine cache, Renderer path safety,
        WordCue integrity, Config defaults, emoji injection.
"""

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── import target module ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from produce import (
    ANIMATIONS,
    COLORS,
    EMOJI_MAP,
    Config,
    Renderer,
    SubtitleEngine,
    TTSEngine,
    WordCue,
    make_video,
)


# ══════════════════════════════════════════════════════════════════════════════
# WordCue
# ══════════════════════════════════════════════════════════════════════════════

class TestWordCue:
    def test_fields_stored(self):
        cue = WordCue(start=1.0, end=2.5, text="hello")
        assert cue.start == 1.0
        assert cue.end == 2.5
        assert cue.text == "hello"

    def test_start_before_end(self):
        cue = WordCue(0.0, 1.0, "word")
        assert cue.start < cue.end

    def test_zero_duration_allowed(self):
        # edge case: some TTS engines emit zero-duration words
        cue = WordCue(1.0, 1.0, "hmm")
        assert cue.start == cue.end


# ══════════════════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_defaults(self):
        cfg = Config(story="s", title="t", voice_id="v", url="u", output="o")
        assert cfg.font_size == 13
        assert cfg.words_per_sub == 3
        assert cfg.avoid_edge_secs == 60
        assert cfg.whisper_model == "base"

    def test_custom_values(self):
        cfg = Config("s", "t", "v", "u", "o", font_size=20, words_per_sub=5)
        assert cfg.font_size == 20
        assert cfg.words_per_sub == 5


# ══════════════════════════════════════════════════════════════════════════════
# SubtitleEngine — timing
# ══════════════════════════════════════════════════════════════════════════════

class TestAssTime:
    def _t(self, secs):
        return SubtitleEngine._ass_time(secs)

    def test_zero(self):
        assert self._t(0.0) == "0:00:00.00"

    def test_one_second(self):
        assert self._t(1.0) == "0:00:01.00"

    def test_one_minute(self):
        assert self._t(60.0) == "0:01:00.00"

    def test_one_hour(self):
        assert self._t(3600.0) == "1:00:00.00"

    def test_centiseconds(self):
        assert self._t(1.5) == "0:00:01.50"

    def test_complex(self):
        # 1h 2m 3.45s
        assert self._t(3723.45) == "1:02:03.45"

    def test_rounding(self):
        # 0.999 → should round centiseconds to 100 (i.e. 1.00)
        result = self._t(0.999)
        assert result in ("0:00:01.00", "0:00:00.99", "0:00:00.100")


# ══════════════════════════════════════════════════════════════════════════════
# SubtitleEngine — animation tags
# ══════════════════════════════════════════════════════════════════════════════

class TestAnimTags:
    def _a(self, style):
        return SubtitleEngine._anim_tags(style)

    def test_pop_has_fscx(self):
        assert "\\fscx" in self._a("pop")

    def test_bounce_has_two_t_blocks(self):
        tag = self._a("bounce")
        assert tag.count("\\t(") == 2

    def test_zoom_starts_small(self):
        # zoom starts at fscx40
        assert "\\fscx40" in self._a("zoom")

    def test_slam_starts_large(self):
        # slam starts at fscx160
        assert "\\fscx160" in self._a("slam")

    def test_unknown_style_returns_empty(self):
        assert self._a("unknown") == ""

    def test_all_animations_covered(self):
        for anim in ANIMATIONS:
            tag = self._a(anim)
            assert tag != "", f"animation '{anim}' returned empty tag"


# ══════════════════════════════════════════════════════════════════════════════
# SubtitleEngine — emoji injection
# ══════════════════════════════════════════════════════════════════════════════

class TestInjectEmoji:
    def _e(self, word):
        return SubtitleEngine._inject_emoji(word)

    def test_known_word_gets_emoji(self):
        result = self._e("food")
        assert "🍕" in result

    def test_known_word_with_punctuation(self):
        result = self._e("food.")
        assert "🍕" in result

    def test_unknown_word_unchanged(self):
        assert self._e("xylophone") == "xylophone"

    def test_case_insensitive(self):
        result = self._e("FOOD")
        # EMOJI_MAP keys are lowercase — lookup strips and lowercases
        # "FOOD".lower().rstrip() = "food" → should match
        assert "🍕" in result

    def test_emoji_appended_not_prepended(self):
        result = self._e("food")
        assert result.startswith("food")


# ══════════════════════════════════════════════════════════════════════════════
# SubtitleEngine — build()
# ══════════════════════════════════════════════════════════════════════════════

class TestSubtitleBuild:
    def _make_cues(self, n=6):
        return [WordCue(i * 0.5, i * 0.5 + 0.4, f"word{i}") for i in range(n)]

    def test_creates_file(self, tmp_path):
        eng  = SubtitleEngine()
        path = tmp_path / "subs.ass"
        eng.build(self._make_cues(), path)
        assert path.exists()

    def test_has_script_info(self, tmp_path):
        eng  = SubtitleEngine()
        path = tmp_path / "subs.ass"
        eng.build(self._make_cues(), path)
        content = path.read_text()
        assert "[Script Info]" in content

    def test_has_events_section(self, tmp_path):
        eng  = SubtitleEngine()
        path = tmp_path / "subs.ass"
        eng.build(self._make_cues(), path)
        assert "[Events]" in path.read_text()

    def test_correct_card_count(self, tmp_path):
        eng  = SubtitleEngine(words_per_sub=3)
        path = tmp_path / "subs.ass"
        cues = self._make_cues(9)   # 9 words ÷ 3 = 3 cards
        eng.build(cues, path)
        dialogues = [l for l in path.read_text().splitlines() if l.startswith("Dialogue:")]
        assert len(dialogues) == 3

    def test_first_word_capitalised(self, tmp_path):
        eng  = SubtitleEngine()
        path = tmp_path / "subs.ass"
        cues = [WordCue(0, 1, "hello"), WordCue(1, 2, "world"), WordCue(2, 3, "foo")]
        eng.build(cues, path)
        content = path.read_text()
        # first card should contain HELLO (capitalised then upper-cased)
        assert "HELLO" in content

    def test_colour_cycles(self, tmp_path):
        eng  = SubtitleEngine(words_per_sub=1)
        path = tmp_path / "subs.ass"
        cues = self._make_cues(len(COLORS) + 1)  # more cards than colors
        eng.build(cues, path)
        content = path.read_text()
        # first color should appear at least twice (cycling)
        first_color = COLORS[0].replace("&H", "")
        assert content.count(first_color) >= 2

    def test_font_size_in_style(self, tmp_path):
        eng  = SubtitleEngine(font_size=42)
        path = tmp_path / "subs.ass"
        eng.build(self._make_cues(), path)
        assert ",42," in path.read_text()


# ══════════════════════════════════════════════════════════════════════════════
# TTSEngine — cache
# ══════════════════════════════════════════════════════════════════════════════

class TestTTSCache:
    def test_cache_key_deterministic(self):
        eng = TTSEngine("key", "voice")
        assert eng._cache_key("hello") == eng._cache_key("hello")

    def test_cache_key_differs_by_text(self):
        eng = TTSEngine("key", "voice")
        assert eng._cache_key("hello") != eng._cache_key("world")

    def test_cache_key_differs_by_voice(self):
        e1 = TTSEngine("key", "voice1")
        e2 = TTSEngine("key", "voice2")
        assert e1._cache_key("hello") != e2._cache_key("hello")

    def test_cache_hit_copies_file(self, tmp_path):
        eng      = TTSEngine("", "voice")
        # Pre-populate cache
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        key      = eng._cache_key("test text")
        src      = cache_dir / f"{key}.mp3"
        src.write_bytes(b"fake-audio")

        out = tmp_path / "out.mp3"

        # Patch CACHE to point to tmp
        with patch("produce.CACHE", cache_dir):
            eng.generate("test text", out)

        assert out.exists()
        assert out.read_bytes() == b"fake-audio"


# ══════════════════════════════════════════════════════════════════════════════
# Renderer — _safe_path (the Windows FFmpeg bug)
# ══════════════════════════════════════════════════════════════════════════════

class TestSafePath:
    def test_relative_path_no_colon(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sub_file = tmp_path / "temp" / "subtitles.ass"
        sub_file.parent.mkdir()
        sub_file.touch()

        cfg = Config("s", "t", "v", "u", "o")
        r   = Renderer(cfg)
        result = r._safe_path(sub_file)

        assert ":" not in result, f"Colon found in path: {result}"
        assert "\\" not in result, f"Backslash found in path: {result}"

    def test_forward_slashes_only(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        sub_file = tmp_path / "temp" / "subtitles.ass"
        sub_file.parent.mkdir()
        sub_file.touch()

        cfg = Config("s", "t", "v", "u", "o")
        r   = Renderer(cfg)
        result = r._safe_path(sub_file)
        assert "/" in result or result == "temp/subtitles.ass"

    def test_outside_cwd_escapes_colon(self, tmp_path, monkeypatch):
        other = tmp_path / "other"
        other.mkdir()
        monkeypatch.chdir(other)
        sub_file = tmp_path / "subtitles.ass"
        sub_file.touch()

        cfg = Config("s", "t", "v", "u", "o")
        r   = Renderer(cfg)
        result = r._safe_path(sub_file)
        # Outside cwd → absolute path with colon escaped as \:
        if ":" in str(sub_file.resolve()):
            assert "\\:" in result


# ══════════════════════════════════════════════════════════════════════════════
# make_video() — integration smoke test (mocked)
# ══════════════════════════════════════════════════════════════════════════════

class TestMakeVideoSmoke:
    def test_returns_output_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("produce.Producer") as MockProducer:
            mock_instance = MagicMock()
            MockProducer.return_value = mock_instance

            result = make_video(
                story="A story.",
                title="A title",
                output="out.mp4",
            )

        assert result == "out.mp4"
        MockProducer.assert_called_once()
        mock_instance.run.assert_called_once()

    def test_config_passed_correctly(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        captured = {}

        with patch("produce.Producer") as MockProducer:
            def capture(cfg):
                captured["cfg"] = cfg
                m = MagicMock()
                return m
            MockProducer.side_effect = capture
            make_video("my story", "my title", "output.mp4",
                       voice_id="voice123", whisper_model="small")

        cfg = captured["cfg"]
        assert cfg.story == "my story"
        assert cfg.title == "my title"
        assert cfg.voice_id == "voice123"
        assert cfg.whisper_model == "small"
        assert cfg.output == "output.mp4"
