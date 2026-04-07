"""
OODA Loop — Orchestrator
Observe → Orient → Decide → Act, continuously.

Run modes
---------
  python ooda_loop.py              # single cycle (cron / scheduler friendly)
  python ooda_loop.py --daemon     # continuous loop at CYCLE_INTERVAL_MINUTES
  python ooda_loop.py --report     # print queue + performance summary, no cycle

Wiring
------
  Observe  →  raw Signals (Reddit posts + derived metrics)
  Orient   →  Assessments (Claude AI scores + suggested metadata)
  Decide   →  Decisions   (ranked queue + upload slots)
  Act      →  ActionResults (build + upload + feedback log)

The feedback loop closes because performance_log.json accumulates real
outcomes across cycles, and future Orient calls can be enhanced to weight
AI predictions against historical accuracy per subreddit or content type.
"""

import argparse
import json
import time
from datetime import datetime, timezone

from config import Config
from observe import Observer
from orient import Orient
from decide import DecisionEngine
from act import Actor


CYCLE_INTERVAL_MINUTES = 60


# ---------------------------------------------------------------------------

class OODALoop:
    def __init__(self, config: Config):
        self.config = config
        self.observer = Observer(config)
        self.orient = Orient(config)
        self.decider = DecisionEngine(config)
        self.actor = Actor(config)

    # ----------------------------------------------------------------- cycle

    def run_cycle(self) -> dict:
        """
        Execute one full OODA cycle and return a summary dict.

        The cycle is intentionally decoupled from actual video/audio asset
        paths — the Act phase is only triggered for items already due in the
        production queue (within 24 hours), not for every new Decision.
        This keeps the loop fast and lets humans / downstream automation
        supply asset paths when ready.
        """
        cycle_start = time.time()
        ts = datetime.now(timezone.utc).isoformat()
        print(f'\n{"="*60}')
        print(f'OODA CYCLE  {ts}')
        print(f'{"="*60}')

        # ── OBSERVE ────────────────────────────────────────────────────────
        signals = self.observer.gather()

        if not signals:
            print('[OODA] No signals collected — aborting cycle.')
            return {'timestamp': ts, 'signals': 0, 'viable': 0, 'decisions': 0}

        # ── ORIENT ─────────────────────────────────────────────────────────
        assessments = self.orient.analyse(signals)
        trends = self.orient.synthesise_trends(assessments)

        # ── DECIDE ─────────────────────────────────────────────────────────
        decisions = self.decider.decide(assessments)

        # ── ACT (dry-run for newly decided content) ─────────────────────────
        # Full Act execution requires asset paths (video/audio/subtitle files)
        # which come from an external production pipeline.  Here we surface
        # items that are *ready* for production so that pipeline can pick them up.
        ready = self.decider.ready_for_production()
        if ready:
            print(f'[ACT] {len(ready)} item(s) due for production in next 24 hrs:')
            for item in ready:
                print(f'  → "{item["title"][:50]}" @ {item["upload_slot"][:16]} UTC')
        else:
            print('[ACT] No items due for production in next 24 hrs.')

        elapsed = round(time.time() - cycle_start, 1)
        summary = {
            'timestamp': ts,
            'elapsed_seconds': elapsed,
            'signals_observed': len(signals),
            'signals_assessed': len(assessments),
            **trends,
            'decisions_made': len(decisions),
            'ready_for_production': len(ready),
            'queue_stats': self.decider.queue_stats(),
            'performance': self.actor.performance_summary(),
        }

        print(f'\n[OODA] Cycle complete in {elapsed}s')
        print(f'       Signals: {len(signals)} observed → {trends["cycle_viable"]} viable → {len(decisions)} queued')
        print(f'       Queue: {summary["queue_stats"]}')
        self._write_cycle_log(summary)
        return summary

    # ─────────────────────────────────────────────────── production handoff ─

    def execute_production(
        self,
        content_id: str,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
    ):
        """
        Trigger Act phase for a specific content_id with supplied asset paths.

        Call this from your external production pipeline once assets are ready.
        Example:
            loop = OODALoop(Config)
            loop.execute_production(
                content_id='https://reddit.com/...',
                video_path='assets/clip.mp4',
                audio_path='assets/voice.mp3',
                subtitle_path='assets/subs.srt',
            )
        """
        # Find the corresponding Decision from the queue
        queue_item = next(
            (item for item in self.decider.queue if item['content_id'] == content_id),
            None,
        )
        if not queue_item:
            raise ValueError(f'content_id not found in queue: {content_id}')

        # Reconstruct a minimal Decision stub for the Actor
        from decide import Decision
        from orient import Assessment
        from observe import Signal

        # Pull the real assessment from an in-memory analyse call if needed
        # For now we pass a lightweight stub — real implementations should
        # cache assessments in state.json for retrieval here.
        print(f'[OODA] Executing production for: {queue_item["title"]}')
        # (Full wiring left as integration point for production pipeline)
        raise NotImplementedError(
            'execute_production is the integration point for your asset pipeline. '
            'Supply Decision + asset paths and call actor.execute().'
        )

    # ─────────────────────────────────────────────────────────────── report ─

    def report(self):
        """Print a human-readable status report."""
        print('\n── Queue ──────────────────────────────────────────────────')
        stats = self.decider.queue_stats()
        print(json.dumps(stats, indent=2))
        print('\n── Performance ────────────────────────────────────────────')
        perf = self.actor.performance_summary()
        print(json.dumps(perf, indent=2))
        print('\n── Upcoming Production (next 24 h) ────────────────────────')
        ready = self.decider.ready_for_production()
        for item in ready:
            print(f'  "{item["title"][:50]}" → {item["upload_slot"][:16]} UTC')
        if not ready:
            print('  (none)')

    # ──────────────────────────────────────────────────────────── cycle log ─

    def _write_cycle_log(self, summary: dict):
        log_file = 'cycle_log.jsonl'
        with open(log_file, 'a') as f:
            f.write(json.dumps(summary) + '\n')


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Minecraft Shorts OODA Loop')
    parser.add_argument('--daemon', action='store_true',
                        help=f'Run continuously every {CYCLE_INTERVAL_MINUTES} minutes')
    parser.add_argument('--report', action='store_true',
                        help='Print queue/performance report and exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_MINUTES,
                        help='Cycle interval in minutes (daemon mode)')
    args = parser.parse_args()

    loop = OODALoop(Config)

    if args.report:
        loop.report()
        return

    if args.daemon:
        interval_secs = args.interval * 60
        print(f'[OODA] Daemon mode — cycle every {args.interval} minutes')
        while True:
            try:
                loop.run_cycle()
            except KeyboardInterrupt:
                print('\n[OODA] Stopped by user.')
                break
            except Exception as exc:
                print(f'[OODA] Cycle error: {exc}')
            print(f'[OODA] Sleeping {args.interval}m until next cycle…')
            time.sleep(interval_secs)
    else:
        loop.run_cycle()


if __name__ == '__main__':
    main()
