import asyncio
import logging
from datetime import datetime

from database.db import get_session
from database.models import Listing, Detection, Seller, MonitoringRun
from crawlers.manager import CrawlerManager
from detection.engine import DetectionEngine

from sqlalchemy import select

logger = logging.getLogger(__name__)


class MonitorScheduler:
    def __init__(
        self,
        crawler_manager: CrawlerManager,
        detection_engine: DetectionEngine,
        scan_queries: list[str] | None = None,
        interval_minutes: int = 30,
    ):
        self.crawler_manager = crawler_manager
        self.detection_engine = detection_engine
        self.interval_minutes = interval_minutes
        self.running = False
        self.scan_queries = scan_queries or [
            "콘서트 티켓 양도",
            "공연 입장권 판매",
            "KTX 표 양도",
            "concert ticket resale",
            "sports ticket sale",
            "티켓 프리미엄",
        ]

    async def run_single_scan(self, query: str, platform: str | None = None) -> dict:
        run = MonitoringRun(
            platform=platform or "all",
            started_at=datetime.utcnow(),
            status="running",
        )
        async with get_session() as session:
            session.add(run)
            await session.commit()
            run_id = run.id

        try:
            platforms = [platform] if platform else None
            results = await self.crawler_manager.run_all(
                query=query, category="all", platforms=platforms
            )

            analyzed = await self.detection_engine.batch_analyze(results)
            violations = [a for a in analyzed if a["is_violation"]]

            async with get_session() as session:
                for ar in analyzed:
                    face_val = ar.listing.get("face_value", 0)
                    listed_val = ar.listing.get("price", ar.listing.get("listed_price", 0))
                    markup = listed_val / face_val if face_val > 0 else 0
                    listing = Listing(
                        platform=ar.listing.get("platform", "unknown"),
                        title=ar.listing.get("title", ""),
                        event_name=ar.listing.get("event_name", query),
                        face_value=face_val,
                        listed_price=listed_val,
                        markup_ratio=round(markup, 2),
                        seller_username=ar.listing.get("seller_username", ""),
                        listing_url=ar.listing.get("listing_url", ""),
                        detected_at=datetime.utcnow(),
                        status="flagged" if ar.is_violation else "active",
                        category=ar.listing.get("category", "other"),
                    )
                    session.add(listing)
                    await session.flush()

                    if ar.is_violation:
                        fine_est = ar.fine_estimate or {}
                        detection = Detection(
                            listing_id=listing.id,
                            severity=ar.severity,
                            detection_rules_matched=[r.rule_name for r in ar.rules_matched],
                            estimated_fine_min=fine_est.get("fine_min", 0),
                            estimated_fine_max=fine_est.get("fine_max", 0),
                            status="new",
                        )
                        session.add(detection)

                    seller_username = ar.listing.get("seller_username", "")
                    if seller_username:
                        existing = await session.execute(
                            select(Seller).where(
                                Seller.username == seller_username,
                                Seller.platform == ar.listing.get("platform", ""),
                            )
                        )
                        seller = existing.scalar_one_or_none()
                        if seller:
                            seller.last_seen = datetime.utcnow()
                            seller.total_listings = (seller.total_listings or 0) + 1
                            if ar.is_violation:
                                seller.ticket_listings = (seller.ticket_listings or 0) + 1
                                seller.risk_score = min(1.0, (seller.risk_score or 0) + 0.1)
                        else:
                            seller = Seller(
                                username=seller_username,
                                platform=ar.listing.get("platform", ""),
                                profile_url=ar.listing.get("seller_url", ""),
                                total_listings=1,
                                ticket_listings=1 if ar.is_violation else 0,
                                risk_score=0.5 if ar.is_violation else 0.1,
                                first_seen=datetime.utcnow(),
                                last_seen=datetime.utcnow(),
                            )
                            session.add(seller)

                db_run = await session.get(MonitoringRun, run_id)
                if db_run:
                    db_run.finished_at = datetime.utcnow()
                    db_run.listings_scanned = len(results)
                    db_run.detections_found = len(violations)
                    db_run.status = "completed"

                await session.commit()

            logger.info(
                f"Scan complete: query='{query}', listings={len(results)}, violations={len(violations)}"
            )
            return {
                "query": query,
                "listings_scanned": len(results),
                "violations_found": len(violations),
            }

        except Exception as e:
            logger.error(f"Scan failed for query='{query}': {e}")
            async with get_session() as session:
                db_run = await session.get(MonitoringRun, run_id)
                if db_run:
                    db_run.finished_at = datetime.utcnow()
                    db_run.status = "failed"
                    db_run.error_message = str(e)
                await session.commit()
            return {"query": query, "error": str(e)}

    async def run_full_scan(self) -> list[dict]:
        logger.info(f"Starting full scan with {len(self.scan_queries)} queries")
        results = []
        for query in self.scan_queries:
            result = await self.run_single_scan(query)
            results.append(result)
            await asyncio.sleep(2)
        return results

    async def start(self):
        self.running = True
        logger.info(f"Monitor scheduler started (interval: {self.interval_minutes}min)")
        while self.running:
            try:
                await self.run_full_scan()
            except Exception as e:
                logger.error(f"Scheduled scan error: {e}")
            await asyncio.sleep(self.interval_minutes * 60)

    def stop(self):
        self.running = False
        logger.info("Monitor scheduler stopped")
