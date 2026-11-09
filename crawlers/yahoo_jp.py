import logging

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class YahooJPCrawler(BaseCrawler):
    platform_name = "yahoo_jp"
    platform_region = "intl"
    base_url = "https://auctions.yahoo.co.jp"

    SEARCH_URL = "https://auctions.yahoo.co.jp/search/search"

    KEYWORDS = [
        "チケット", "コンサート", "公演", "入場券", "ライブ",
        "K-POP", "BTS", "BLACKPINK", "ticket", "concert",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        params = {
            "p": query,
            "va": query,
            "auccat": "22260",
            "tab_ex": "commerce",
            "ei": "utf-8",
            "n": 50,
        }
        resp = await self._fetch(self.SEARCH_URL, params=params)
        if not resp:
            logger.info("[yahoo_jp] No response for query: %s", query)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.select("li.Product, div.Result__body, ul.Products__items li")
        for item in items:
            try:
                title_el = item.select_one("h3 a, a.Product__titleLink, a[class*='title']")
                price_el = item.select_one("span.Product__priceValue, span[class*='price']")
                if title_el:
                    link = title_el.get("href", "")
                    price_text = price_el.get_text(strip=True) if price_el else "0"
                    if "円" not in price_text and "¥" not in price_text:
                        price_text = f"¥{price_text}"
                    seller = ""
                    seller_el = item.select_one("span[class*='seller'], a[class*='Seller']")
                    if seller_el:
                        seller = seller_el.get_text(strip=True)
                    results.append(self._build_result(
                        title=title_el.get_text(strip=True),
                        price=self.parse_price(price_text),
                        seller_username=seller,
                        listing_url=link,
                        category=category,
                        raw_html=str(item),
                    ))
            except Exception as e:
                logger.debug("[yahoo_jp] Parse error: %s", e)
        logger.info("[yahoo_jp] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1.ProductTitle__text")
        price_el = soup.select_one("dd.Price__value")
        seller_el = soup.select_one("span.Seller__name a")
        desc_el = soup.select_one("div.ProductExplanation__body")
        return {
            "title": title_el.get_text(strip=True) if title_el else "",
            "price": self.parse_price(f"¥{price_el.get_text(strip=True)}") if price_el else 0,
            "seller_username": seller_el.get_text(strip=True) if seller_el else "",
            "description": desc_el.get_text(strip=True) if desc_el else "",
            "raw_html": resp.text[:5000],
        }
