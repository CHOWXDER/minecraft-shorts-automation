import praw
import os
from dotenv import load_dotenv

load_dotenv()

class RedditScraper:
    def __init__(self):
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )

    def get_top_posts(self, subreddit_name, limit=10, time_filter='week'):
        subreddit = self.reddit.subreddit(subreddit_name)
        posts = subreddit.top(time_filter=time_filter, limit=limit)
        
        results = []
        for post in posts:
            results.append({
                'title': post.title,
                'selftext': post.selftext,
                'score': post.score,
                'url': post.url,
                'author': post.author.name if post.author else 'Deleted',
                'created_utc': post.created_utc,
                'subreddit': post.subreddit.display_name
            })
        
        return results

    def filter_quality_posts(self, posts, min_score=500):
        return [post for post in posts if post['score'] >= min_score]

    def get_minecraft_stories(self):
        minecraft_subreddits = ['Minecraft', 'MinecraftStories', 'mcservers']
        all_posts = []
        
        for subreddit in minecraft_subreddits:
            try:
                posts = self.get_top_posts(subreddit, limit=5)
                all_posts.extend(posts)
            except Exception as e:
                print(f"Error fetching from {subreddit}: {e}")
        
        return self.filter_quality_posts(all_posts)

if __name__ == '__main__':
    scraper = RedditScraper()
    posts = scraper.get_minecraft_stories()
    for post in posts:
        print(f"Title: {post['title']}")
        print(f"Score: {post['score']}")
        print(f"Author: {post['author']}")
        print("---")
