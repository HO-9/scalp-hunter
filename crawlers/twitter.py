import logging
import os
import re

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class TwitterCrawler(BaseCrawler):
    platform_name = "twitter"
    platform_region = "social"
    base_url = "https://api.twitter.com"

    SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"

    KEYWORDS_KR = [
        "티켓 양도", "티켓 판매", "콘서트 티켓", "입장권 양도",
        "표 팝니다", "좌석 양도", "암표", "#티켓양도",
    ]
    KEYWORDS_EN = [
        "selling ticket", "tickets for sale", "concert ticket",
        "#ticketforsale", "#sellingtickets", "DM for tickets",
    ]

    PRICE_PATTERN = re.compile(
        r"(?:₩|원|만\s*원|\$|USD)\s*[\d,.]+|[\d,.]+\s*(?:원|만\s*원|₩|\$|USD)"
    )

    def __init__(self, bearer_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN", "")

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        if not self.bearer_token:
            logger.warning("[twitter] No bearer token configured")
            return results

        search_query = f'{query} (티켓 OR ticket OR 양도 OR selling) -is:retweet'
        params = {
            "query": search_query,
            "max_results": 100,
            "tweet.fields": "author_id,created_at,text",
            "expansions": "author_id",
            "user.fields": "username",
        }
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        data = await self._fetch_json(self.SEARCH_URL, params=params, headers=headers)
        if not data or "data" not in data:
            logger.info("[twitter] No results for query: %s", query)
            return results

        users_map = {}
        if "includes" in data and "users" in data["includes"]:
            for u in data["includes"]["users"]:
                users_map[u["id"]] = u.get("username", "")

        for tweet in data.get("data", []):
            try:
                text = tweet.get("text", "")
                price_match = self.PRICE_PATTERN.search(text)
                price = self.parse_price(price_match.group()) if price_match else 0
                author_id = tweet.get("author_id", "")
                username = users_map.get(author_id, author_id)
                tweet_id = tweet.get("id", "")
                results.append(self._build_result(
                    title=text[:120],
                    price=price,
                    seller_username=f"@{username}",
                    listing_url=f"https://x.com/{username}/status/{tweet_id}",
                    category=category,
                ))
            except Exception as e:
                logger.debug("[twitter] Parse error: %s", e)
        logger.info("[twitter] Found %d tweets for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        parts = url.rstrip("/").split("/")
        tweet_id = parts[-1] if parts else ""
        if not self.bearer_token or not tweet_id:
            return {}
        api_url = f"https://api.twitter.com/2/tweets/{tweet_id}"
        params = {
            "tweet.fields": "author_id,created_at,text",
            "expansions": "author_id",
            "user.fields": "username,public_metrics",
        }
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        data = await self._fetch_json(api_url, params=params, headers=headers)
        if not data or "data" not in data:
            return {}
        tweet = data["data"]
        username = ""
        if "includes" in data and "users" in data["includes"]:
            username = data["includes"]["users"][0].get("username", "")
        return {
            "title": tweet.get("text", "")[:120],
            "price": 0,
            "seller_username": f"@{username}",
            "description": tweet.get("text", ""),
            "raw_html": "",
        }
