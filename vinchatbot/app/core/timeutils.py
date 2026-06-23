"""Serving-time date helpers (Phase 1.9 — time awareness).

The agent had no notion of "now", so it could not answer "what semester am I in?". These helpers
compute the current academic year + term from a datetime, mirroring the Sep→Aug boundary already used
at ingest in ``parsers._date_token_to_iso`` (month >= 9 ⇒ the start year of the academic year). Term
labels match the ingest values ("Fall"/"Spring"/"Summer", see ``parsers._term_from_text``).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

# VinUni operates on Vietnam local time; "today" must be anchored there, not the server's UTC.
VINUNI_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# VinUni academic year runs Sep → Aug. Fall = Sep–Dec; Spring = Jan–May; Summer = Jun–Aug.
_FALL_START_MONTH = 9
_SUMMER_START_MONTH = 6


def now_in_vietnam() -> datetime:
    """Current wall-clock time in VinUni's timezone."""
    return datetime.now(VINUNI_TZ)


def current_academic_context(now: datetime) -> tuple[str, str]:
    """Return ``(academic_year, term)`` for ``now`` using the Sep→Aug boundary.

    Examples: 2026-09-01 → ("2026-2027", "Fall"); 2026-06-18 → ("2025-2026", "Summer");
    2026-03-10 → ("2025-2026", "Spring").
    """
    month, year = now.month, now.year
    if month >= _FALL_START_MONTH:
        return f"{year}-{year + 1}", "Fall"
    if month >= _SUMMER_START_MONTH:
        return f"{year - 1}-{year}", "Summer"
    return f"{year - 1}-{year}", "Spring"


def current_time_context(now: datetime | None = None) -> dict[str, str]:
    """Bundle the fields needed for prompt injection / the get_current_datetime tool."""
    now = now or now_in_vietnam()
    academic_year, term = current_academic_context(now)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"),
        "academic_year": academic_year,
        "term": term,
    }


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# A "pure time" question is one whose ENTIRE answer is the current date / weekday / term / academic
# year — derivable from the clock alone. It must NEVER hijack a calendar-DATA question ("which semester
# is course X in?", "when does the term start?", "is today the opening day?", "how long until add/drop?")
# — those flow to the agent (which has the injected date + the get_current_datetime tool). So:
#   • the date branch requires an explicit date/weekday ask WITH a quantifier (bao nhiêu/mấy / "date");
#   • the term/year branch requires BOTH a time-subject word AND an explicit present-time marker
#     ("now/currently/hiện tại/đang/am I in/is it?") — "học kỳ nào" alone is NOT enough.
# Matching is accent-insensitive (Vietnamese diacritics stripped) and case-insensitive.
# Date / weekday "what is it now" asks. The date/number quantifier is anchored to today/now so a
# data question ("Hạn nộp là ngày mấy?" / "what is the deadline date?") is NOT matched.
_TODAY_RE = re.compile(
    r"what day is (it|today)"
    r"|what(?:'s| is) (?:the |today'?s )?date"
    r"|today'?s date|current date"
    r"|(?:hom nay|bay gio|hien tai) (?:la )?(?:ngay|thu) (?:bao nhieu|may)"
    r"|(?:hom nay|bay gio) (?:la )?(?:thu|ngay) may"
    r"|(?:ngay|thu) (?:bao nhieu|may) roi",
    re.IGNORECASE,
)
# "Which term/year is it NOW" asks. Enumerated structurally so the now-sense binds to the subject —
# "current SEMESTER" (not "current tuition … semester"), "what semester am I IN" (not "what semester
# is the exam in"). "học kỳ nào" alone never matches; it needs an adjacent hiện tại/đang/bây giờ.
_TERM_NOW_RE = re.compile(
    r"(?:what|which) (?:semester|term|academic year|year)(?:'?s)? (?:am i|are we|is it)"
    r"|current (?:semester|term|academic year|year)"
    r"|(?:semester|term|academic year|year) (?:am i|are we) (?:currently )?in"
    r"|dang o (?:hoc ky|nam hoc|ky hoc)"
    r"|(?:hoc ky|nam hoc|ky hoc) hien tai"
    r"|hien tai.{0,25}(?:hoc ky|nam hoc).{0,15}nao"
    r"|bay gio (?:la )?(?:nam hoc|hoc ky)"
    r"|(?:nam hoc|hoc ky) nao.{0,12}(?:hien tai|bay gio)",
    re.IGNORECASE,
)


def is_pure_time_question(message: str) -> bool:
    """True only for questions whose entire answer is the current date / weekday / term / academic
    year (answerable from the clock alone). Conservative: when unsure it returns False so the
    question flows to the agent rather than being wrongly short-circuited."""
    t = _strip_accents(message or "")
    return bool(_TODAY_RE.search(t) or _TERM_NOW_RE.search(t))
