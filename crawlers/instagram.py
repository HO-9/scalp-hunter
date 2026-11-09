import logging
import re

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class InstagramCrawler(BaseCrawler):
    platform_name = "instagram"
    platform_region = "social"
    base_url = "https://www.instagram.com"

    HASHTAG_URL = "https://www.instagram.com/explore/tags/{tag}/"

    HASHTAGS = [
        "티켓양도", "콘서트티켓", "티켓팝니다", "입장권양도",
        "ticketforsale", "sellingtickets", "concertticket",
    ]

    PRICE_PATTERN = re.compile(
        r"(?:₩|원|만\s*원|\$|USD)\s*[\d,.]+|[\d,.]+\s*(?:원|만\s*원|₩|\$|USD)"
    )

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        tag = query.replace(" ", "").replace("#", "")
        url = self.HASHTAG_URL.format(tag=tag)
        resp = await self._fetch(url)
        if not resp:
            logger.info("[instagram] No response for tag: %s", tag)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        scripts = soup.select("script[type='application/ld+json']")
        for script in scripts:
            try:
                import json
                data = json.loads(script.string or "{}")
                if isinstance(data, dict) and "caption" in data:
                    caption = data.get("caption", "")
                    author = data.get("author", {}).get("name", "")
                    price_match = self.PRICE_PATTERN.search(caption)
                    price = self.parse_price(price_match.group()) if price_match else 0
                    post_url = data.get("url", "")
                    results.append(self._build_result(
                        title=caption[:120],
                        price=price,
                        seller_username=f"@{author}",
                        listing_url=post_url,
                        category=category,
                    ))
            except Exception as e:
                logger.debug("[instagram] Parse error: %s", e)

        meta_tags = soup.select("meta[property='og:description']")
        for meta in meta_tags:
            content = meta.get("content", "")
            if any(kw in content for kw in self.HASHTAGS):
                price_match = self.PRICE_PATTERN.search(content)
                price = self.parse_price(price_match.group()) if price_match else 0
                results.append(self._build_result(
                    title=content[:120],
                    price=price,
                    seller_username="",
                    listing_url=url,
                    category=category,
                ))

        logger.info("[instagram] Found %d posts for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        desc_meta = soup.select_one("meta[property='og:description']")
        title_meta = soup.select_one("meta[property='og:title']")
        return {
            "title": title_meta.get("content", "") if title_meta else "",
            "price": 0,
            "seller_username": "",
            "description": desc_meta.get("content", "") if desc_meta else "",
            "raw_html": resp.text[:5000],
        }
