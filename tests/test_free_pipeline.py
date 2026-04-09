"""
TDD tests for the free/local pipeline components.
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
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": {"children": [{"data": p} for p in posts]}}
        resp.raise_for_status.return_value = None
        return resp

    def _post(self, score=1000, title="Test post", selftext="Body"):
        return {
            "title": title, "selftext": selftext, "score": score,
            "num_comments": 50, "url": "https://reddit.com/r/Minecraft/abc",
            "author": "testuser", "created_utc": 1700000000.0,
            "subreddit": "Minecraft", "upvote_ratio": 0.95, "is_self": True,
        }

    def test_no_praw_import(self):
        import reddit_scraper, inspect
        assert "praw" not in inspect.getsource(reddit_scraper)

    def test_get_top_posts_parses_json(self):
        scraper = RedditScraper()
        fake    = self._fake_response([self._post(score=800)])
        with patch.object(scraper._session, "get", return_value=fake):
            with patch("time.sleep"):
                posts = scraper.get_top_posts("Minecraft")
        assert len(posts) == 1
        assert posts[0]["score"] == 800
        assert posts[0]["title"] == "Test post"

    def test_get_top_posts_uses_text_key(self):
        """Downstream orient.py expects key 'text', not 'selftext'."""
        scraper = RedditScraper()
        fake    = self._fake_response([self._post(selftext="The story body")])
        with patch.object(scraper._session, "get", return_value=fake):
            with patch("time.sleep"):
                posts = scraper.get_top_posts("Minecraft")
        assert "text" in posts[0]
        assert posts[0]["text"] == "The story body"

    def test_get_top_posts_returns_empty_on_http_error(self):
        scraper = RedditScraper()
        with patch.object(scraper._session, "get", side_effect=Exception("network error")):
            posts = scraper.get_top_posts("Minecraft")
        assert posts == []

    def test_url_contains_top_and_subreddit(self):
        scraper      = RedditScraper()
        captured_url = []

        def fake_get(url, **kwargs):
            captured_url.append(url)
            return self._fake_response([])

        with patch.object(scraper._session, "get", side_effect=fake_get):
            with patch("time.sleep"):
                scraper.get_top_posts("Minecraft")

        assert "top.json" in captured_url[0]
        assert "Minecraft" in captured_url[0]
        assert "t=day" in captured_url[0]

    def test_get_minecraft_stories_filters_min_score(self):
        scraper = RedditScraper()
        low  = self._post(score=100,  selftext="x" * 51)
        high = self._post(score=1000, selftext="x" * 51)

        with patch.object(scraper._session, "get",
                          return_value=self._fake_response([low, high])):
            with patch("time.sleep"):
                posts = scraper.get_minecraft_stories()

        assert all(p["score"] >= 500 for p in posts)

    def test_no_api_key_env_var_needed(self):
        with patch.dict("os.environ", {}, clear=True):
            scraper = RedditScraper()
        assert scraper is not None


# ══════════════════════════════════════════════════════════════════════════════
# Orient — simplified Ollama scoring (mocked)
# ══════════════════════════════════════════════════════════════════════════════

from orient import Orient


def _signal(title="Test", score=1000, text="A long story with details"):
    return {"title": title, "text": text, "score": score, "subreddit": "Minecraft"}


class TestOrientSimple:
    def test_no_anthropic_import(self):
        import orient, inspect
        assert "anthropic" not in inspect.getsource(orient)

    def test_analyse_empty_returns_empty(self):
        o = Orient()
        assert o.analyse([]) == []

    def test_analyse_returns_ai_score_key(self):
        o = Orient()
        o._ollama_available = False   # force heuristic

        results = o.analyse([_signal(score=5000)])
        assert len(results) == 1
        assert "ai_score" in results[0]

    def test_analyse_score_is_int_1_to_10(self):
        o = Orient()
        o._ollama_available = False

        results = o.analyse([_signal(score=5000)])
        score = results[0]["ai_score"]
        assert isinstance(score, int)
        assert 1 <= score <= 10

    def test_analyse_sorted_by_ai_score_descending(self):
        o = Orient()
        o._ollama_available = False

        sigs    = [_signal(score=100), _signal(score=10000)]
        results = o.analyse(sigs)
        assert results[0]["ai_score"] >= results[1]["ai_score"]

    def test_analyse_ollama_used_when_available(self):
        o   = Orient()
        o._ollama_available = True

        with patch("orient.query_ollama", return_value="8") as mock_q:
            results = o.analyse([_signal()])

        mock_q.assert_called()
        assert results[0]["ai_score"] == 8

    def test_ollama_score_regex_handles_various_formats(self):
        """Score extraction must handle '7', '7/10', 'Score: 9', '10'."""
        import re
        cases = [("7", 7), ("7/10", 7), ("Score: 9", 9), ("10", 10), ("I give it a 6.", 6)]
        for raw, expected in cases:
            match = re.search(r'\b([1-9]|10)\b', raw)
            assert match and int(match.group(1)) == expected, f"Failed for: {raw}"

    def test_heuristic_fallback_when_ollama_down(self):
        o = Orient()
        with patch("orient.is_running", return_value=False):
            o._ollama_available = None  # reset probe cache
            results = o.analyse([_signal(score=5000)])
        assert len(results) == 1
        assert 1 <= results[0]["ai_score"] <= 10

    def test_synthesise_trends_returns_dict(self):
        o       = Orient()
        o._ollama_available = False
        results = o.analyse([_signal(score=5000)])
        trends  = o.synthesise_trends(results)
        assert "cycle_viable" in trends
        assert "cycle_total"  in trends

    def test_probe_stores_result(self):
        o = Orient()
        with patch("orient.is_running", return_value=False):
            result = o._probe_ollama()
        assert result is False
        assert o._ollama_available is False

    def test_probe_true_when_ollama_up(self):
        o = Orient()
        with patch("orient.is_running", return_value=True):
            result = o._probe_ollama()
        assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# edge_tts default in TTSEngine
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeTTSDefault:
    def test_no_api_key_goes_to_edge_tts(self, tmp_path, monkeypatch):
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

    def test_fallback_voice_is_neural(self):
        from produce import TTSEngine
        assert "Neural" in TTSEngine.FALLBACK_VOICE
        assert "en-US"  in TTSEngine.FALLBACK_VOICE

    def test_cache_key_deterministic(self):
        from produce import TTSEngine
        eng = TTSEngine("", "voice")
        assert eng._cache_key("hello") == eng._cache_key("hello")

    def test_cache_key_differs_by_text(self):
        from produce import TTSEngine
        eng = TTSEngine("", "voice")
        assert eng._cache_key("hello") != eng._cache_key("world")
