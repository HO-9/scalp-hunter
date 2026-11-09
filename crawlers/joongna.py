import logging

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class JoongnaCrawler(BaseCrawler):
    platform_name = "joongna"
    platform_region = "kr"
    base_url = "https://web.joongna.com"

    SEARCH_URL = "https://web.joongna.com/search/{query}"

    KEYWORDS = [
        "티켓", "콘서트", "공연", "양도", "입장권",
        "KTX 표", "SRT 표", "스탠딩", "VIP석",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        search_url = self.SEARCH_URL.format(query=query)
        resp = await self._fetch(search_url)
        if not resp:
            logger.info("[joongna] No response for query: %s", query)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("a.product-card, li.search-result-item, div[class*='ProductCard']")
        for item in items:
            try:
                title_el = item.select_one("h2, span[class*='title'], div[class*='Title']")
                price_el = item.select_one("span[class*='price'], div[class*='Price']")
                link = item.get("href", "")
                if title_el:
                    results.append(self._build_result(
                        title=title_el.get_text(strip=True),
                        price=self.parse_price(price_el.get_text(strip=True)) if price_el else 0,
                        seller_username="",
                        listing_url=f"{self.base_url}{link}" if link.startswith("/") else link,
                        category=category,
                        raw_html=str(item),
                    ))
            except Exception as e:
                logger.debug("[joongna] Parse error: %s", e)
        logger.info("[joongna] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, div[class*='Title']")
        price_el = soup.select_one("span[class*='price'], div[class*='Price']")
        seller_el = soup.select_one("span[class*='nickname'], div[class*='Seller']")
        desc_el = soup.select_one("div[class*='description'], div[class*='Detail']")
        return {
            "title": title_el.get_text(strip=True) if title_el else "",
            "price": self.parse_price(price_el.get_text(strip=True)) if price_el else 0,
            "seller_username": seller_el.get_text(strip=True) if seller_el else "",
            "description": desc_el.get_text(strip=True) if desc_el else "",
            "raw_html": resp.text[:5000],
        }
