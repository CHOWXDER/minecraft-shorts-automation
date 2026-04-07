import os
import praw
from dotenv import load_dotenv

load_dotenv()


class RedditScraper:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT', 'MinecraftShortsBot/1.0'),
        )

    def get_top_posts(self, subreddit_name: str, limit: int = 20, time_filter: str = 'day') -> list[dict]:
        subreddit = self.reddit.subreddit(subreddit_name)
        posts = subreddit.top(time_filter=time_filter, limit=limit)

        results = []
        for post in posts:
            results.append({
                'title': post.title,
                'selftext': post.selftext,
                'score': post.score,
                'num_comments': post.num_comments,
                'url': post.url,
                'author': post.author.name if post.author else 'Deleted',
                'created_utc': post.created_utc,
                'subreddit': post.subreddit.display_name,
                'upvote_ratio': post.upvote_ratio,
                'is_self': post.is_self,
            })
        return results

    def filter_quality_posts(self, posts: list[dict], min_score: int = 500) -> list[dict]:
        return [p for p in posts if p['score'] >= min_score]

    def get_minecraft_stories(self) -> list[dict]:
        subreddits = ['Minecraft', 'MinecraftStories', 'mcservers']
        all_posts: list[dict] = []

        for sub in subreddits:
            try:
                posts = self.get_top_posts(sub, limit=20)
                all_posts.extend(posts)
            except Exception as exc:
                print(f'[RedditScraper] Error fetching from {sub}: {exc}')

        return self.filter_quality_posts(all_posts)


if __name__ == '__main__':
    scraper = RedditScraper()
    posts = scraper.get_minecraft_stories()
    for post in posts:
        print(f"Title: {post['title']}")
        print(f"Score: {post['score']}  Comments: {post['num_comments']}")
        print(f"Author: {post['author']}")
        print('---')
