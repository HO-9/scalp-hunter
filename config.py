import os
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    url: str = "sqlite+aiosqlite:///scalp_hunter.db"
    echo: bool = False


@dataclass
class CrawlerConfig:
    request_timeout: int = 30
    rate_limit_delay: float = 1.0
    max_concurrent_requests: int = 5
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    retry_count: int = 3
    retry_delay: float = 2.0


@dataclass
class PlatformCredentials:
    ticketmaster_api_key: str = field(default_factory=lambda: os.getenv("TICKETMASTER_API_KEY", ""))
    twitter_bearer_token: str = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN", ""))
    instagram_session_id: str = field(default_factory=lambda: os.getenv("INSTAGRAM_SESSION_ID", ""))


@dataclass
class DetectionConfig:
    min_markup_ratio: float = 1.0
    bulk_listing_threshold: int = 3
    new_account_days_threshold: int = 30
    risk_score_weights: dict = field(default_factory=lambda: {
        "price_markup": 0.35,
        "bulk_listing": 0.20,
        "recent_account": 0.15,
        "keyword_match": 0.10,
        "cross_platform": 0.10,
        "repeat_offender": 0.10,
    })


@dataclass
class SherlockConfig:
    binary_path: str = field(default_factory=lambda: os.getenv("SHERLOCK_PATH", "sherlock"))
    timeout: int = 60
    max_platforms: int = 100


@dataclass
class SchedulerConfig:
    monitor_interval_minutes: int = 30
    full_scan_interval_hours: int = 6


@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class Config:
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    credentials: PlatformCredentials = field(default_factory=PlatformCredentials)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    sherlock: SherlockConfig = field(default_factory=SherlockConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    api: APIConfig = field(default_factory=APIConfig)

    scalper_keywords_kr: list = field(default_factory=lambda: [
        "정가이상", "웃돈", "프리미엄", "긴급양도", "마감임박",
        "양도합니다", "티켓양도", "입장권양도", "좌석양도",
        "매진", "솔드아웃", "구하기힘든",
    ])
    scalper_keywords_en: list = field(default_factory=lambda: [
        "sold out", "premium", "limited", "below market",
        "face value", "best offer", "rare tickets", "last chance",
        "guaranteed entry", "VIP access",
    ])

    ticket_categories: dict = field(default_factory=lambda: {
        "concert": {"law": "공연법", "keywords": ["콘서트", "공연", "concert", "live", "tour"]},
        "sports": {"law": "국민체육진흥법", "keywords": ["야구", "축구", "농구", "배구", "sports", "경기", "KBO", "K-League"]},
        "ktx": {"law": "기타", "keywords": ["KTX", "SRT", "기차", "열차"]},
        "festival": {"law": "공연법", "keywords": ["페스티벌", "festival", "축제"]},
        "musical": {"law": "공연법", "keywords": ["뮤지컬", "musical", "연극", "오페라"]},
        "esports": {"law": "국민체육진흥법", "keywords": ["이스포츠", "esports", "LOL", "게임대회"]},
    })


config = Config()
