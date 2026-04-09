import time
import requests

_HEADERS = {"User-Agent": "MinecraftBot/1.0"}
_DELAY   = 1.2   # seconds between requests — stay under Reddit rate limit


class RedditScraper:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def get_top_posts(self, subreddit_name: str) -> list[dict]:
        url = f"https://www.reddit.com/r/{subreddit_name}/top.json?t=day&limit=25"
        try:
            resp = self._session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[Scraper] r/{subreddit_name} failed: {e}")
            return []

        results = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            results.append({
                "title":     p.get("title", ""),
                "text":      p.get("selftext", ""),   # "text" used everywhere downstream
                "score":     p.get("score", 0),
                "subreddit": subreddit_name,
                "url":       p.get("url", ""),
            })

        time.sleep(_DELAY)
        return results

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
    for p in RedditScraper().get_minecraft_stories()[:3]:
        print(f"[{p['score']}] {p['title']}")
