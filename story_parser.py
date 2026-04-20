"""story_parser.py — Split a Reddit story into narrator / other speaker segments."""
import json
import re
import requests
from config import Config

NARRATOR_VOICE = "pNInz6obpgDQGcFmaJgB"   # Adam — deep male
OTHER_VOICE    = "21m00Tcm4TlvDq8ikWAM"   # Rachel — female


def parse_segments(story: str) -> list[dict]:
    """
    Returns list of {"speaker": "narrator"|"other", "text": "...", "voice_id": "..."}.
    Falls back to a single narrator segment if Ollama is unavailable or returns bad JSON.
    """
    prompt = (
        "You are splitting a Reddit AITA story into audio segments for a YouTube Short.\n\n"
        f"Story:\n{story}\n\n"
        "Return ONLY a JSON array with no extra text. Each item must have:\n"
        '  "speaker": "narrator" (OP\'s own words) or "other" (OP quoting someone else)\n'
        '  "text": the text for that segment\n\n'
        "Rules:\n"
        '- Use "other" ONLY when OP clearly quotes another person speaking (look for he said / she told me / direct quotes)\n'
        "- Each segment should be 1-3 sentences\n"
        "- If no direct quotes exist just return a single narrator segment\n"
        "- Return ONLY valid JSON, nothing else\n\n"
        "Example:\n"
        '[{"speaker":"narrator","text":"I asked him to stop."},'
        '{"speaker":"other","text":"He said I was overreacting."},'
        '{"speaker":"narrator","text":"I couldn\'t believe it."}]'
    )
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": Config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            segs = json.loads(m.group())
            if isinstance(segs, list) and segs:
                for s in segs:
                    s["voice_id"] = OTHER_VOICE if s.get("speaker") == "other" else NARRATOR_VOICE
                print(f"  [Parser] {len(segs)} segments — "
                      f"{sum(1 for s in segs if s['speaker']=='narrator')} narrator, "
                      f"{sum(1 for s in segs if s['speaker']=='other')} other")
                return segs
    except Exception as e:
        print(f"  [Parser] Ollama unavailable ({e}) — single narrator")

    return [{"speaker": "narrator", "text": story, "voice_id": NARRATOR_VOICE}]
