"""
TDD test suite for the free/local pipeline components.
Covers: anonymous Reddit scraper, Ollama orient (mocked), edge_tts default.
"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ══════════════════════════════════════════════════════════════════════════════
# RedditScraper — anonymous JSON scraping
# ══════════════════════════════════════════════════════════════════════════════

from reddit_scraper import RedditScraper


class TestRedditScraperAnonymous:
    def _fake_response(self, posts: list[dict]):
        """Build a fake Reddit JSON response."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "data": {
                "children": [{"data": p} for p in posts]
            }
        }
        resp.raise_for_status.return_value = None
        return resp

    def _post(self, score=1000, title="Test post", selftext="Body text"):
        return {
            "title": title,
            "selftext": selftext,
            "score": score,
            "num_comments": 50,
            "url": "https://reddit.com/r/Minecraft/comments/abc",
            "author": "testuser",
            "created_utc": 1700000000.0,
            "subreddit": "Minecraft",
            "upvote_ratio": 0.95,
            "is_self": True,
        }

    def test_no_praw_import(self):
        """reddit_scraper must not import praw at all."""
        import reddit_scraper
        import ast, inspect
        src = inspect.getsource(reddit_scraper)
        assert "praw" not in src, "praw found in reddit_scraper.py — must be removed"

    def test_get_top_posts_parses_json(self):
        scraper = RedditScraper()
        fake    = self._fake_response([self._post(score=800)])

        with patch.object(scraper._session, "get", return_value=fake):
            with patch("time.sleep"):   # skip rate-limit delay
                posts = scraper.get_top_posts("Minecraft", limit=5)

        assert len(posts) == 1
        assert posts[0]["score"] == 800
        assert posts[0]["title"] == "Test post"

    def test_get_top_posts_returns_empty_on_http_error(self):
        scraper = RedditScraper()
        with patch.object(scraper._session, "get", side_effect=Exception("network error")):
            posts = scraper.get_top_posts("Minecraft")
        assert posts == []

    def test_filter_quality_posts_min_score(self):
        scraper = RedditScraper()
        posts   = [
            self._post(score=200),
            self._post(score=600),
            self._post(score=1500),
        ]
        result = scraper.filter_quality_posts(posts, min_score=500)
        assert len(result) == 2
        assert all(p["score"] >= 500 for p in result)

    def test_filter_keeps_all_above_threshold(self):
        scraper = RedditScraper()
        posts   = [self._post(score=1000), self._post(score=2000)]
        assert scraper.filter_quality_posts(posts, min_score=100) == posts

    def test_url_contains_top_and_time_filter(self):
        scraper = RedditScraper()
        captured_url = []

        def fake_get(url, **kwargs):
            captured_url.append(url)
            return self._fake_response([])

        with patch.object(scraper._session, "get", side_effect=fake_get):
            with patch("time.sleep"):
                scraper.get_top_posts("Minecraft", limit=10, time_filter="week")

        assert len(captured_url) == 1
        assert "top.json" in captured_url[0]
        assert "t=week" in captured_url[0]
        assert "limit=10" in captured_url[0]

    def test_no_api_key_env_var_needed(self):
        """Instantiating RedditScraper must not raise even with no env vars set."""
        with patch.dict("os.environ", {}, clear=True):
            scraper = RedditScraper()
        assert scraper is not None


# ══════════════════════════════════════════════════════════════════════════════
# Orient — Ollama integration (mocked)
# ══════════════════════════════════════════════════════════════════════════════

from observe import Signal


def _make_signal(title="Test", score=1000, velocity=50.0) -> Signal:
    return Signal(
        source="reddit",
        content_id="abc123",
        title=title,
        body="Some body text",
        score=score,
        num_comments=100,
        velocity=velocity,
        comment_velocity=5.0,
        engagement_rate=0.1,
        score_delta=100,
        momentum=velocity,
        created_utc=1700000000.0,
        url="https://reddit.com/test",
        author="user",
        subreddit="Minecraft",
    )


class MockConfig:
    pass


