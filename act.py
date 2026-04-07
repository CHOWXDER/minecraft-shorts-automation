"""
OODA Phase 4 — ACT
Execution engine: build video, upload to YouTube, record outcomes.

Outcomes feed back into the OODA loop's ORIENT phase on the next cycle
via performance_log.json, allowing the system to learn which content
types, subreddits, and title styles actually drive views.
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from video_builder import VideoBuilder
from youtube_uploader import upload_video
from decide import Decision


# ---------------------------------------------------------------------------

@dataclass
class ActionResult:
    content_id: str
    success: bool
    video_path: Optional[str]
    youtube_video_id: Optional[str]
    upload_scheduled_time: Optional[str]
    error: Optional[str]
    duration_seconds: float

    def to_dict(self) -> dict:
        return {
            'content_id': self.content_id,
            'success': self.success,
            'video_path': self.video_path,
            'youtube_video_id': self.youtube_video_id,
            'upload_scheduled_time': self.upload_scheduled_time,
            'error': self.error,
            'duration_seconds': round(self.duration_seconds, 2),
        }


class Actor:
    """
    ACT phase: Execute production pipeline and persist outcomes.

    Each execution record written to performance_log.json captures:
    - The AI scores that drove the decision
    - Whether production succeeded
    - The scheduled upload time

    This log is the feedback data that makes the OODA loop self-improving:
    future Orient cycles can correlate AI scores with real-world outcomes.
    """

    PERF_LOG = 'performance_log.json'

    def __init__(self, config):
        self.config = config
        self._load_log()

    # ------------------------------------------------------------------ state

    def _load_log(self):
        if os.path.exists(self.PERF_LOG):
            with open(self.PERF_LOG) as f:
                self.log: list[dict] = json.load(f)
        else:
            self.log = []

    def _save_log(self):
        with open(self.PERF_LOG, 'w') as f:
            json.dump(self.log, f, indent=2)

    # --------------------------------------------------------------- helpers

    def _safe_filename(self, content_id: str) -> str:
        return content_id[:30].replace('/', '_').replace('\\', '_').replace(':', '_')

    def _build_description(self, decision: Decision) -> str:
        sig = decision.assessment.signal
        lines = [
            decision.assessment.reasoning,
            '',
            f'Original story from r/{sig.subreddit}',
            '',
            '#Minecraft #Shorts #MinecraftStories',
        ]
        return '\n'.join(lines)

    # ---------------------------------------------------------------- public

    def execute(
        self,
        decision: Decision,
        video_path: str,
        audio_path: str,
        subtitle_path: str,
    ) -> ActionResult:
        """
        Run the full production pipeline for a single Decision.

        Steps:
          1. Build the video with FFmpeg (VideoBuilder)
          2. Upload to YouTube with scheduled publish time
          3. Record outcome to performance log
        """
        t0 = time.time()
        content_id = decision.assessment.signal.content_id
        output_path = f'output_{self._safe_filename(content_id)}.mp4'

        print(f'[ACT] Building: "{decision.assessment.suggested_title[:50]}"')

        try:
            builder = VideoBuilder(video_path, audio_path, subtitle_path)
            builder.build_video(output_path)

            print(f'[ACT] Uploading → scheduled {decision.upload_slot[:10]}')
            upload_video(
                file=output_path,
                title=decision.assessment.suggested_title,
                description=self._build_description(decision),
                tags=decision.assessment.suggested_tags,
                scheduled_time=decision.upload_slot,
            )

            result = ActionResult(
                content_id=content_id,
                success=True,
                video_path=output_path,
                youtube_video_id=None,   # populated post-upload when API returns ID
                upload_scheduled_time=decision.upload_slot,
                error=None,
                duration_seconds=time.time() - t0,
            )
            print(f'[ACT] Success — production took {result.duration_seconds:.1f}s')

        except Exception as exc:
            result = ActionResult(
                content_id=content_id,
                success=False,
                video_path=None,
                youtube_video_id=None,
                upload_scheduled_time=None,
                error=str(exc),
                duration_seconds=time.time() - t0,
            )
            print(f'[ACT] FAILED: {exc}')

        self._record(decision, result)
        return result

    def _record(self, decision: Decision, result: ActionResult):
        a = decision.assessment
        record = {
            **result.to_dict(),
            'title': a.suggested_title,
            'subreddit': a.signal.subreddit,
            'decision_score': decision.decision_score,
            'ai_scores': {
                'viral_potential': a.viral_potential,
                'narrative_strength': a.narrative_strength,
                'title_quality': a.title_quality,
                'audience_fit': a.audience_fit,
                'composite': a.composite_score,
            },
            'scored_by_ai': a.scored_by_ai,
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }
        self.log.append(record)
        self._save_log()

    def performance_summary(self) -> dict:
        """Aggregate stats from the performance log for reporting."""
        if not self.log:
            return {'total_actions': 0}
        total = len(self.log)
        successes = sum(1 for r in self.log if r.get('success'))
        avg_score = sum(r.get('decision_score', 0) for r in self.log) / total
        return {
            'total_actions': total,
            'successes': successes,
            'failures': total - successes,
            'success_rate': round(successes / total, 2),
            'avg_decision_score': round(avg_score, 1),
        }
