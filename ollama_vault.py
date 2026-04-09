"""
ollama_vault.py — Local Ollama bridge.

Health-checks the local Ollama server, lists available models,
and provides a clean API for the rest of the pipeline to use.

Ollama runs on your PC — free, private, no API key.
Download: https://ollama.com
Pull a model: ollama pull llama3

Usage:
    py ollama_vault.py          # health check + model list
    py ollama_vault.py prompt   # interactive query
"""

import json
import sys
from typing import Iterator

import requests

OLLAMA_BASE  = "http://localhost:11434"
DEFAULT_MODEL = "llama3"
TIMEOUT_QUERY = 120   # seconds for single query
TIMEOUT_PROBE = 3     # seconds for health check


# ── Health check ──────────────────────────────────────────────────────────────

def is_running() -> bool:
    """Return True if Ollama server is reachable."""
    try:
        r = requests.get(OLLAMA_BASE, timeout=TIMEOUT_PROBE)
        return r.status_code in (200, 404)
    except Exception:
        return False


def list_models() -> list[str]:
    """Return list of locally available model names."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=TIMEOUT_PROBE)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def best_model(preferred: str = DEFAULT_MODEL) -> str:
    """Return preferred model if available, else first available, else preferred."""
    available = list_models()
    if not available:
        return preferred
    # Strip :tag for comparison
    names = [m.split(":")[0] for m in available]
    if preferred.split(":")[0] in names:
        return preferred
    return available[0]


# ── Query API ─────────────────────────────────────────────────────────────────

def query(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: str = "",
    temperature: float = 0.3,
    timeout: int = TIMEOUT_QUERY,
) -> str:
    """
    Send a single prompt to Ollama and return the full response string.
    Raises RuntimeError if Ollama is not running.
    """
    if not is_running():
        raise RuntimeError(
            "Ollama is not running.\n"
            "Start it with:  ollama serve\n"
            "Or download from: https://ollama.com"
        )

    payload: dict = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    r = requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json=payload,
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()


def stream_query(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: str = "",
    temperature: float = 0.3,
) -> Iterator[str]:
    """
    Stream tokens from Ollama as they arrive.
    Yields each token string.
    """
    if not is_running():
        raise RuntimeError("Ollama is not running.")

    payload: dict = {
        "model":   model,
        "prompt":  prompt,
        "stream":  True,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    with requests.post(
        f"{OLLAMA_BASE}/api/generate",
        json=payload,
        stream=True,
        timeout=TIMEOUT_QUERY,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            yield data.get("response", "")
            if data.get("done"):
                break


def chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    timeout: int = TIMEOUT_QUERY,
) -> str:
    """
    OpenAI-compatible chat API.
    messages = [{"role": "user", "content": "..."}, ...]
    Returns the assistant response string.
    """
    if not is_running():
        raise RuntimeError("Ollama is not running.")

    r = requests.post(
        f"{OLLAMA_BASE}/api/chat",
        json={
            "model":    model,
            "messages": messages,
            "stream":   False,
            "options":  {"temperature": temperature},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "").strip()


# ── Score content (used by orient.py) ────────────────────────────────────────

def score_posts_json(
    posts_json: str,
    system_prompt: str,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Send posts payload to Ollama with a system prompt; return raw response.
    Used by orient.py for content scoring.
    """
    return query(
        prompt=posts_json,
        model=model,
        system=system_prompt,
        temperature=0.2,
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def _health_report() -> None:
    print("\n── Ollama Vault Health Check ─────────────────────────────────")
    if is_running():
        print("  ✓ Ollama server reachable at", OLLAMA_BASE)
        models = list_models()
        if models:
            print(f"  ✓ {len(models)} model(s) available:")
            for m in models:
                marker = " ← default" if m.startswith(DEFAULT_MODEL) else ""
                print(f"      {m}{marker}")
        else:
            print("  ✗ No models installed.")
            print("    Fix:  ollama pull llama3")
    else:
        print("  ✗ Ollama NOT running.")
        print("    Start: ollama serve")
        print("    Install: https://ollama.com")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    _health_report()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"Query: {prompt}\n")
        try:
            for token in stream_query(prompt, model=best_model()):
                print(token, end="", flush=True)
            print()
        except RuntimeError as e:
            print(f"Error: {e}")
