import logging

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class ViagogoCrawler(BaseCrawler):
    platform_name = "viagogo"
    platform_region = "intl"
    base_url = "https://www.viagogo.com"

    SEARCH_URL = "https://www.viagogo.com/search"

    KEYWORDS = [
        "K-pop", "concert", "ticket", "BTS", "BLACKPINK",
        "football", "soccer", "NBA", "premier league",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        params = {"searchTerm": query}
        resp = await self._fetch(self.SEARCH_URL, params=params)
        if not resp:
            logger.info("[viagogo] No response for query: %s", query)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div[class*='search-result'], a[class*='EventCard'], div[class*='eventCard']")
        for item in items:
            try:
                title_el = item.select_one("h3, span[class*='title'], div[class*='name']")
                price_el = item.select_one("span[class*='price'], div[class*='Price']")
                link_el = item.select_one("a[href]") or item
                link = link_el.get("href", "")
                if title_el:
                    price_text = price_el.get_text(strip=True) if price_el else "0"
                    results.append(self._build_result(
                        title=title_el.get_text(strip=True),
                        price=self.parse_price(price_text),
                        seller_username="",
                        listing_url=f"{self.base_url}{link}" if link.startswith("/") else link,
                        category=category,
                        raw_html=str(item),
                    ))
            except Exception as e:
                logger.debug("[viagogo] Parse error: %s", e)
        logger.info("[viagogo] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1")
        price_el = soup.select_one("span[class*='price']")
        return {
            "title": title_el.get_text(strip=True) if title_el else "",
            "price": self.parse_price(price_el.get_text(strip=True)) if price_el else 0,
            "seller_username": "",
            "description": "",
            "raw_html": resp.text[:5000],
        }
