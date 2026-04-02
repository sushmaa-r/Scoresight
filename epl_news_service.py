import feedparser
from typing import List, Dict

class EPLNewsService:
    def __init__(self):
        self.rss_feeds = [
            'https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml',
            'https://www.skysports.com/rss/12040',
            'https://www.theguardian.com/football/premierleague/rss'
        ]
    
    def fetch_rss_news(self) -> List[Dict]:
        """Fetch latest Premier League news from RSS feeds"""
        all_articles = []

        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:8]:
                    article = {
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.get('summary', entry.get('description', '')),
                        'published': entry.get('published', ''),
                        'source': feed.feed.get('title', 'Unknown Source')
                    }
                    all_articles.append(article)
            except Exception as e:
                print(f"Error fetching RSS feed {feed_url}: {e}")
                continue

        return all_articles

    def get_all_news(self, limit: int = 20) -> List[Dict]:
        """Combine all sources and return latest news"""
        try:
            all_articles = self.fetch_rss_news()
            unique = {a['title']: a for a in all_articles}  # remove duplicates
            news_list = list(unique.values())[:limit]
            return news_list
        except Exception as e:
            print(f"Error in get_all_news: {e}")
            return []

# Global instance
news_service = EPLNewsService()
