from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .pricing import calculate_fine
from .rules import ALL_RULES, SEVERITY_ORDER, DetectionRule, RuleResult

EVENT_CATEGORY_KEYWORDS = {
    "concert": ["콘서트", "concert", "tour", "world tour", "앵콜", "encore", "live"],
    "sports": ["kbo", "k-league", "축구", "야구", "epl", "프리미어", "korean series", "월드컵"],
    "ktx": ["ktx", "srt", "기차", "열차", "train"],
    "festival": ["페스티벌", "festival", "lollapalooza", "워터밤", "축제"],
    "musical": ["뮤지컬", "musical", "오페라", "opera", "연극"],
    "esports": ["e스포츠", "esports", "lol", "롤드컵", "worlds"],
}


def _classify_event(listing: dict) -> str:
    text = " ".join(
        str(listing.get(f, "")) for f in ("event_name", "title", "category")
    ).lower()
    for category, keywords in EVENT_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "other"


@dataclass
class DetectionResult:
    listing: dict
    rules_matched: list[RuleResult] = field(default_factory=list)
    severity: str = "low"
    is_violation: bool = False
    fine_estimate: dict | None = None
    recommendation: str = ""
    event_category: str = "other"


class DetectionEngine:
    def __init__(self, rules: list[DetectionRule] | None = None):
        self.rules = rules if rules is not None else list(ALL_RULES)

    async def analyze_listing(
        self, listing: dict, seller_history: dict | None = None
    ) -> DetectionResult:
        if seller_history is None:
            seller_history = {}

        result = DetectionResult(listing=listing)
        result.event_category = _classify_event(listing)

        for rule in self.rules:
            rule_result = rule.evaluate(listing, seller_history)
            if rule_result.matched:
                result.rules_matched.append(rule_result)

        if not result.rules_matched:
            result.recommendation = "No violation indicators found"
            return result

        worst = min(
            result.rules_matched,
            key=lambda r: SEVERITY_ORDER.get(r.severity, 99),
        )
        base_severity = worst.severity

        matched_count = len(result.rules_matched)
        if matched_count >= 4 and base_severity != "critical":
            result.severity = "critical"
        elif matched_count >= 3 and SEVERITY_ORDER.get(base_severity, 99) > 0:
            result.severity = "high" if base_severity != "critical" else "critical"
        elif matched_count >= 2 and SEVERITY_ORDER.get(base_severity, 99) > 1:
            result.severity = max(
                "medium",
                base_severity,
                key=lambda s: -SEVERITY_ORDER.get(s, 99),
            )
        else:
            result.severity = base_severity

        has_price_violation = any(r.rule_name == "price_markup" for r in result.rules_matched)
        has_pattern = any(
            r.rule_name in ("bulk_listing", "repeat_offender", "cross_platform")
            for r in result.rules_matched
        )
        result.is_violation = has_price_violation and (has_pattern or result.severity in ("critical", "high"))

        if has_price_violation:
            sale_amount = listing.get("listed_price") or listing.get("price", 0)
            ticket_count = listing.get("ticket_count", 1)
            law_type = "sports" if result.event_category in ("sports", "esports") else "performance"
            result.fine_estimate = calculate_fine(
                sale_amount=sale_amount,
                ticket_count=ticket_count,
                law_type=law_type,
                event_category=result.event_category,
            )

        result.recommendation = self._build_recommendation(result)
        return result

    async def batch_analyze(
        self, listings: list[dict], seller_histories: dict[str, dict] | None = None
    ) -> list[DetectionResult]:
        if seller_histories is None:
            seller_histories = {}

        tasks = []
        for listing in listings:
            seller_id = listing.get("seller_id", listing.get("seller_username", ""))
            history = seller_histories.get(seller_id, {})
            tasks.append(self.analyze_listing(listing, history))

        return await asyncio.gather(*tasks)

    @staticmethod
    def _build_recommendation(result: DetectionResult) -> str:
        if not result.is_violation:
            if result.rules_matched:
                return "Monitor - suspicious indicators but insufficient for violation"
            return "No action needed"

        if result.severity == "critical":
            return (
                "Immediate report recommended - strong violation indicators. "
                "Collect evidence (screenshots, transaction records) and submit to reporting authority."
            )
        if result.severity == "high":
            return (
                "Investigation recommended - run Sherlock cross-platform lookup "
                "and initiate undercover chat to confirm habitual selling pattern."
            )
        return "Flag for review - gather additional evidence before reporting."
