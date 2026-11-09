import logging
import os

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class TicketmasterCrawler(BaseCrawler):
    platform_name = "ticketmaster"
    platform_region = "intl"
    base_url = "https://app.ticketmaster.com"

    DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

    KEYWORDS = [
        "concert", "ticket", "K-pop", "BTS", "BLACKPINK",
        "aespa", "NewJeans", "Stray Kids", "SEVENTEEN",
    ]

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("TICKETMASTER_API_KEY", "")

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        if not self.api_key:
            logger.warning("[ticketmaster] No API key configured")
            return results

        params = {
            "apikey": self.api_key,
            "keyword": query,
            "size": 50,
            "sort": "date,asc",
        }
        if category == "concert":
            params["classificationName"] = "music"
        elif category == "sports":
            params["classificationName"] = "sports"

        data = await self._fetch_json(self.DISCOVERY_URL, params=params)
        if not data or "_embedded" not in data:
            logger.info("[ticketmaster] No results for query: %s", query)
            return results

        for event in data["_embedded"].get("events", []):
            try:
                price_ranges = event.get("priceRanges", [{}])
                min_price = price_ranges[0].get("min", 0) if price_ranges else 0
                max_price = price_ranges[0].get("max", 0) if price_ranges else 0
                currency = price_ranges[0].get("currency", "USD") if price_ranges else "USD"
                price_str = f"${max_price}" if currency == "USD" else f"{max_price} {currency}"
                results.append(self._build_result(
                    title=event.get("name", ""),
                    price=self.parse_price(price_str),
                    seller_username="ticketmaster_resale",
                    listing_url=event.get("url", ""),
                    category=category,
                ))
            except Exception as e:
                logger.debug("[ticketmaster] Parse error: %s", e)
        logger.info("[ticketmaster] Found %d events for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        event_id = url.rstrip("/").split("/")[-1]
        api_url = f"{self.DISCOVERY_URL.replace('events.json', f'events/{event_id}.json')}"
        params = {"apikey": self.api_key} if self.api_key else {}
        data = await self._fetch_json(api_url, params=params)
        if not data:
            return {}
        return {
            "title": data.get("name", ""),
            "price": 0,
            "seller_username": "",
            "description": data.get("info", ""),
            "raw_html": "",
        }
