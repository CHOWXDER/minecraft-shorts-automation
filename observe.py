"""
OODA Phase 1 — OBSERVE
Multi-source signal collection with velocity, engagement, and momentum tracking.
"""

import time
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from reddit_scraper import RedditScraper


@dataclass
class Signal:
    source: str
    content_id: str
    title: str
    body: str
    score: int
    num_comments: int
    velocity: float          # upvotes/hour since creation
    comment_velocity: float  # comments/hour since creation
    engagement_rate: float   # comments / max(score, 1)
    score_delta: int         # score change since last observation
    momentum: float          # score_delta / hours_since_last_seen
    created_utc: float
    url: str
    author: str
    subreddit: str
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop('raw_data', None)
        return d


class Observer:
    """
    OBSERVE phase: Collect, enrich, and de-duplicate signals from Reddit.

    Tracks post state across cycles to compute momentum — the rate of
    score change between observations — which is a leading indicator of
    virality more predictive than raw score alone.
    """

    STATE_FILE = 'ooda_state.json'

    def __init__(self, config):
        self.config = config
        self.scraper = RedditScraper()
        self._load_state()

    # ------------------------------------------------------------------ state

    def _load_state(self):
        if os.path.exists(self.STATE_FILE):
            with open(self.STATE_FILE) as f:
                self.state = json.load(f)
        else:
            self.state = {'seen_posts': {}, 'cycle_count': 0}

    def _save_state(self):
        with open(self.STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    # --------------------------------------------------------------- metrics

    def _velocity(self, score: int, created_utc: float) -> float:
        age_hours = max((time.time() - created_utc) / 3600, 0.1)
        return round(score / age_hours, 2)

    def _comment_velocity(self, num_comments: int, created_utc: float) -> float:
        age_hours = max((time.time() - created_utc) / 3600, 0.1)
        return round(num_comments / age_hours, 2)

    def _engagement_rate(self, num_comments: int, score: int) -> float:
        return round(num_comments / max(score, 1), 4)

    def _momentum(self, content_id: str, current_score: int) -> tuple[int, float]:
        """Returns (score_delta, momentum_per_hour)."""
        prev = self.state['seen_posts'].get(content_id)
        if not prev:
            return 0, 0.0
        delta = current_score - prev['score']
        hours_elapsed = max((time.time() - prev['last_seen']) / 3600, 0.1)
        return delta, round(delta / hours_elapsed, 2)

    # ----------------------------------------------------------------- gather

    def gather(self) -> list[Signal]:
        """
        Scrape configured subreddits, enrich each post with derived metrics,
        and return a deduplicated list of Signals sorted by velocity.
        """
        self.state['cycle_count'] = self.state.get('cycle_count', 0) + 1
        print(f'[OBSERVE] Cycle #{self.state["cycle_count"]} — scraping {len(self.config.SUBREDDITS)} subreddits')

        raw_posts: list[dict] = []
        for sub in self.config.SUBREDDITS:
            try:
                posts = self.scraper.get_top_posts(sub, limit=20, time_filter='day')
                raw_posts.extend(posts)
                print(f'  {sub}: {len(posts)} posts')
            except Exception as exc:
                print(f'  [WARN] {sub}: {exc}')

        signals: list[Signal] = []
        seen_ids: set[str] = set()

        for post in raw_posts:
            content_id = post.get('url') or post['title']
            if content_id in seen_ids:
                continue
            seen_ids.add(content_id)

            score = post.get('score', 0)
            num_comments = post.get('num_comments', 0)
            created_utc = post.get('created_utc', time.time())
            score_delta, momentum = self._momentum(content_id, score)

            signal = Signal(
                source='reddit',
                content_id=content_id,
                title=post.get('title', ''),
                body=post.get('selftext', '')[:2000],
                score=score,
                num_comments=num_comments,
                velocity=self._velocity(score, created_utc),
                comment_velocity=self._comment_velocity(num_comments, created_utc),
                engagement_rate=self._engagement_rate(num_comments, score),
                score_delta=score_delta,
                momentum=momentum,
                created_utc=created_utc,
                url=post.get('url', ''),
                author=post.get('author', 'Unknown'),
                subreddit=post.get('subreddit', ''),
                raw_data=post,
            )
            signals.append(signal)

            self.state['seen_posts'][content_id] = {
                'score': score,
                'last_seen': time.time(),
            }

        self._save_state()

        signals.sort(key=lambda s: s.velocity, reverse=True)
        print(f'[OBSERVE] {len(signals)} unique signals collected')
        return signals
