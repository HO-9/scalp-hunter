import asyncio
import logging
import sys
import signal

import uvicorn

from config import config
from database.db import init_db
from api.server import app
from crawlers.manager import CrawlerManager
from detection.engine import DetectionEngine
from scheduler.monitor import MonitorScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scalp-hunter")


async def seed_demo_data():
    from database.db import get_session
    from database.models import Listing, Detection, Seller
    from datetime import datetime, timedelta
    from sqlalchemy import select

    async with get_session() as session:
        existing = await session.scalar(select(Listing.id).limit(1))
        if existing:
            return

        logger.info("Seeding demo data...")
        demo_listings = [
            {
                "platform": "danggeun",
                "title": "BTS World Tour 2026 Seoul VIP A-block 2장",
                "event_name": "BTS World Tour 2026 Seoul",
                "face_value": 154000,
                "listed_price": 580000,
                "seller_username": "ticket_master_kr",
                "category": "concert",
            },
            {
                "platform": "twitter",
                "title": "aespa SYNK Concert floor standing 양도",
                "event_name": "aespa SYNK Concert",
                "face_value": 132000,
                "listed_price": 450000,
                "seller_username": "aespa_tix_sell",
                "category": "concert",
            },
            {
                "platform": "bungae",
                "title": "KTX 서울-부산 12/24 창가석",
                "event_name": "KTX Seoul-Busan (Dec 24)",
                "face_value": 59800,
                "listed_price": 180000,
                "seller_username": "ktx_express_deal",
                "category": "ktx",
            },
            {
                "platform": "viagogo",
                "title": "IU The Winning VIP Package Seoul",
                "event_name": "IU Concert The Winning",
                "face_value": 110000,
                "listed_price": 890000,
                "seller_username": "kr_premium_seats",
                "category": "concert",
            },
            {
                "platform": "xianyu",
                "title": "BLACKPINK Born Pink Encore Beijing VIP",
                "event_name": "BLACKPINK Born Pink Encore",
                "face_value": 165000,
                "listed_price": 1200000,
                "seller_username": "blackpink_vip_cn",
                "category": "concert",
            },
            {
                "platform": "ticketmaster",
                "title": "Coldplay MOTS Seoul Day2",
                "event_name": "Coldplay Music of the Spheres",
                "face_value": 99000,
                "listed_price": 320000,
                "seller_username": "live_tix_pro",
                "category": "concert",
            },
            {
                "platform": "instagram",
                "title": "KBO 한국시리즈 G7 1루측 내야석",
                "event_name": "KBO Korean Series G7",
                "face_value": 30000,
                "listed_price": 150000,
                "seller_username": "sports_ticket_kr",
                "category": "sports",
            },
        ]

        for i, dl in enumerate(demo_listings):
            markup = dl["listed_price"] / dl["face_value"]
            listing = Listing(
                platform=dl["platform"],
                title=dl["title"],
                event_name=dl["event_name"],
                face_value=dl["face_value"],
                listed_price=dl["listed_price"],
                markup_ratio=round(markup, 2),
                seller_username=dl["seller_username"],
                listing_url=f"https://example.com/listing/{i+1}",
                detected_at=datetime.utcnow() - timedelta(hours=i),
                status="flagged",
                category=dl["category"],
            )
            session.add(listing)
            await session.flush()

            severity = "critical" if markup > 3 else "high" if markup > 2 else "medium"
            detection = Detection(
                listing_id=listing.id,
                severity=severity,
                detection_rules_matched=["price_markup", "keyword_match"],
                estimated_fine_min=dl["listed_price"] * 2,
                estimated_fine_max=dl["listed_price"] * 10,
                status="new",
            )
            session.add(detection)

            seller = Seller(
                username=dl["seller_username"],
                platform=dl["platform"],
                total_listings=5 + i,
                ticket_listings=2 + i % 3,
                risk_score=min(1.0, markup / 10),
                first_seen=datetime.utcnow() - timedelta(days=30 + i * 10),
                last_seen=datetime.utcnow(),
            )
            session.add(seller)

        await session.commit()
        logger.info(f"Seeded {len(demo_listings)} demo listings")


async def main():
    logger.info("ScalpHunter starting...")

    await init_db()
    await seed_demo_data()

    crawler_manager = CrawlerManager()
    detection_engine = DetectionEngine()
    scheduler = MonitorScheduler(
        crawler_manager=crawler_manager,
        detection_engine=detection_engine,
        interval_minutes=config.scheduler.monitor_interval_minutes,
    )

    logger.info(f"Registered {len(crawler_manager.list_crawlers())} platform crawlers")
    logger.info("Starting API server...")

    server_config = uvicorn.Config(
        app="api.server:app",
        host=config.api.host,
        port=config.api.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)

    loop = asyncio.get_event_loop()

    def handle_shutdown(sig, frame):
        logger.info(f"Received {sig}, shutting down...")
        scheduler.stop()
        server.should_exit = True

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
