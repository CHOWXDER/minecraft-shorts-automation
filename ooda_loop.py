"""
ooda_loop.py — Autonomous OODA cycle.
Observe Reddit → Orient (AI score) → Decide (pick best) → Act (make video)
Falls back to proven viral story bank when Reddit produces nothing good.
Loops every 60 minutes. Runs forever with no manual steps.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from config import Config
from reddit_scraper import RedditScraper
from orient import Orient
from produce import make_video
from story_bank import get_story
from youtube_uploader import upload_video

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

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
        print(f"[DECIDE] No Reddit story scored >= {VIABILITY_THRESHOLD} — using story bank")
        best = get_story()
        best["ai_score"] = 10   # bank stories are pre-vetted
        best["text"] = best.get("text", "")
    else:
        print(f"[DECIDE] Reddit winner: {best['title'][:70]} (score={best['ai_score']}/10)")

    # Truncate story to ~150 words so video stays under 60 seconds
    words = best["text"].split()
    story = " ".join(words[:150])
    if len(words) > 150:
        story += "..."
        print(f"[DECIDE] Story truncated to 150 words for Shorts length")

    # ── ACT ───────────────────────────────────────────────────────────────────
    print("\n[ACT] Producing video…")
    try:
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(OUTPUT_DIR / f"video_{timestamp}.mp4")
        output = make_video(
            story=story,
            title=best["title"],
            output=output_path,
            whisper_model=Config.WHISPER_MODEL,
            gta_url=Config.GTA_FOOTAGE_URL,
        )
        print(f"\n[ACT] Video ready: {output}")
        os.startfile(os.path.abspath(output))

        upload_video(
            file=output,
            title=best["title"][:100],
            description=(
                f"{best['title']}\n\n"
                f"Drop your verdict in the comments.\n\n"
                f"#Shorts #AITA #Reddit #RedditStories #RelationshipAdvice"
            ),
            tags=[
                "reddit", "aita", "shorts", "reddit stories",
                "relationship advice", "storytime", "drama",
                "am i the asshole", "reddit drama",
            ],
        )
    except Exception as e:
        print(f"[ACT] Production failed: {e}")


if __name__ == "__main__":
    from check_env import validate
    validate()

    try:
        while True:
            try:
                run_cycle()
            except Exception as e:
                print(f"[LOOP] Cycle error: {e}")

            wait = Config.CYCLE_INTERVAL_MINUTES * 60
            print(f"\n{'='*52}")
            print(f"  CYCLE DONE. Next in {Config.CYCLE_INTERVAL_MINUTES} min.")
            print(f"  Video saved: final_video.mp4")
            print(f"{'='*52}\n")
            for remaining in range(wait, 0, -30):
                mins, secs = divmod(remaining, 60)
                print(f"  Next cycle in {mins:02d}:{secs:02d} ...  (Ctrl+C to stop)", end="\r")
                time.sleep(30)
    except KeyboardInterrupt:
        print("\n\n  Stopped. Bye.")
