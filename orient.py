"""
orient.py — Fast heuristic scoring. No AI calls, no waiting.
Reddit posts that pass strict quality filters go to production.
Everything else falls back to the story bank (which has great content).

Why no Ollama? It rated a Minecraft server ad 9/10. Heuristics are faster
and smarter for filtering Reddit garbage.
"""

VIABILITY_THRESHOLD = 7


class Orient:
    def __init__(self):
        self._ollama_available = False  # unused, kept for test compat

    def _probe_ollama(self) -> bool:
        return False

    def _heuristic_score(self, signal: dict) -> int:
        """
        Score 1-10 using Reddit signals only. Instant, no network calls.
        A story needs: high score, long personal text, engagement.
        """
        score  = signal.get("score", 0)
        text   = signal.get("text", "")
        title  = signal.get("title", "").lower()

        # Must be a text post with actual story content
        if len(text) < 200:
            return 1

        # Must sound like a personal story (AITA / relationship / drama)
        drama_words = [
            "aita", "wibta", "tifu", "my boyfriend", "my girlfriend",
            "my husband", "my wife", "my mom", "my dad", "my friend",
            "i told", "i quit", "i left", "i found out", "he said",
            "she said", "they said", "kicked out", "broke up", "cheating",
            "fired", "stole", "lied", "secret", "family", "wedding",
        ]
        drama_score = sum(1 for w in drama_words if w in title or w in text.lower())
        if drama_score == 0:
            return 2

        # Score based on Reddit popularity + engagement + drama keywords
        pop   = min(score / 1000, 3.0)         # 0-3 pts
        drama = min(drama_score / 3, 3.0)      # 0-3 pts
        length = min(len(text) / 500, 2.0)     # 0-2 pts (longer = better story)
        comments = min(signal.get("num_comments", 0) / 200, 2.0)  # 0-2 pts

        total = pop + drama + length + comments
        return max(1, min(10, int(total)))

    def analyse(self, signals: list[dict]) -> list[dict]:
        if not signals:
            return []

        results = []
        for s in signals:
            results.append({**s, "ai_score": self._heuristic_score(s)})

        results.sort(key=lambda x: x["ai_score"], reverse=True)
        viable = sum(1 for r in results if r["ai_score"] >= VIABILITY_THRESHOLD)
        print(f"[ORIENT] {len(results)} signals scored instantly — {viable} viable — top: {results[0]['ai_score']}/10")
        return results

    def synthesise_trends(self, assessments: list[dict]) -> dict:
        viable = [a for a in assessments if a.get("ai_score", 0) >= VIABILITY_THRESHOLD]
        return {"cycle_viable": len(viable), "cycle_total": len(assessments)}
