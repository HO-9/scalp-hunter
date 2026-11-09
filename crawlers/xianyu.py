import logging

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class XianyuCrawler(BaseCrawler):
    platform_name = "xianyu"
    platform_region = "intl"
    base_url = "https://www.goofish.com"

    SEARCH_URL = "https://www.goofish.com/search"

    KEYWORDS = [
        "门票", "演唱会", "演出", "票", "转让",
        "K-POP", "BTS", "BLACKPINK", "concert", "ticket",
        "韩国", "首尔",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        params = {"q": query}
        resp = await self._fetch(self.SEARCH_URL, params=params)
        if not resp:
            logger.info("[xianyu] No response for query: %s", query)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("div[class*='item'], a[class*='card'], div[class*='Feed']")
        for item in items:
            try:
                title_el = item.select_one("div[class*='title'], span[class*='title'], h3")
                price_el = item.select_one("span[class*='price'], div[class*='price']")
                link_el = item.select_one("a[href]") or item
                link = link_el.get("href", "")
                if title_el:
                    price_text = price_el.get_text(strip=True) if price_el else "0"
                    if "元" not in price_text and "¥" not in price_text:
                        price_text = f"{price_text}元"
                    results.append(self._build_result(
                        title=title_el.get_text(strip=True),
                        price=self.parse_price(price_text),
                        seller_username="",
                        listing_url=f"{self.base_url}{link}" if link.startswith("/") else link,
                        category=category,
                        raw_html=str(item),
                    ))
            except Exception as e:
                logger.debug("[xianyu] Parse error: %s", e)
        logger.info("[xianyu] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1, div[class*='Title']")
        price_el = soup.select_one("span[class*='price']")
        seller_el = soup.select_one("span[class*='nick'], div[class*='Seller']")
        desc_el = soup.select_one("div[class*='desc'], div[class*='Detail']")
        price_text = price_el.get_text(strip=True) if price_el else "0"
        if "元" not in price_text and "¥" not in price_text:
            price_text = f"{price_text}元"
        return {
            "title": title_el.get_text(strip=True) if title_el else "",
            "price": self.parse_price(price_text),
            "seller_username": seller_el.get_text(strip=True) if seller_el else "",
            "description": desc_el.get_text(strip=True) if desc_el else "",
            "raw_html": resp.text[:5000],
        }
