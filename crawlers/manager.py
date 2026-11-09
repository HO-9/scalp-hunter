import asyncio
import logging
from hashlib import md5

from .base import BaseCrawler
from .bungae import BungaeCrawler
from .danggeun import DanggeunCrawler
from .instagram import InstagramCrawler
from .joongna import JoongnaCrawler
from .ticketmaster import TicketmasterCrawler
from .twitter import TwitterCrawler
from .viagogo import ViagogoCrawler
from .xianyu import XianyuCrawler
from .yahoo_jp import YahooJPCrawler

logger = logging.getLogger(__name__)


class CrawlerManager:
    def __init__(self):
        self._crawlers: dict[str, BaseCrawler] = {}
        self._register_defaults()

    def _register_defaults(self):
        for cls in [
            DanggeunCrawler,
            BungaeCrawler,
            JoongnaCrawler,
            TicketmasterCrawler,
            ViagogoCrawler,
            YahooJPCrawler,
            XianyuCrawler,
            TwitterCrawler,
            InstagramCrawler,
        ]:
            crawler = cls()
            self._crawlers[crawler.platform_name] = crawler

    def register(self, crawler: BaseCrawler):
        self._crawlers[crawler.platform_name] = crawler

    def get_crawler(self, name: str) -> BaseCrawler | None:
        return self._crawlers.get(name)

    def list_crawlers(self) -> list[dict]:
        return [
            {
                "name": c.platform_name,
                "region": c.platform_region,
                "base_url": c.base_url,
            }
            for c in self._crawlers.values()
        ]

    @staticmethod
    def _listing_hash(listing: dict) -> str:
        key = f"{listing['platform']}:{listing['listing_url']}:{listing['title']}"
        return md5(key.encode()).hexdigest()

    def _deduplicate(self, listings: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for listing in listings:
            h = self._listing_hash(listing)
            if h not in seen:
                seen.add(h)
                unique.append(listing)
        return unique

    async def search_all(
        self,
        query: str,
        category: str = "all",
        platforms: list[str] | None = None,
        region: str | None = None,
    ) -> list[dict]:
        crawlers = list(self._crawlers.values())
        if platforms:
            crawlers = [c for c in crawlers if c.platform_name in platforms]
        if region:
            crawlers = [c for c in crawlers if c.platform_region == region]

        if not crawlers:
            logger.warning("No crawlers match the filter")
            return []

        logger.info(
            "Searching %d platforms for '%s' (category=%s)",
            len(crawlers), query, category,
        )

        async def _safe_search(crawler: BaseCrawler) -> list[dict]:
            try:
                return await crawler.search_tickets(query, category)
            except Exception as e:
                logger.error("[%s] Unhandled error: %s", crawler.platform_name, e)
                return []

        tasks = [_safe_search(c) for c in crawlers]
        results = await asyncio.gather(*tasks)

        all_listings = []
        for listings in results:
            all_listings.extend(listings)

        deduplicated = self._deduplicate(all_listings)
        logger.info("Total: %d listings (%d unique)", len(all_listings), len(deduplicated))
        return deduplicated

    async def search_platform(
        self, platform: str, query: str, category: str = "all"
    ) -> list[dict]:
        crawler = self._crawlers.get(platform)
        if not crawler:
            logger.warning("Unknown platform: %s", platform)
            return []
        try:
            return await crawler.search_tickets(query, category)
        except Exception as e:
            logger.error("[%s] Error: %s", platform, e)
            return []
