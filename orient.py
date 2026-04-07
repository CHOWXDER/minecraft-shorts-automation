"""
OODA Phase 2 — ORIENT
Claude AI-powered content analysis, scoring, and trend synthesis.

Each Signal is evaluated across four dimensions by claude-sonnet-4-6:
  - Viral Potential   : hook strength, shareability, emotional resonance
  - Narrative Strength: story arc, conflict, resolution potential
  - Title Quality     : effectiveness of original title for YT Shorts
  - Audience Fit      : alignment with Minecraft Shorts audience (13-25 yr)

Results are combined into a composite score and supplemented with an
optimized title, recommended tags, and a one-sentence rationale.
"""

import json
import anthropic
from dataclasses import dataclass, field
from observe import Signal


@dataclass
class Assessment:
    signal: Signal
    viral_potential: float      # 0-100
    narrative_strength: float   # 0-100
    title_quality: float        # 0-100
    audience_fit: float         # 0-100
    composite_score: float      # 0-100  (weighted blend)
    suggested_title: str
    suggested_tags: list[str] = field(default_factory=list)
    reasoning: str = ''
    is_viable: bool = False
    scored_by_ai: bool = True   # False = fallback heuristic

    def summary(self) -> str:
        flag = 'AI' if self.scored_by_ai else 'heuristic'
        return (
            f'[{flag}] "{self.suggested_title[:55]}" '
            f'score={self.composite_score:.0f} viable={self.is_viable}'
        )


_SYSTEM_PROMPT = """\
You are an elite content strategist for a Minecraft YouTube Shorts channel.
Your job: analyse Reddit posts and predict their performance as 60-second Shorts.

Scoring rubric (all 0-100):
  viral_potential    — hook strength, meme-ability, emotional resonance, shareability
  narrative_strength — story arc clarity, conflict/resolution potential, relatability
  title_quality      — original title effectiveness for Shorts (concise, curiosity gap)
  audience_fit       — fit for 13-25 yr Minecraft fans on mobile

composite_score = 0.35*viral + 0.25*narrative + 0.20*title + 0.20*audience

Also supply:
  suggested_title — punchy YT Shorts title ≤60 chars, no ALL CAPS, no excessive punctuation
  suggested_tags  — 6-8 relevant tags (list of strings)
  reasoning       — one crisp sentence explaining the top signal for or against
  is_viable       — true if composite_score ≥ 62

Respond ONLY with a valid JSON array, one object per post, same order as input.
"""

_USER_TEMPLATE = """\
Analyse these {n} Reddit posts for Minecraft Shorts potential:

{posts_json}

Return a JSON array of {n} assessment objects.
"""

VIABILITY_THRESHOLD = 62
BATCH_SIZE = 10


