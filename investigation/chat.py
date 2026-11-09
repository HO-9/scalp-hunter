import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

SUGGESTED_QUESTIONS = [
    "이 티켓 아직 판매 중인가요? / Is this ticket still available?",
    "몇 장 가지고 계신가요? / How many tickets do you have?",
    "정가가 얼마였나요? / What was the face value?",
    "어디서 구매하셨나요? / Where did you buy these?",
    "자주 티켓을 파시나요? / Do you sell tickets often?",
    "영수증이나 구매 증빙 있으신가요? / Do you have proof of purchase?",
    "직거래 가능하신가요? / Can we meet in person for the transaction?",
    "가격 네고 가능한가요? / Is the price negotiable?",
]

EVIDENCE_KEYWORDS = [
    "웃돈",
    "정가 이상",
    "프리미엄",
    "여러 장",
    "자주 팔아",
    "사업",
    "매번",
    "단골",
    "대량",
    "original price",
    "markup",
    "premium",
    "multiple tickets",
    "bulk",
    "business",
    "regularly sell",
]

PRICE_PATTERN = re.compile(r"(\d[\d,]*)\s*(?:원|won|krw|₩)", re.IGNORECASE)


@dataclass
class ChatMessage:
    role: str
    text: str
    timestamp: str


@dataclass
class ChatSession:
    seller_username: str
    platform: str
    case_id: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    messages: list[ChatMessage] = field(default_factory=list)

    def add_message(self, role: str, text: str) -> ChatMessage:
        msg = ChatMessage(
            role=role,
            text=text,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.messages.append(msg)
        return msg

    def get_suggested_questions(self, context: str | None = None) -> list[str]:
        if context is None:
            return list(SUGGESTED_QUESTIONS)

        context_lower = context.lower()
        prioritised: list[str] = []
        rest: list[str] = []
        for q in SUGGESTED_QUESTIONS:
            q_lower = q.lower()
            if any(w in context_lower for w in q_lower.split()[:3]):
                rest.append(q)
            else:
                prioritised.append(q)
        return prioritised + rest

    def export_evidence(self) -> dict:
        analysis = self.get_analysis()
        return {
            "case_id": self.case_id,
            "seller_username": self.seller_username,
            "platform": self.platform,
            "session_created": self.created_at,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "message_count": len(self.messages),
            "messages": [
                {"role": m.role, "text": m.text, "timestamp": m.timestamp}
                for m in self.messages
            ],
            "analysis": analysis,
        }

    def get_analysis(self) -> dict:
        flagged_messages: list[dict] = []
        keyword_hits: dict[str, int] = {}
        prices_mentioned: list[int] = []

        for msg in self.messages:
            text_lower = msg.text.lower()
            matched_keywords: list[str] = []

            for kw in EVIDENCE_KEYWORDS:
                if kw.lower() in text_lower:
                    matched_keywords.append(kw)
                    keyword_hits[kw] = keyword_hits.get(kw, 0) + 1

            for match in PRICE_PATTERN.finditer(msg.text):
                raw = match.group(1).replace(",", "")
                try:
                    prices_mentioned.append(int(raw))
                except ValueError:
                    pass

            if matched_keywords:
                flagged_messages.append({
                    "role": msg.role,
                    "text": msg.text,
                    "timestamp": msg.timestamp,
                    "keywords": matched_keywords,
                })

        indicators = {
            "price_above_face_value": any(
                kw in keyword_hits
                for kw in ("웃돈", "정가 이상", "프리미엄", "markup", "premium")
            ),
            "multiple_tickets": any(
                kw in keyword_hits
                for kw in ("여러 장", "대량", "multiple tickets", "bulk")
            ),
            "habitual_selling": any(
                kw in keyword_hits
                for kw in ("자주 팔아", "매번", "단골", "사업", "business", "regularly sell")
            ),
        }

        risk_score = sum(indicators.values())

        return {
            "risk_level": "critical" if risk_score >= 3 else "high" if risk_score == 2 else "medium" if risk_score == 1 else "low",
            "risk_score": risk_score,
            "indicators": indicators,
            "keyword_hits": keyword_hits,
            "prices_mentioned": prices_mentioned,
            "flagged_messages": flagged_messages,
            "total_messages_analyzed": len(self.messages),
        }
