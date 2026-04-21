import re
import time
import xml.etree.ElementTree as ET
import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}
_DELAY = 1.2


class RedditScraper:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def get_top_posts(self, subreddit_name: str) -> list[dict]:
        # Try 1: www.reddit.com JSON
        posts = self._json(f"https://www.reddit.com/r/{subreddit_name}/top.json?t=day&limit=25", subreddit_name)
        if posts:
            return posts

        # Try 2: old.reddit.com JSON (less strict CDN rules)
        posts = self._json(f"https://old.reddit.com/r/{subreddit_name}/top.json?t=day&limit=25", subreddit_name)
        if posts:
            return posts

        # Try 3: RSS feed (no auth needed, just XML)
        posts = self._rss(subreddit_name)
        if posts:
            return posts

        print(f"[Scraper] r/{subreddit_name} all methods failed")
        return []

    def _json(self, url: str, subreddit_name: str) -> list[dict]:
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for child in data.get("data", {}).get("children", []):
                p = child.get("data", {})
                text = p.get("selftext", "").strip()
                if text in ("[removed]", "[deleted]", ""):
                    continue
                results.append({
                    "title":        p.get("title", ""),
                    "text":         text,
                    "score":        p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                    "subreddit":    subreddit_name,
                    "url":          p.get("url", ""),
                })
            time.sleep(_DELAY)
            if results:
                print(f"[Scraper] r/{subreddit_name}: {len(results)} posts (JSON)")
            return results
        except Exception:
            return []

    def _rss(self, subreddit_name: str) -> list[dict]:
        try:
            url  = f"https://www.reddit.com/r/{subreddit_name}/top.rss?t=day&limit=25"
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns   = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            for entry in root.findall("atom:entry", ns):
                title   = entry.findtext("atom:title", "", ns).strip()
                content = entry.findtext("atom:content", "", ns) or ""
                text    = re.sub(r"<[^>]+>", " ", content).strip()
                text    = re.sub(r"\s+", " ", text)
                if len(text) < 80:
                    continue
                results.append({
                    "title":     title,
                    "text":      text,
                    "score":     500,   # RSS doesn't expose score
                    "subreddit": subreddit_name,
                    "url":       "",
                })
            time.sleep(_DELAY)
            if results:
                print(f"[Scraper] r/{subreddit_name}: {len(results)} posts (RSS)")
            return results
        except Exception:
            return []

    def get_minecraft_stories(self) -> list[dict]:
        all_posts: list[dict] = []
        for sub in ["Minecraft", "MinecraftStories", "mcservers"]:
            posts = self.get_top_posts(sub)
            all_posts.extend(posts)
            print(f"[Scraper] r/{sub}: {len(posts)} posts")
        quality = [p for p in all_posts if p["score"] >= 500 and len(p["text"]) > 50]
        print(f"[Scraper] {len(quality)}/{len(all_posts)} passed quality filter")
        return quality


if __name__ == "__main__":
    scraper = RedditScraper()
    for sub in ["AmItheAsshole", "tifu", "relationship_advice"]:
        posts = scraper.get_top_posts(sub)
        print(f"r/{sub}: {len(posts)} posts fetched")
        if posts:
            print(f"  Sample: {posts[0]['title'][:70]}")
