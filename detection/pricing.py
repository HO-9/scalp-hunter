from __future__ import annotations

PERFORMANCE_ACT_TABLE = {
    2:  [2, 2, 3, 4, 5, 6, 7, 8, 10],
    3:  [2, 3, 4, 5, 7, 8, 10, 10, 10],
    4:  [3, 4, 5, 6, 8, 10, 12, 15, 15],
    5:  [3, 4, 5, 7, 10, 12, 15, 18, 20],
    6:  [4, 5, 6, 9, 12, 15, 18, 20, 25],
    7:  [4, 6, 8, 10, 13, 18, 20, 25, 30],
    8:  [5, 7, 9, 12, 15, 20, 23, 30, 35],
    9:  [5, 8, 10, 13, 18, 23, 25, 35, 40],
    10: [5, 8, 10, 15, 20, 25, 30, 40, 50],
}

SPORTS_ACT_TABLE = {
    2:  [2, 5, 8, 11, 14, 19, 24, 29, 30],
    3:  [4, 7, 10, 13, 16, 21, 26, 30, 30],
    4:  [6, 9, 10, 15, 18, 23, 28, 30, 30],
    5:  [8, 11, 14, 17, 20, 25, 30, 35, 40],
    6:  [10, 13, 16, 19, 22, 27, 32, 37, 40],
    7:  [12, 15, 18, 21, 24, 29, 34, 39, 40],
    8:  [14, 17, 20, 23, 26, 31, 36, 40, 40],
    9:  [16, 19, 20, 25, 28, 33, 38, 40, 40],
    10: [18, 21, 24, 27, 30, 35, 40, 45, 50],
}

PERFORMANCE_BRACKETS = [50_000, 100_000, 250_000, 500_000, 750_000, 1_000_000, 1_250_000, 1_500_000, 2_000_000]
SPORTS_BRACKETS = [20_000, 100_000, 250_000, 500_000, 750_000, 1_000_000, 1_250_000, 1_500_000, 2_000_000]


def _bracket_index(amount: int, brackets: list[int]) -> int | None:
    if amount < brackets[0]:
        return None
    for i in range(len(brackets) - 1):
        if brackets[i] <= amount < brackets[i + 1]:
            return i
    return len(brackets) - 1


def _ticket_row(count: int) -> int:
    return min(count, 10)


def calculate_fine(
    sale_amount: int,
    ticket_count: int,
    law_type: str = "auto",
    event_category: str | None = None,
) -> dict:
    if law_type == "auto":
        if event_category in ("sports", "esports"):
            law_type = "sports"
        else:
            law_type = "performance"

    if law_type == "sports":
        table = SPORTS_ACT_TABLE
        brackets = SPORTS_BRACKETS
        applicable_law = "국민체육진흥법 제6조의4"
        min_amount = 20_000
        min_tickets = 2
    else:
        table = PERFORMANCE_ACT_TABLE
        brackets = PERFORMANCE_BRACKETS
        applicable_law = "공연법 제4조의4"
        min_amount = 50_000
        min_tickets = 2

    notes: list[str] = []

    if ticket_count == 1:
        notes.append(
            "1매 판매: 위반행위 내용/정도를 고려하여 "
            "판매금액의 5배 범위 내 과징금 부과 가능"
        )
        return {
            "fine_min": 0,
            "fine_max": sale_amount * 5,
            "fine_multiplier_min": 0,
            "fine_multiplier_max": 5,
            "applicable_law": applicable_law,
            "notes": notes,
        }

    if sale_amount < min_amount:
        notes.append(
            f"판매금액 ₩{sale_amount:,}은 최소 기준 "
            f"₩{min_amount:,} 미만 (과징금 부과 기준 미달 가능)"
        )
        return {
            "fine_min": 0,
            "fine_max": sale_amount * 5,
            "fine_multiplier_min": 0,
            "fine_multiplier_max": 5,
            "applicable_law": applicable_law,
            "notes": notes,
        }

    if ticket_count < min_tickets:
        notes.append(f"판매매수 {ticket_count}매는 최소 {min_tickets}매 기준 미달")
        return {
            "fine_min": 0,
            "fine_max": sale_amount * 5,
            "fine_multiplier_min": 0,
            "fine_multiplier_max": 5,
            "applicable_law": applicable_law,
            "notes": notes,
        }

    col = _bracket_index(sale_amount, brackets)
    if col is None:
        notes.append(f"판매금액이 최소 구간 미만 (₩{sale_amount:,})")
        return {
            "fine_min": 0,
            "fine_max": sale_amount * 5,
            "fine_multiplier_min": 0,
            "fine_multiplier_max": 5,
            "applicable_law": applicable_law,
            "notes": notes,
        }

    row_key = _ticket_row(ticket_count)
    multiplier = table[row_key][col]

    fine = sale_amount * multiplier

    notes.append(f"판매금액 ₩{sale_amount:,} × {multiplier}배 = ₩{fine:,}")
    if ticket_count > 10:
        notes.append(f"판매매수 {ticket_count}매 (10매 이상 구간 적용)")

    return {
        "fine_min": sale_amount * 2,
        "fine_max": fine,
        "fine_multiplier_min": 2,
        "fine_multiplier_max": multiplier,
        "applicable_law": applicable_law,
        "notes": notes,
    }
