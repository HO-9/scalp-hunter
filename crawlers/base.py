import asyncio
import logging
import re
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    platform_name: str = ""
    platform_region: str = ""
    base_url: str = ""
    rate_limit_delay: float = 1.0

    TICKET_KEYWORDS_KR = [
        "티켓", "입장권", "관람권", "양도", "판매", "좌석", "스탠딩",
        "VIP", "R석", "S석", "A석", "지정석", "자유석", "예매",
        "콘서트", "공연", "경기", "KTX", "SRT",
    ]
    TICKET_KEYWORDS_EN = [
        "ticket", "tickets", "admission", "seat", "standing",
        "VIP", "floor", "section", "row", "concert", "show",
        "game", "match", "sold out", "face value",
    ]

    def __init__(self, rate_limit_delay: float | None = None):
        if rate_limit_delay is not None:
            self.rate_limit_delay = rate_limit_delay
        self._last_request_time: float = 0

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            follow_redirects=True,
        )

    async def _rate_limit(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch(self, url: str, params: dict | None = None) -> httpx.Response | None:
        await self._rate_limit()
        try:
            async with self._get_client() as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp
        except httpx.HTTPStatusError as e:
            logger.warning("[%s] HTTP %d for %s", self.platform_name, e.response.status_code, url)
        except httpx.RequestError as e:
            logger.warning("[%s] Request error for %s: %s", self.platform_name, url, e)
        return None

    async def _fetch_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict | list | None:
        await self._rate_limit()
        try:
            async with self._get_client() as client:
                if headers:
                    client.headers.update(headers)
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning("[%s] JSON fetch error for %s: %s", self.platform_name, url, e)
        except ValueError:
            logger.warning("[%s] Invalid JSON from %s", self.platform_name, url)
        return None

    @staticmethod
    def parse_price(text: str) -> int:
        if not text:
            return 0
        cleaned = re.sub(r"[^\d.,]", "", text.replace(",", ""))
        match = re.search(r"[\d.]+", cleaned)
        if not match:
            return 0
        raw = match.group()
        try:
            value = float(raw)
        except ValueError:
            return 0
        lower = text.lower()
        if "$" in text or "usd" in lower:
            return int(value * 1350)
        if "€" in text or "eur" in lower:
            return int(value * 1450)
        if "¥" in text or "円" in text or "jpy" in lower:
            return int(value * 9)
        if "元" in text or "cny" in lower or "rmb" in lower:
            return int(value * 185)
        if "£" in text or "gbp" in lower:
            return int(value * 1700)
        return int(value)

    @staticmethod
    def calculate_markup(face_value: int, listed_price: int) -> float:
        if face_value <= 0:
            return 0.0
        return round(listed_price / face_value, 2)

    def _build_result(
        self,
        title: str,
        price: int,
        seller_username: str,
        listing_url: str,
        category: str = "ticket",
        raw_html: str = "",
    ) -> dict:
        return {
            "title": title,
            "price": price,
            "seller_username": seller_username,
            "listing_url": listing_url,
            "platform": self.platform_name,
            "platform_region": self.platform_region,
            "category": category,
            "raw_html": raw_html,
        }

    @abstractmethod
    async def search_tickets(self, query: str, category: str = "all") -> list[dict]:
        ...

    @abstractmethod
    async def get_listing_detail(self, url: str) -> dict:
        ...
