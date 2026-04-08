"""
OODA Phase 3 — DECIDE
Priority queue, slot-aware scheduling optimizer, and adaptive thresholds.

Decision score formula (weighted):
  60% — AI composite score (orient.py)
  20% — velocity (upvotes/hr, normalised)
  10% — engagement rate (comments/score, normalised)
  10% — raw score (normalised)

The engine also applies a recency bonus for posts < 6 hours old (momentum
is most predictive when a post is still actively climbing) and a small
diversity penalty to avoid queuing multiple posts from the same subreddit
in the same cycle.

State is persisted to production_queue.json so scheduling survives restarts.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from orient import Assessment


# ---------------------------------------------------------------------------

@dataclass
class Decision:
    assessment: Assessment
    priority_rank: int
    upload_slot: str            # ISO-8601 UTC datetime
    decision_score: float       # 0-100
    rationale: str
    status: str = 'queued'      # queued | in_progress | done | skipped


class DecisionEngine:
    """
    DECIDE phase: score, rank, schedule, and persist content decisions.

    Upload slots are allocated on Mon / Wed / Fri at UPLOAD_HOUR UTC.
    Only MAX_PER_CYCLE decisions are emitted per OODA cycle to prevent
    over-scheduling.  Already-queued content_ids are skipped.
    """

    QUEUE_FILE = 'production_queue.json'
    SCHEDULE_DAYS = {'Monday', 'Wednesday', 'Friday'}
    UPLOAD_HOUR = 14          # 2 PM UTC
    MAX_PER_CYCLE = 3
    RECENCY_BONUS_HOURS = 6   # posts younger than this get a +5 score bonus
    RECENCY_BONUS = 5.0

    def __init__(self, config):
        self.config = config
        self._load_queue()

    # ------------------------------------------------------------------ state

    def _load_queue(self):
        if os.path.exists(self.QUEUE_FILE):
            with open(self.QUEUE_FILE) as f:
                self.queue: list[dict] = json.load(f)
        else:
            self.queue = []

    def _save_queue(self):
        with open(self.QUEUE_FILE, 'w') as f:
            json.dump(self.queue, f, indent=2)

    # ----------------------------------------------------------------- slots

    def _queued_slots(self) -> set[str]:
        return {item['upload_slot'] for item in self.queue if 'upload_slot' in item}

    def _next_free_slot(self) -> str:
        """Return the next Mon/Wed/Fri 14:00 UTC slot that is not already taken."""
        now = datetime.now(timezone.utc)
        taken = self._queued_slots()
        for days_ahead in range(21):  # look up to 3 weeks out
            candidate = now + timedelta(days=days_ahead)
            if candidate.strftime('%A') in self.SCHEDULE_DAYS:
                slot_dt = candidate.replace(
                    hour=self.UPLOAD_HOUR, minute=0, second=0, microsecond=0
                )
                if slot_dt > now:
                    slot_str = slot_dt.isoformat()
                    if slot_str not in taken:
                        taken.add(slot_str)  # reserve optimistically
                        return slot_str
        # Fallback: 7 days from now
        return (now + timedelta(days=7)).isoformat()

    # --------------------------------------------------------------- scoring

    def _decision_score(self, assessment: Assessment) -> float:
        s = assessment.signal

        ai_component = assessment.composite_score * 0.60
        velocity_norm = min(s.velocity / 500, 1.0) * 100 * 0.20
        engagement_norm = min(s.engagement_rate / 0.5, 1.0) * 100 * 0.10
        raw_score_norm = min(s.score / 10_000, 1.0) * 100 * 0.10

        base = ai_component + velocity_norm + engagement_norm + raw_score_norm

        # Recency bonus: posts still climbing are higher-risk, higher-reward
        import time
        age_hours = (time.time() - s.created_utc) / 3600
        if age_hours < self.RECENCY_BONUS_HOURS and s.momentum > 0:
            base += self.RECENCY_BONUS

        return round(min(base, 100.0), 2)

    def _already_queued(self, content_id: str) -> bool:
        return any(item['content_id'] == content_id for item in self.queue)

    # ---------------------------------------------------------------- public

    def decide(self, assessments: list[Assessment]) -> list[Decision]:
        """
        Select top viable content, assign upload slots, persist to queue.
        Returns at most MAX_PER_CYCLE Decision objects.
        """
        viable = [a for a in assessments if a.is_viable and not self._already_queued(a.signal.content_id)]
        if not viable:
            print('[DECIDE] No new viable content this cycle.')
            return []

        # Score and rank
        scored = sorted(viable, key=self._decision_score, reverse=True)

        decisions: list[Decision] = []
        seen_subreddits: set[str] = set()

        for rank, assessment in enumerate(scored, 1):
            if len(decisions) >= self.MAX_PER_CYCLE:
                break

            sub = assessment.signal.subreddit
            # Soft diversity filter: allow max 2 posts from same subreddit per cycle
            sub_count = sum(1 for d in decisions if d.assessment.signal.subreddit == sub)
            if sub_count >= 2:
                continue

            dscore = self._decision_score(assessment)
            slot = self._next_free_slot()
            rationale = (
                f'Rank #{rank} | decision={dscore:.1f} | '
                f'AI composite={assessment.composite_score:.0f} | '
                f'velocity={assessment.signal.velocity:.0f} upvotes/hr | '
                f'{assessment.reasoning}'
            )

            decision = Decision(
                assessment=assessment,
                priority_rank=rank,
                upload_slot=slot,
                decision_score=dscore,
                rationale=rationale,
            )
            decisions.append(decision)
            seen_subreddits.add(sub)

            # Persist — store story body so Act phase can produce without re-scraping
            self.queue.append({
                'content_id': assessment.signal.content_id,
                'title': assessment.suggested_title,
                'story': assessment.signal.body or assessment.signal.title,
                'source_url': assessment.signal.url,
                'subreddit': sub,
                'upload_slot': slot,
                'status': 'queued',
                'decision_score': dscore,
                'ai_composite': assessment.composite_score,
                'tags': assessment.suggested_tags,
                'rationale': rationale,
                'queued_at': datetime.now(timezone.utc).isoformat(),
            })

        self._save_queue()

        print(f'[DECIDE] {len(decisions)} content item(s) queued this cycle')
        for d in decisions:
            print(f'  → "{d.assessment.suggested_title[:50]}" | slot={d.upload_slot[:10]} | score={d.decision_score:.1f}')

        return decisions

    def ready_for_production(self) -> list[dict]:
        """Return queued items whose upload slot falls within the next 24 hours."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(hours=24)
        ready = []
        for item in self.queue:
            if item.get('status') != 'queued':
                continue
            try:
                slot = datetime.fromisoformat(item['upload_slot'])
                if now <= slot <= cutoff:
                    ready.append(item)
            except (ValueError, KeyError):
                pass
        return ready

    def mark_done(self, content_id: str, outcome: dict):
        """Record production outcome and update queue entry status."""
        for item in self.queue:
            if item['content_id'] == content_id:
                item['status'] = 'done'
                item['outcome'] = outcome
                item['completed_at'] = datetime.now(timezone.utc).isoformat()
                break
        self._save_queue()

    def mark_skipped(self, content_id: str, reason: str):
        for item in self.queue:
            if item['content_id'] == content_id:
                item['status'] = 'skipped'
                item['skip_reason'] = reason
                break
        self._save_queue()

    def queue_stats(self) -> dict:
        statuses = [item.get('status', 'unknown') for item in self.queue]
        from collections import Counter
        return {
            'total': len(self.queue),
            **Counter(statuses),
        }
