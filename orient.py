import re
from ollama_vault import query_ollama, is_running

VIABILITY_THRESHOLD = 7   # out of 10


class Orient:
    def __init__(self):
        self._ollama_available: bool | None = None  # lazy probe

    def _probe_ollama(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        self._ollama_available = is_running()
        if self._ollama_available:
            print("[ORIENT] Ollama detected — using AI scoring")
        else:
            print("[ORIENT] Ollama not running — using heuristic scoring")
        return self._ollama_available

    def _heuristic_score(self, signal: dict) -> int:
        """Rule-based 1-10 score when Ollama is unavailable."""
        return min(10, max(1, int(signal.get("score", 0) / 500)))

    def analyse(self, signals: list[dict]) -> list[dict]:
        if not signals:
            return []

        use_ai = self._probe_ollama()
        results = []

        for s in signals:
            if use_ai:
                prompt = (
                    f"Rate this Reddit story's viral potential as a 60-second YouTube Short "
                    f"for Minecraft fans aged 13-25. Return ONLY a number from 1 to 10.\n\n"
                    f"Title: {s['title']}\n"
                    f"Story: {s.get('text', '')[:300]}"
                )
                raw   = query_ollama(prompt)
                match = re.search(r'\b([1-9]|10)\b', raw or "")
                ai_score = int(match.group(1)) if match else self._heuristic_score(s)
            else:
                ai_score = self._heuristic_score(s)

            results.append({**s, "ai_score": ai_score})

        results.sort(key=lambda x: x["ai_score"], reverse=True)
        top = results[0]["ai_score"] if results else 0
        print(f"[ORIENT] Scored {len(results)} signals — top score: {top}/10")
        return results

    def synthesise_trends(self, assessments: list[dict]) -> dict:
        viable = [a for a in assessments if a.get("ai_score", 0) >= VIABILITY_THRESHOLD]
        return {"cycle_viable": len(viable), "cycle_total": len(assessments)}
