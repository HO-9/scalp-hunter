from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass
class RuleResult:
    matched: bool
    rule_name: str
    severity: str  # critical / high / medium / low
    details: str


class DetectionRule(Protocol):
    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult: ...


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class PriceMarkupRule:
    """Core legal criterion: listed price exceeds face value."""

    name = "price_markup"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        face = listing.get("face_value", 0)
        listed = listing.get("listed_price") or listing.get("price", 0)
        if face <= 0 or listed <= face:
            return RuleResult(False, self.name, "low", "")

        ratio = listed / face
        if ratio >= 5.0:
            severity = "critical"
        elif ratio >= 3.0:
            severity = "high"
        elif ratio >= 1.5:
            severity = "medium"
        else:
            severity = "low"

        profit = listed - face
        return RuleResult(
            True,
            self.name,
            severity,
            f"Listed at ×{ratio:.1f} of face value "
            f"(₩{face:,} → ₩{listed:,}, profit ₩{profit:,})",
        )


class BulkListingRule:
    """Flags habitual/business pattern: 3+ listings for the same event."""

    name = "bulk_listing"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        event_id = listing.get("event_id") or listing.get("event_name", "")
        if not event_id:
            return RuleResult(False, self.name, "low", "")

        same_event = 0
        for past in seller_history.get("listings", []):
            past_event = past.get("event_id") or past.get("event_name", "")
            if past_event and past_event == event_id:
                same_event += 1

        if same_event < 3:
            return RuleResult(False, self.name, "low", "")

        severity = "critical" if same_event >= 10 else "high" if same_event >= 5 else "medium"
        return RuleResult(
            True,
            self.name,
            severity,
            f"Seller has {same_event} listings for the same event (habitual pattern)",
        )


class RecentAccountRule:
    """Flags seller accounts created within 30 days."""

    name = "recent_account"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        created = seller_history.get("account_created")
        if not created:
            return RuleResult(False, self.name, "low", "")

        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                return RuleResult(False, self.name, "low", "")

        age = datetime.now() - created
        if age > timedelta(days=30):
            return RuleResult(False, self.name, "low", "")

        severity = "high" if age < timedelta(days=7) else "medium"
        return RuleResult(
            True,
            self.name,
            severity,
            f"Account created {age.days} day(s) ago (suspicious timing)",
        )


SCALPER_KEYWORDS_KR = [
    "정가이상", "웃돈", "프리미엄", "긴급양도", "마감임박",
    "급처", "정가이상거래", "양도합니다", "급매", "프리미엄석",
    "선착순", "조기마감", "매진", "솔드아웃",
]

SCALPER_KEYWORDS_EN = [
    "sold out", "limited", "premium seat", "below market",
    "best offer", "rare ticket", "last chance", "hurry",
    "face value", "markup", "resale", "scalp",
]

_KR_PATTERN = re.compile("|".join(re.escape(k) for k in SCALPER_KEYWORDS_KR), re.IGNORECASE)
_EN_PATTERN = re.compile("|".join(re.escape(k) for k in SCALPER_KEYWORDS_EN), re.IGNORECASE)


class KeywordRule:
    """Checks listing text for known scalper keywords."""

    name = "keyword_match"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        text = " ".join(
            str(listing.get(f, ""))
            for f in ("title", "description", "seller_note")
        )
        if not text.strip():
            return RuleResult(False, self.name, "low", "")

        kr_hits = _KR_PATTERN.findall(text)
        en_hits = _EN_PATTERN.findall(text)
        hits = list(dict.fromkeys(kr_hits + en_hits))

        if not hits:
            return RuleResult(False, self.name, "low", "")

        severity = "high" if len(hits) >= 3 else "medium" if len(hits) >= 2 else "low"
        return RuleResult(
            True,
            self.name,
            severity,
            f"Scalper keywords detected: {', '.join(hits[:5])}",
        )


class CrossPlatformRule:
    """Flags when the same username appears on multiple platforms."""

    name = "cross_platform"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        platforms = seller_history.get("platforms_found", [])
        if len(platforms) < 2:
            return RuleResult(False, self.name, "low", "")

        severity = "critical" if len(platforms) >= 5 else "high" if len(platforms) >= 3 else "medium"
        return RuleResult(
            True,
            self.name,
            severity,
            f"Username active on {len(platforms)} platforms: {', '.join(platforms[:6])}",
        )


class RepeatOffenderRule:
    """Flags sellers who have been previously detected."""

    name = "repeat_offender"

    def evaluate(self, listing: dict, seller_history: dict) -> RuleResult:
        prior = seller_history.get("prior_detections", 0)
        if prior <= 0:
            return RuleResult(False, self.name, "low", "")

        severity = "critical" if prior >= 3 else "high" if prior >= 2 else "medium"
        return RuleResult(
            True,
            self.name,
            severity,
            f"Seller has {prior} prior detection(s) on record",
        )


ALL_RULES: list[DetectionRule] = [
    PriceMarkupRule(),
    BulkListingRule(),
    RecentAccountRule(),
    KeywordRule(),
    CrossPlatformRule(),
    RepeatOffenderRule(),
]
