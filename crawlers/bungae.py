import logging

from .base import BaseCrawler

logger = logging.getLogger(__name__)


class BungaeCrawler(BaseCrawler):
    platform_name = "bungae"
    platform_region = "kr"
    base_url = "https://m.bunjang.co.kr"

    API_URL = "https://api.bunjang.co.kr/api/1/find_v2.json"

    KEYWORDS = [
        "티켓", "콘서트", "공연", "양도", "입장권",
        "KTX", "SRT", "좌석", "스탠딩", "VIP",
    ]

    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        results = []
        params = {
            "q": query,
            "order": "date",
            "page": 0,
            "n": 50,
        }
        data = await self._fetch_json(self.API_URL, params=params)
        if not data or "list" not in data:
            logger.info("[bungae] No results for query: %s", query)
            return results

        for item in data.get("list", []):
            try:
                pid = item.get("pid", "")
                results.append(self._build_result(
                    title=item.get("name", ""),
                    price=int(item.get("price", 0)),
                    seller_username=item.get("seller_name", ""),
                    listing_url=f"{self.base_url}/product/{pid}",
                    category=category,
                ))
            except Exception as e:
                logger.debug("[bungae] Parse error: %s", e)
        logger.info("[bungae] Found %d listings for '%s'", len(results), query)
        return results

    async def get_listing_detail(self, url: str) -> dict:
        pid = url.rstrip("/").split("/")[-1]
        api_url = f"https://api.bunjang.co.kr/api/1/product/{pid}/detail_info.json"
        data = await self._fetch_json(api_url)
        if not data or "item_info" not in data:
            return {}
        info = data["item_info"]
        return {
            "title": info.get("name", ""),
            "price": int(info.get("price", 0)),
            "seller_username": info.get("seller_name", ""),
            "description": info.get("description", ""),
            "raw_html": "",
        }
