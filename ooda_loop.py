"""
ooda_loop.py — Autonomous OODA cycle.
Observe Reddit → Orient (AI score) → Decide (pick best) → Act (make video)
Loops every 60 minutes. Runs forever with no manual steps.
"""

import time
from config import Config
from reddit_scraper import RedditScraper
from orient import Orient
from produce import make_video

VIABILITY_THRESHOLD = 7   # ai_score out of 10


def run_cycle() -> None:
    print("\n" + "=" * 52)
    print("  OODA CYCLE START")
    print("=" * 52)

    # ── OBSERVE ───────────────────────────────────────────────────────────────
    print("\n[OBSERVE] Scraping Reddit…")
    scraper = RedditScraper()
    signals: list[dict] = []
    for sub in Config.SUBREDDITS:
        signals.extend(scraper.get_top_posts(sub))
    print(f"[OBSERVE] {len(signals)} raw signals collected")

    if not signals:
        print("[OBSERVE] No signals — skipping cycle")
        return

    # ── ORIENT ────────────────────────────────────────────────────────────────
    print("\n[ORIENT] Scoring with AI…")
    scored = Orient().analyse(signals)

    # ── DECIDE ────────────────────────────────────────────────────────────────
    print("\n[DECIDE] Finding best story…")
    best = next((s for s in scored if s.get("ai_score", 0) >= VIABILITY_THRESHOLD), None)

    if not best:
        top = scored[0] if scored else None
        print(f"[DECIDE] No story scored >= {VIABILITY_THRESHOLD}.")
        if top:
            print(f"         Best available: {top['title'][:60]} (score={top['ai_score']})")
        return

    print(f"[DECIDE] Winner: {best['title'][:70]} (score={best['ai_score']}/10)")

    # Truncate story to ~150 words so video stays under 60 seconds
    words = best["text"].split()
    story = " ".join(words[:150])
    if len(words) > 150:
        story += "..."
        print(f"[DECIDE] Story truncated to 150 words for Shorts length")

    # ── ACT ───────────────────────────────────────────────────────────────────
    print("\n[ACT] Producing video…")
    try:
        output = make_video(
            story=story,
            title=best["title"],
            output="final_video.mp4",
            whisper_model=Config.WHISPER_MODEL,
        )
        print(f"\n[ACT] Video ready: {output}")
    except Exception as e:
        print(f"[ACT] Production failed: {e}")


if __name__ == "__main__":
    from check_env import validate
    validate()

    while True:
        try:
            run_cycle()
        except Exception as e:
            print(f"[LOOP] Cycle error: {e}")

        print(f"\nSleeping {Config.CYCLE_INTERVAL_MINUTES} min…")
        time.sleep(Config.CYCLE_INTERVAL_MINUTES * 60)
