import logging

from bs4 import BeautifulSoup

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class DanggeunCrawler(BaseCrawler):
    platform_name = "danggeun"
    platform_region = "kr"
    base_url = "https://www.daangn.com"

    SEARCH_URL = "https://www.daangn.com/search/{query}"

    KEYWORDS = [
        "티켓 양도", "콘서트 티켓", "공연 양도", "입장권 판매",
        "KTX 양도", "좌석 양도", "스탠딩 양도", "VIP 양도",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        search_url = self.SEARCH_URL.format(query=query)
        resp = await self._fetch(search_url)
        if not resp:
            logger.info("[danggeun] No response for query: %s", query)
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.flea-market-article, a[data-event-label='search_article']")
        for article in articles:
            try:
                title_el = article.select_one("span.article-title, h2")
                price_el = article.select_one("span.article-price, p.price")
                link = article.get("href") or ""
                if title_el:
                    title = title_el.get_text(strip=True)
                    price_text = price_el.get_text(strip=True) if price_el else "0"
                    price = self.parse_price(price_text)
                    listing_url = f"{self.base_url}{link}" if link.startswith("/") else link
                    results.append(self._build_result(
                        title=title,
                        price=price,
                        seller_username="",
                        listing_url=listing_url,
                        category=category,
                        raw_html=str(article),
                    ))
            except Exception as e:
                logger.debug("[danggeun] Parse error: %s", e)
        logger.info("[danggeun] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        resp = await self._fetch(url)
        if not resp:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.select_one("h1#article-title, h1")
        price_el = soup.select_one("p#article-price, span.price")
        seller_el = soup.select_one("a[data-event-label='article_profile'], div.nickname")
        return {
            "title": title_el.get_text(strip=True) if title_el else "",
            "price": self.parse_price(price_el.get_text(strip=True)) if price_el else 0,
            "seller_username": seller_el.get_text(strip=True) if seller_el else "",
            "description": soup.select_one("div#article-detail, article")
            and soup.select_one("div#article-detail, article").get_text(strip=True)
            or "",
            "raw_html": resp.text[:5000],
        }
