import enum
from datetime import datetime

from sqlalchemy import ForeignKey, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    FLAGGED = "flagged"
    REPORTED = "reported"
    RESOLVED = "resolved"


class ListingCategory(str, enum.Enum):
    CONCERT = "concert"
    SPORTS = "sports"
    KTX = "ktx"
    FESTIVAL = "festival"
    OTHER = "other"


class DetectionSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetectionStatus(str, enum.Enum):
    NEW = "new"
    INVESTIGATING = "investigating"
    REPORTED = "reported"
    CLOSED = "closed"


class MonitoringStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column()
    title: Mapped[str] = mapped_column()
    event_name: Mapped[str] = mapped_column()
    face_value: Mapped[int] = mapped_column()
    listed_price: Mapped[int] = mapped_column()
    markup_ratio: Mapped[float] = mapped_column()
    seller_username: Mapped[str] = mapped_column()
    seller_url: Mapped[str | None] = mapped_column(default=None)
    listing_url: Mapped[str | None] = mapped_column(default=None)
    detected_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    status: Mapped[ListingStatus] = mapped_column(default=ListingStatus.ACTIVE)
    category: Mapped[ListingCategory] = mapped_column(default=ListingCategory.OTHER)
    raw_data: Mapped[dict | None] = mapped_column(JSON, default=None)

    detections: Mapped[list["Detection"]] = relationship(back_populates="listing")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"))
    severity: Mapped[DetectionSeverity] = mapped_column()
    detection_rules_matched: Mapped[list] = mapped_column(JSON, insert_default=list)
    estimated_fine_min: Mapped[int] = mapped_column(default=0)
    estimated_fine_max: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[DetectionStatus] = mapped_column(default=DetectionStatus.NEW)

    listing: Mapped["Listing"] = relationship(back_populates="detections")


class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column()
    platform: Mapped[str] = mapped_column()
    profile_url: Mapped[str | None] = mapped_column(default=None)
    account_age_days: Mapped[int | None] = mapped_column(default=None)
    total_listings: Mapped[int] = mapped_column(default=0)
    ticket_listings: Mapped[int] = mapped_column(default=0)
    risk_score: Mapped[float] = mapped_column(default=0.0)
    sherlock_results: Mapped[dict | None] = mapped_column(JSON, default=None)
    first_seen: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    chat_logs: Mapped[list["ChatLog"]] = relationship(back_populates="seller")
    sherlock_lookups: Mapped[list["SherlockResult"]] = relationship(back_populates="linked_seller")


class SherlockResult(Base):
    __tablename__ = "sherlock_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username_searched: Mapped[str] = mapped_column()
    platforms_found: Mapped[list] = mapped_column(JSON, insert_default=list)
    searched_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    linked_seller_id: Mapped[int | None] = mapped_column(ForeignKey("sellers.id"), default=None)

    linked_seller: Mapped["Seller | None"] = relationship(back_populates="sherlock_lookups")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sellers.id"))
    platform: Mapped[str] = mapped_column()
    messages: Mapped[list] = mapped_column(JSON, insert_default=list)
    started_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    last_message_at: Mapped[datetime | None] = mapped_column(default=None)
    evidence_notes: Mapped[str | None] = mapped_column(Text, default=None)

    seller: Mapped["Seller"] = relationship(back_populates="chat_logs")


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(insert_default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    listings_scanned: Mapped[int] = mapped_column(default=0)
    detections_found: Mapped[int] = mapped_column(default=0)
    status: Mapped[MonitoringStatus] = mapped_column(default=MonitoringStatus.RUNNING)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
