import requests
import json

OLLAMA_BASE = "http://localhost:11434"


def is_running() -> bool:
    try:
        return requests.get(OLLAMA_BASE, timeout=3).status_code in (200, 404)
    except Exception:
        return False


def query_ollama(prompt: str, system_prompt: str = "") -> str | None:
    try:
        payload = {
            "model":  "llama3",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if system_prompt:
            payload["system"] = system_prompt
        r = requests.post(f"{OLLAMA_BASE}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        print(f"[Ollama] Error: {e}")
        return None


if __name__ == "__main__":
    if is_running():
        print("✓ Ollama is running")
        print(query_ollama("Say READY in one word."))
    else:
        print("✗ Ollama not running — open the Ollama app then run: ollama serve")