class Orient:
    """
    ORIENT phase: Claude-powered batch analysis with heuristic fallback.

    Processes signals in batches of BATCH_SIZE to stay well within token
    limits while maximising throughput.  Falls back to rule-based scoring
    if the API call fails so the pipeline never stalls.
    """

    MODEL = 'claude-sonnet-4-6'

    def __init__(self, config):
        self.config = config
        self.client = anthropic.Anthropic()

    # --------------------------------------------------------------- private

    def _posts_payload(self, signals: list[Signal]) -> str:
        return json.dumps([
            {
                'title': s.title,
                'body_preview': s.body[:200],
                'score': s.score,
                'velocity_upvotes_per_hour': s.velocity,
                'comment_velocity_per_hour': s.comment_velocity,
                'engagement_rate': s.engagement_rate,
                'momentum_upvotes_per_hour': s.momentum,
                'subreddit': s.subreddit,
            }
            for s in signals
        ], indent=2)

    def _parse_response(self, text: str) -> list[dict]:
        text = text.strip()
        # Strip markdown code fences if present
        for fence in ('```json', '```'):
            if text.startswith(fence):
                text = text[len(fence):]
                break
        if text.endswith('```'):
            text = text[:-3]
        return json.loads(text.strip())

    def _ai_batch(self, signals: list[Signal]) -> list[Assessment]:
        payload = self._posts_payload(signals)
        response = self.client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=[{
                'role': 'user',
                'content': _USER_TEMPLATE.format(n=len(signals), posts_json=payload),
            }],
        )
        results = self._parse_response(response.content[0].text)

        assessments = []
        for signal, r in zip(signals, results):
            composite = round(
                0.35 * r.get('viral_potential', 0)
                + 0.25 * r.get('narrative_strength', 0)
                + 0.20 * r.get('title_quality', 0)
                + 0.20 * r.get('audience_fit', 0),
                1,
            )
            assessments.append(Assessment(
                signal=signal,
                viral_potential=r.get('viral_potential', 0),
                narrative_strength=r.get('narrative_strength', 0),
                title_quality=r.get('title_quality', 0),
                audience_fit=r.get('audience_fit', 0),
                composite_score=composite,
                suggested_title=r.get('suggested_title', signal.title)[:60],
                suggested_tags=r.get('suggested_tags', ['Minecraft', 'Shorts']),
                reasoning=r.get('reasoning', ''),
                is_viable=composite >= VIABILITY_THRESHOLD,
                scored_by_ai=True,
            ))
        return assessments

    def _heuristic_fallback(self, signal: Signal) -> Assessment:
        """Rule-based scoring used when the AI call fails."""
        vel_score = min(signal.velocity / 300, 1.0) * 100
        eng_score = min(signal.engagement_rate / 0.3, 1.0) * 100
        raw_score = min(signal.score / 5000, 1.0) * 100
        composite = round(0.4 * vel_score + 0.35 * raw_score + 0.25 * eng_score, 1)
        return Assessment(
            signal=signal,
            viral_potential=vel_score,
            narrative_strength=raw_score * 0.8,
            title_quality=50.0,
            audience_fit=60.0,
            composite_score=composite,
            suggested_title=signal.title[:60],
            suggested_tags=['Minecraft', 'Shorts'],
            reasoning='Heuristic fallback — AI unavailable.',
            is_viable=composite >= VIABILITY_THRESHOLD,
            scored_by_ai=False,
        )

    # ---------------------------------------------------------------- public

    def analyse(self, signals: list[Signal]) -> list[Assessment]:
        """Analyse all signals in batches; return assessments sorted by composite score."""
        if not signals:
            return []

        print(f'[ORIENT] Analysing {len(signals)} signals via {self.MODEL}')
        assessments: list[Assessment] = []

        for i in range(0, len(signals), BATCH_SIZE):
            batch = signals[i:i + BATCH_SIZE]
            try:
                batch_results = self._ai_batch(batch)
                assessments.extend(batch_results)
                print(f'  batch {i // BATCH_SIZE + 1}: {len(batch_results)} assessed by AI')
            except Exception as exc:
                print(f'  [WARN] AI batch failed: {exc} — using heuristic fallback')
                for signal in batch:
                    assessments.append(self._heuristic_fallback(signal))

        assessments.sort(key=lambda a: a.composite_score, reverse=True)
        viable = sum(1 for a in assessments if a.is_viable)
        print(f'[ORIENT] {viable}/{len(assessments)} signals are viable (threshold ≥ {VIABILITY_THRESHOLD})')
        return assessments

    def synthesise_trends(self, assessments: list[Assessment]) -> dict:
        """Aggregate trend signals across all assessments for downstream logging."""
        from collections import Counter
        viable = [a for a in assessments if a.is_viable]
        all_tags: list[str] = []
        for a in viable:
            all_tags.extend(a.suggested_tags)

        tag_freq = Counter(all_tags).most_common(10)
        scores = [a.composite_score for a in assessments]
        avg_score = round(sum(scores) / max(len(scores), 1), 1)

        return {
            'cycle_viable': len(viable),
            'cycle_total': len(assessments),
            'avg_composite_score': avg_score,
            'top_5_scores': sorted(scores, reverse=True)[:5],
            'trending_tags': [t for t, _ in tag_freq],
            'viability_ratio': round(len(viable) / max(len(assessments), 1), 2),
        }
