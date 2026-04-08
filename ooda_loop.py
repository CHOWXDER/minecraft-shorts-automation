"""
OODA Loop — Fully Automated Orchestrator
Observe → Orient → Decide → Act, continuously.

Run modes
---------
  python ooda_loop.py              # single cycle
  python ooda_loop.py --daemon     # continuous loop at CYCLE_INTERVAL_MINUTES
  python ooda_loop.py --report     # queue + performance summary, no cycle
  python ooda_loop.py --produce    # force-produce all ready queue items now

Pipeline
--------
  OBSERVE  →  Reddit signals (viral velocity, momentum, engagement)
  ORIENT   →  Claude AI scores (viral_potential, narrative_strength, ...)
  DECIDE   →  Ranked queue with Mon/Wed/Fri upload slots
  ACT      →  ElevenLabs TTS → Whisper sync → FFmpeg → YouTube upload

The loop is fully self-contained. No manual asset paths needed.
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
        self.config  = config
        self.observer = Observer(config)
        self.orient   = Orient(config)
        self.decider  = DecisionEngine(config)
        self.actor    = Actor(config)

    # ----------------------------------------------------------------- cycle

    def run_cycle(self) -> dict:
        """Execute one full OODA cycle. Returns a summary dict."""
        cycle_start = time.time()
        ts = datetime.now(timezone.utc).isoformat()
        print(f'\n{"=" * 60}')
        print(f'OODA CYCLE  {ts}')
        print(f'{"=" * 60}')

        # ── OBSERVE ────────────────────────────────────────────────────────
        signals = self.observer.gather()
        if not signals:
            print('[OODA] No signals — aborting cycle.')
            return {'timestamp': ts, 'signals': 0, 'viable': 0, 'decisions': 0}

        # ── ORIENT ─────────────────────────────────────────────────────────
        assessments = self.orient.analyse(signals)
        trends      = self.orient.synthesise_trends(assessments)

        # ── DECIDE ─────────────────────────────────────────────────────────
        decisions = self.decider.decide(assessments)

        # ── ACT ─────────────────────────────────────────────────────────────
        results = self._act_on_ready()

        elapsed = round(time.time() - cycle_start, 1)
        summary = {
            'timestamp': ts,
            'elapsed_seconds': elapsed,
            'signals_observed': len(signals),
            'signals_assessed': len(assessments),
            **trends,
            'decisions_made': len(decisions),
            'videos_produced': sum(1 for r in results if r.success),
            'videos_failed':   sum(1 for r in results if not r.success),
            'queue_stats': self.decider.queue_stats(),
            'performance': self.actor.performance_summary(),
        }

        print(f'\n[OODA] Cycle complete in {elapsed}s')
        print(f'       Signals : {len(signals)} → {trends["cycle_viable"]} viable → {len(decisions)} queued')
        print(f'       Produced: {summary["videos_produced"]} ok, {summary["videos_failed"]} failed')
        print(f'       Queue   : {summary["queue_stats"]}')
        self._write_cycle_log(summary)
        return summary

    # ─────────────────────────────────────────────────────────────── act ────

    def _act_on_ready(self):
        """Produce + upload all queue items due in the next 24 hours."""
        from act import ActionResult
        ready = self.decider.ready_for_production()

        if not ready:
            print('[ACT] No items due for production in the next 24 hrs.')
            return []

        print(f'[ACT] {len(ready)} item(s) due — producing now…')
        results: list[ActionResult] = []

        for item in ready:
            result = self.actor.execute_queued(item)
            results.append(result)

            if result.success:
                self.decider.mark_done(item['content_id'], result.to_dict())
            else:
                self.decider.mark_skipped(
                    item['content_id'],
                    result.error or 'unknown error'
                )

        return results

    # ─────────────────────────────────────────────────────────────── report ─

    def report(self):
        """Print a human-readable status report."""
        print('\n── Queue ──────────────────────────────────────────────────')
        print(json.dumps(self.decider.queue_stats(), indent=2))
        print('\n── Performance ────────────────────────────────────────────')
        print(json.dumps(self.actor.performance_summary(), indent=2))
        print('\n── Upcoming (next 24 h) ───────────────────────────────────')
        ready = self.decider.ready_for_production()
        if ready:
            for item in ready:
                print(f'  "{item["title"][:50]}" → {item["upload_slot"][:16]} UTC')
        else:
            print('  (none due)')

    # ──────────────────────────────────────────────────────────── cycle log ─

    def _write_cycle_log(self, summary: dict):
        with open('cycle_log.jsonl', 'a') as f:
            f.write(json.dumps(summary) + '\n')


# ---------------------------------------------------------------------------

def main():
    from check_env import validate
    validate(exit_on_fail=True)

    parser = argparse.ArgumentParser(description='Minecraft Shorts OODA Loop')
    parser.add_argument('--daemon',  action='store_true',
                        help=f'Run continuously every {CYCLE_INTERVAL_MINUTES} minutes')
    parser.add_argument('--report',  action='store_true',
                        help='Print queue/performance report and exit')
    parser.add_argument('--produce', action='store_true',
                        help='Force-produce all ready queue items now and exit')
    parser.add_argument('--interval', type=int, default=CYCLE_INTERVAL_MINUTES,
                        help='Cycle interval in minutes (daemon mode)')
    args = parser.parse_args()

    loop = OODALoop(Config)

    if args.report:
        loop.report()
        return

    if args.produce:
        print('[OODA] Force-produce mode')
        loop._act_on_ready()
        return

    if args.daemon:
        interval_secs = args.interval * 60
        print(f'[OODA] Daemon — cycle every {args.interval} minutes. Ctrl+C to stop.')
        while True:
            try:
                loop.run_cycle()
            except KeyboardInterrupt:
                print('\n[OODA] Stopped.')
                break
            except Exception as exc:
                print(f'[OODA] Cycle error: {exc}')
            print(f'[OODA] Sleeping {args.interval}m…')
            time.sleep(interval_secs)
    else:
        loop.run_cycle()


if __name__ == '__main__':
    main()