class TestOrientOllama:
    def test_no_anthropic_import(self):
        """orient.py must not import anthropic."""
        import orient
        import inspect
        src = inspect.getsource(orient)
        assert "anthropic" not in src, "anthropic found in orient.py — must be removed"

    def test_heuristic_fallback_always_works(self):
        from orient import Orient
        o = Orient(MockConfig())
        sig    = _make_signal(score=5000, velocity=300.0)
        result = o._heuristic_fallback(sig)
        assert result.composite_score >= 0
        assert result.scored_by_ai is False
        assert result.suggested_title == sig.title[:60]

    def test_heuristic_viability_high_score(self):
        from orient import Orient, VIABILITY_THRESHOLD
        o   = Orient(MockConfig())
        sig = _make_signal(score=10000, velocity=500.0)
        r   = o._heuristic_fallback(sig)
        assert r.is_viable == (r.composite_score >= VIABILITY_THRESHOLD)

    def test_analyse_empty_signals(self):
        from orient import Orient
        o = Orient(MockConfig())
        assert o.analyse([]) == []

    def test_analyse_uses_heuristic_when_ollama_down(self):
        from orient import Orient
        o = Orient(MockConfig())
        o._ollama_available = False   # force heuristic path

        sigs    = [_make_signal(), _make_signal(title="Second")]
        results = o.analyse(sigs)

        assert len(results) == 2
        assert all(not r.scored_by_ai for r in results)

    def test_analyse_sorted_by_composite_score(self):
        from orient import Orient
        o = Orient(MockConfig())
        o._ollama_available = False

        sigs = [
            _make_signal(score=100,   velocity=1.0),
            _make_signal(score=10000, velocity=500.0),
        ]
        results = o.analyse(sigs)
        assert results[0].composite_score >= results[1].composite_score

    def test_ollama_batch_parses_response(self):
        """Mock Ollama HTTP call and verify Assessment is built correctly."""
        from orient import Orient, VIABILITY_THRESHOLD
        o = Orient(MockConfig())

        fake_result = [{
            "viral_potential":    80.0,
            "narrative_strength": 75.0,
            "title_quality":      70.0,
            "audience_fit":       85.0,
            "suggested_title":    "Epic Minecraft Story",
            "suggested_tags":     ["Minecraft", "Shorts", "Story"],
            "reasoning":          "Strong narrative arc.",
            "is_viable":          True,
        }]
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {"response": json.dumps(fake_result)}

        with patch("requests.post", return_value=fake_resp):
            sig     = _make_signal()
            results = o._ollama_batch([sig])

        assert len(results) == 1
        r = results[0]
        assert r.scored_by_ai is True
        assert r.suggested_title == "Epic Minecraft Story"
        assert r.viral_potential == 80.0
        # composite = 0.35*80 + 0.25*75 + 0.20*70 + 0.20*85
        expected = round(0.35 * 80 + 0.25 * 75 + 0.20 * 70 + 0.20 * 85, 1)
        assert r.composite_score == expected

    def test_synthesise_trends_returns_dict(self):
        from orient import Orient, Assessment
        o    = Orient(MockConfig())
        sig  = _make_signal()
        a    = o._heuristic_fallback(sig)
        a.is_viable = True
        trends = o.synthesise_trends([a])
        assert "cycle_viable" in trends
        assert "avg_composite_score" in trends
        assert "trending_tags" in trends

    def test_probe_ollama_marks_unavailable_on_connection_error(self):
        from orient import Orient
        o = Orient(MockConfig())
        with patch("requests.get", side_effect=Exception("connection refused")):
            result = o._probe_ollama()
        assert result is False
        assert o._ollama_available is False

    def test_probe_ollama_marks_available_on_200(self):
        from orient import Orient
        o    = Orient(MockConfig())
        resp = MagicMock()
        resp.status_code = 200
        with patch("requests.get", return_value=resp):
            result = o._probe_ollama()
        assert result is True
        assert o._ollama_available is True


# ══════════════════════════════════════════════════════════════════════════════
# edge_tts default in TTSEngine
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeTTSDefault:
    def test_no_api_key_goes_to_edge_tts(self, tmp_path, monkeypatch):
        """With no API key, TTSEngine must call edge_tts, not ElevenLabs."""
        from produce import TTSEngine, CACHE
        monkeypatch.setattr("produce.CACHE", tmp_path / "cache")

        edge_called = []

        def fake_edge(self, text, path):
            edge_called.append(True)
            path.write_bytes(b"fake-audio")

        with patch("produce.TTSEngine._edge_tts", fake_edge):
            eng = TTSEngine(api_key="", voice_id="any")
            eng.generate("hello", tmp_path / "out.mp3")

        assert edge_called, "edge_tts was not called despite no API key"

    def test_edge_tts_is_fallback_voice_constant(self):
        from produce import TTSEngine
        assert "Neural" in TTSEngine.FALLBACK_VOICE   # Microsoft neural voice
        assert "en-US" in TTSEngine.FALLBACK_VOICE
