"""
reddit_scraper.py — Anonymous Reddit JSON scraping. No API key required.

Uses Reddit's public .json endpoint — zero accounts, zero credentials.
Rate-limited to ~1 req/sec to be polite.
"""

import time
import requests

_HEADERS = {"User-Agent": "MinecraftShortsBot/1.0 (local automation)"}
_DELAY   = 1.1  # seconds between requests (Reddit rate limit: ~60/min)


class RedditScraper:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def get_top_posts(
        self,
        subreddit_name: str,
        limit: int = 25,
        time_filter: str = "day",
    ) -> list[dict]:
        url = (
            f"https://www.reddit.com/r/{subreddit_name}/top.json"
            f"?t={time_filter}&limit={limit}"
        )
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            print(f"[RedditScraper] Failed to fetch r/{subreddit_name}: {exc}")
            return []

        results = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            results.append({
                "title":         p.get("title", ""),
                "selftext":      p.get("selftext", ""),
                "score":         p.get("score", 0),
                "num_comments":  p.get("num_comments", 0),
                "url":           p.get("url", ""),
                "author":        p.get("author", "Deleted"),
                "created_utc":   p.get("created_utc", 0.0),
                "subreddit":     p.get("subreddit", subreddit_name),
                "upvote_ratio":  p.get("upvote_ratio", 0.0),
                "is_self":       p.get("is_self", False),
            })

        time.sleep(_DELAY)
        return results

    def filter_quality_posts(self, posts: list[dict], min_score: int = 500) -> list[dict]:
        return [p for p in posts if p["score"] >= min_score]

    def get_minecraft_stories(self) -> list[dict]:
        subreddits = ["Minecraft", "MinecraftStories", "mcservers"]
        all_posts: list[dict] = []

        for sub in subreddits:
            posts = self.get_top_posts(sub, limit=25)
            all_posts.extend(posts)
            print(f"[RedditScraper] r/{sub}: {len(posts)} posts fetched")

        filtered = self.filter_quality_posts(all_posts)
        print(f"[RedditScraper] {len(filtered)}/{len(all_posts)} posts passed quality filter")
        return filtered


if __name__ == "__main__":
    scraper = RedditScraper()
    posts   = scraper.get_minecraft_stories()
    for post in posts[:5]:
        print(f"Title: {post['title']}")
        print(f"Score: {post['score']}  Comments: {post['num_comments']}")
        print("---")
