"""
OODA Phase 4 — ACT
Fully automated production: story → ElevenLabs TTS → Whisper sync →
FFmpeg render → YouTube upload → performance log.

No external asset paths required. produce.make_video() owns the entire
media pipeline; Act just orchestrates scheduling and outcome recording.
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from produce import make_video
from youtube_uploader import upload_video


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
    ACT phase: produce a video from a queue item, upload it, log the outcome.

    Queue items come from DecisionEngine.ready_for_production() and carry
    all the context needed — title, story, tags, upload_slot — so this
    phase is fully self-contained once the queue is populated.
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
        return content_id[:40].replace('/', '_').replace('\\', '_').replace(':', '_')

    def _build_description(self, queue_item: dict) -> str:
        lines = [
            queue_item.get('rationale', ''),
            '',
            f'Original story from r/{queue_item.get("subreddit", "Minecraft")}',
            '',
            '#Minecraft #Shorts #MinecraftStories #AITA',
        ]
        return '\n'.join(lines)

    # ---------------------------------------------------------------- public

    def execute_queued(self, queue_item: dict) -> ActionResult:
        """
        End-to-end production for a single queue item.

        1. Calls produce.make_video()  → ElevenLabs TTS + Whisper + FFmpeg
        2. Uploads to YouTube with the scheduled publish slot
        3. Records full outcome to performance_log.json
        """
        t0         = time.time()
        content_id = queue_item['content_id']
        title      = queue_item.get('title', 'Minecraft Short')
        story      = queue_item.get('story') or title
        upload_slot = queue_item.get('upload_slot')
        tags       = queue_item.get('tags', ['Minecraft', 'Shorts', 'MinecraftStories'])

        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(
            self.config.OUTPUT_DIR,
            f'video_{self._safe_filename(content_id)}.mp4',
        )

        print(f'\n[ACT] Producing: "{title[:60]}"')
        print(f'[ACT] Upload slot: {upload_slot[:16] if upload_slot else "immediate"} UTC')

        try:
            make_video(
                story=story,
                title=title,
                output=output_path,
                voice_id=self.config.ELEVENLABS_VOICE_ID,
                url=self.config.MINECRAFT_FOOTAGE_URL,
                whisper_model=self.config.WHISPER_MODEL,
            )

            print(f'[ACT] Uploading to YouTube…')
            upload_video(
                file=output_path,
                title=title,
                description=self._build_description(queue_item),
                tags=tags,
                scheduled_time=upload_slot,
            )

            result = ActionResult(
                content_id=content_id,
                success=True,
                video_path=output_path,
                youtube_video_id=None,
                upload_scheduled_time=upload_slot,
                error=None,
                duration_seconds=time.time() - t0,
            )
            print(f'[ACT] Success — {result.duration_seconds:.1f}s total → {output_path}')

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

        self._record(queue_item, result)
        return result

    def _record(self, queue_item: dict, result: ActionResult):
        record = {
            **result.to_dict(),
            'title': queue_item.get('title'),
            'subreddit': queue_item.get('subreddit'),
            'decision_score': queue_item.get('decision_score'),
            'ai_composite': queue_item.get('ai_composite'),
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }
        self.log.append(record)
        self._save_log()

    def performance_summary(self) -> dict:
        if not self.log:
            return {'total_actions': 0}
        total      = len(self.log)
        successes  = sum(1 for r in self.log if r.get('success'))
        avg_score  = sum(r.get('decision_score') or 0 for r in self.log) / total
        return {
            'total_actions': total,
            'successes': successes,
            'failures': total - successes,
            'success_rate': round(successes / total, 2),
            'avg_decision_score': round(avg_score, 1),
        }
