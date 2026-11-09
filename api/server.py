from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import asyncio

from config import config
from database.db import get_session, init_db
from database.models import Listing, Detection, Seller, SherlockResult, ChatLog, MonitoringRun
from detection.engine import DetectionEngine
from investigation.sherlock_lookup import SherlockLookup
from investigation.chat import ChatSession
from crawlers.manager import CrawlerManager

from sqlalchemy import select, func, desc

app = FastAPI(title="ScalpHunter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

detection_engine = DetectionEngine()
sherlock = SherlockLookup()
crawler_manager = CrawlerManager()
chat_sessions: dict[str, ChatSession] = {}


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/")
async def root():
    return FileResponse("static/index.html")


class DashboardStats(BaseModel):
    total_detections_24h: int
    platforms_monitored: int
    suspected_scalpers: int
    avg_markup: float
    reported_count: int
    estimated_illegal_profit: int


@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    async with get_session() as session:
        now = datetime.utcnow()
        day_ago = datetime(now.year, now.month, now.day - 1) if now.day > 1 else now

        det_count = await session.scalar(
            select(func.count(Detection.id)).where(Detection.created_at >= day_ago)
        ) or 0

        scalper_count = await session.scalar(
            select(func.count(Seller.id)).where(Seller.risk_score >= 0.5)
        ) or 0

        avg_markup = await session.scalar(
            select(func.avg(Listing.markup_ratio)).where(Listing.markup_ratio > 1.0)
        ) or 0.0

        reported = await session.scalar(
            select(func.count(Detection.id)).where(Detection.status == "reported")
        ) or 0

        total_profit = await session.scalar(
            select(func.sum(Listing.listed_price - Listing.face_value)).where(
                Listing.listed_price > Listing.face_value
            )
        ) or 0

        return DashboardStats(
            total_detections_24h=det_count,
            platforms_monitored=len(crawler_manager.list_crawlers()),
            suspected_scalpers=scalper_count,
            avg_markup=round(avg_markup, 1),
            reported_count=reported,
            estimated_illegal_profit=total_profit,
        )


@app.get("/api/listings")
async def get_listings(
    platform: Optional[str] = None,
    category: Optional[str] = None,
    min_markup: Optional[float] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    async with get_session() as session:
        q = select(Listing).order_by(desc(Listing.detected_at))
        if platform:
            q = q.where(Listing.platform == platform)
        if category:
            q = q.where(Listing.category == category)
        if min_markup:
            q = q.where(Listing.markup_ratio >= min_markup)
        q = q.limit(limit).offset(offset)
        result = await session.execute(q)
        listings = result.scalars().all()
        return [
            {
                "id": l.id,
                "platform": l.platform,
                "title": l.title,
                "event_name": l.event_name,
                "face_value": l.face_value,
                "listed_price": l.listed_price,
                "markup_ratio": l.markup_ratio,
                "seller_username": l.seller_username,
                "listing_url": l.listing_url,
                "detected_at": l.detected_at.isoformat() if l.detected_at else None,
                "status": l.status,
                "category": l.category,
            }
            for l in listings
        ]


@app.get("/api/detections")
async def get_detections(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    async with get_session() as session:
        q = select(Detection).order_by(desc(Detection.created_at))
        if severity:
            q = q.where(Detection.severity == severity)
        if status:
            q = q.where(Detection.status == status)
        q = q.limit(limit)
        result = await session.execute(q)
        dets = result.scalars().all()
        return [
            {
                "id": d.id,
                "listing_id": d.listing_id,
                "severity": d.severity,
                "detection_rules_matched": d.detection_rules_matched,
                "estimated_fine_min": d.estimated_fine_min,
                "estimated_fine_max": d.estimated_fine_max,
                "notes": d.notes,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "status": d.status,
            }
            for d in dets
        ]


@app.get("/api/detections/{detection_id}")
async def get_detection_detail(detection_id: int):
    async with get_session() as session:
        det = await session.get(Detection, detection_id)
        if not det:
            raise HTTPException(404, "Detection not found")
        listing = await session.get(Listing, det.listing_id) if det.listing_id else None
        seller = None
        if listing:
            result = await session.execute(
                select(Seller).where(Seller.username == listing.seller_username)
            )
            seller = result.scalar_one_or_none()
        return {
            "detection": {
                "id": det.id,
                "severity": det.severity,
                "rules_matched": det.detection_rules_matched,
                "fine_min": det.estimated_fine_min,
                "fine_max": det.estimated_fine_max,
                "status": det.status,
                "notes": det.notes,
                "created_at": det.created_at.isoformat() if det.created_at else None,
            },
            "listing": {
                "title": listing.title if listing else None,
                "event": listing.event_name if listing else None,
                "platform": listing.platform if listing else None,
                "face_value": listing.face_value if listing else None,
                "listed_price": listing.listed_price if listing else None,
                "markup": listing.markup_ratio if listing else None,
                "url": listing.listing_url if listing else None,
            },
            "seller": {
                "username": seller.username if seller else None,
                "platform": seller.platform if seller else None,
                "risk_score": seller.risk_score if seller else None,
                "total_listings": seller.total_listings if seller else None,
                "account_age_days": seller.account_age_days if seller else None,
                "sherlock_results": seller.sherlock_results if seller else None,
            },
        }


class SherlockRequest(BaseModel):
    username: str


@app.post("/api/sherlock/lookup")
async def sherlock_lookup(req: SherlockRequest):
    result = await sherlock.run_lookup(req.username)
    async with get_session() as session:
        sr = SherlockResult(
            username_searched=result.username,
            platforms_found=[
                {"platform": r["platform"], "url": r["url"], "found": r["found"]}
                for r in result.results
            ],
            searched_at=result.searched_at,
        )
        session.add(sr)
        await session.commit()

    return {
        "username": result.username,
        "searched_at": result.searched_at.isoformat(),
        "platforms_checked": result.platforms_checked,
        "platforms_found": result.platforms_found,
        "results": result.results,
    }


@app.get("/api/sherlock/history")
async def sherlock_history(limit: int = 20):
    async with get_session() as session:
        result = await session.execute(
            select(SherlockResult).order_by(desc(SherlockResult.searched_at)).limit(limit)
        )
        items = result.scalars().all()
        return [
            {
                "id": s.id,
                "username": s.username_searched,
                "platforms_found": s.platforms_found,
                "searched_at": s.searched_at.isoformat() if s.searched_at else None,
            }
            for s in items
        ]


@app.get("/api/sellers")
async def get_sellers(min_risk: float = 0.0, limit: int = 50):
    async with get_session() as session:
        q = (
            select(Seller)
            .where(Seller.risk_score >= min_risk)
            .order_by(desc(Seller.risk_score))
            .limit(limit)
        )
        result = await session.execute(q)
        sellers = result.scalars().all()
        return [
            {
                "id": s.id,
                "username": s.username,
                "platform": s.platform,
                "risk_score": s.risk_score,
                "total_listings": s.total_listings,
                "ticket_listings": s.ticket_listings,
                "account_age_days": s.account_age_days,
                "first_seen": s.first_seen.isoformat() if s.first_seen else None,
                "last_seen": s.last_seen.isoformat() if s.last_seen else None,
            }
            for s in sellers
        ]


class ChatMessage(BaseModel):
    seller_username: str
    platform: str
    role: str
    text: str


@app.post("/api/chat/message")
async def add_chat_message(msg: ChatMessage):
    key = f"{msg.seller_username}@{msg.platform}"
    if key not in chat_sessions:
        chat_sessions[key] = ChatSession(
            seller_username=msg.seller_username,
            platform=msg.platform,
            case_id=f"CASE-{msg.seller_username}-{msg.platform}",
        )
    session = chat_sessions[key]
    session.add_message(msg.role, msg.text)
    return {"status": "ok", "message_count": len(session.messages)}


@app.get("/api/chat/suggestions")
async def get_chat_suggestions(context: Optional[str] = None):
    session = ChatSession(seller_username="", platform="", case_id="")
    return {"suggestions": session.get_suggested_questions(context)}


@app.get("/api/chat/{seller_username}/evidence")
async def get_chat_evidence(seller_username: str, platform: str = ""):
    key = f"{seller_username}@{platform}"
    if key not in chat_sessions:
        raise HTTPException(404, "No chat session found")
    return chat_sessions[key].export_evidence()


@app.get("/api/chat/{seller_username}/analysis")
async def get_chat_analysis(seller_username: str, platform: str = ""):
    key = f"{seller_username}@{platform}"
    if key not in chat_sessions:
        raise HTTPException(404, "No chat session found")
    return chat_sessions[key].get_analysis()


class ScanRequest(BaseModel):
    query: str
    platforms: Optional[list[str]] = None
    category: Optional[str] = None


@app.post("/api/scan")
async def run_scan(req: ScanRequest):
    results = await crawler_manager.search_all(
        query=req.query,
        category=req.category or "all",
        platforms=req.platforms,
    )

    analyzed = await detection_engine.batch_analyze(results)

    async with get_session() as session:
        saved_count = 0
        for ar in analyzed:
            face_val = ar.listing.get("face_value", 0)
            listed_val = ar.listing.get("price", ar.listing.get("listed_price", 0))
            markup = listed_val / face_val if face_val > 0 else 0
            listing = Listing(
                platform=ar.listing.get("platform", "unknown"),
                title=ar.listing.get("title", ""),
                event_name=ar.listing.get("event_name", req.query),
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
                saved_count += 1

        await session.commit()

    return {
        "total_listings": len(results),
        "violations_found": sum(1 for a in analyzed if a.is_violation),
        "saved_detections": saved_count,
    }


@app.get("/api/platforms")
async def get_platforms():
    return [
        {
            "id": c["name"].lower().replace(" ", "_"),
            "name": c["name"],
            "region": c["region"],
            "base_url": c["base_url"],
            "status": "active",
        }
        for c in crawler_manager.list_crawlers()
    ]


@app.get("/api/monitoring/runs")
async def get_monitoring_runs(limit: int = 20):
    async with get_session() as session:
        result = await session.execute(
            select(MonitoringRun).order_by(desc(MonitoringRun.started_at)).limit(limit)
        )
        runs = result.scalars().all()
        return [
            {
                "id": r.id,
                "platform": r.platform,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "listings_scanned": r.listings_scanned,
                "detections_found": r.detections_found,
                "status": r.status,
            }
            for r in runs
        ]
