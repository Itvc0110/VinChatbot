"""Deterministic structured lookup for exact calendar/fee point-lookups (CODEX P0).

For an exact date/amount question, consult a deterministic index built from the structured records
already produced at ingest and return the ONE exact row — never the adjacent near-identical row that
vector retrieval leaks (the grounded-but-wrong residuals). Stage 1 = calendar; fees follow in Stage 2.

Fail-open by construction: a missing artifact, an unparseable query, or a non-unique match returns a
MISS (``None``) so the caller falls back to the existing vector path. No LLM calls, no network — pure
regex/dict, so it strictly *reduces* nondeterminism and latency on the turns it handles.

The single-winner rule is the core guarantee: a result is returned only when exactly one record survives
(academic-year → event-type → term → month → name-concept) filtering. 0 or >1 survivors ⇒ MISS.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinchatbot.app.core.config import Settings, get_settings
from vinchatbot.app.rag.query_engineering import extract_month_years
from vinchatbot.app.schemas.document import DocumentMetadata, stable_hash

logger = logging.getLogger(__name__)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_EN_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Day(s)+month tokens inside an event name, e.g. "21-Jun", "16-20-Aug", "23-27 Aug", "8 - Jan".
# Re-parsed from event_name because the stored date_*_iso fields are unreliable (end truncated / swapped).
_DATE_SPAN_RE = re.compile(
    r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*[- ]\s*"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)",
    re.IGNORECASE,
)
# Strip the leading date prefix off an event name to recover the human description.
_LEADING_DATE_RE = re.compile(
    r"^[\d\s\-–]*(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[\d\s\-–]*)+",
    re.IGNORECASE,
)

# Term → the months its term-less rows (deadlines/holidays) fall in, so e.g. a "Spring" query picks the
# Feb Add/Transfer deadline, not the Oct one. Only used to FILL a missing term, never to override.
_TERM_WINDOWS = {"Fall": {9, 10, 11, 12, 1}, "Spring": {2, 3, 4, 5, 6}, "Summer": {7, 8}}

# Holiday/ceremony concepts (EN candidate names vs EN+VI query phrasings). ORDER matters — first match
# wins, so lunar_new_year is checked before new_year_day ("Lunar New Year" contains "new year").
_CONCEPTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("convocation", ("convocation",), ("convocation",)),
    ("graduation", ("graduation",), ("tốt nghiệp", "graduation")),
    ("hung_king", ("hung king", "commemoration"), ("giỗ tổ", "hùng vương")),
    ("orientation", ("orientation",), ("định hướng", "orientation")),
    ("lunar_new_year", ("lunar",), ("tết", "nguyên đán", "lunar")),
    ("new_year_day", ("new year",), ("năm mới", "tết dương")),
    ("victory_day", ("victory",), ("giải phóng", "victory")),
    ("culture_day", ("culture",), ("văn hóa", "culture")),
    ("independence", ("independence",), ("quốc khánh", "độc lập")),
    ("national_defense", ("national defense",), ("quốc phòng",)),
    ("move_in", ("move-in", "move in", "dorm"), ("ký túc xá", "dorm")),
    ("last_day", ("last day of instruction",), ("ngày cuối", "kết thúc giảng dạy")),
)


@dataclass
class _CalEntry:
    academic_year: str
    term: str | None
    event_type: str
    start_iso: str
    end_iso: str | None
    month_start: int | None
    concept: str | None
    description: str
    tentative: bool
    record_id: str
    parent_doc_id: str
    source_url: str
    metadata: dict[str, Any]


def _ay_bounds(academic_year: str | None) -> tuple[int, int] | None:
    years = re.findall(r"\d{4}", academic_year or "")
    return (int(years[0]), int(years[1])) if len(years) >= 2 else None


def _parse_event_dates(name: str, bounds: tuple[int, int] | None) -> tuple[str | None, str | None]:
    """Re-derive (start_iso, end_iso) from the full event name. Year from the academic-year bounds
    (Sep–Dec → first year, Jan–Aug → second), matching the ingest parser's convention."""
    matches = list(_DATE_SPAN_RE.finditer(name or ""))
    if not matches or not bounds:
        return None, None
    start_year, end_year = bounds

    def to_iso(day: int, month: int) -> str:
        year = start_year if month >= 9 else end_year
        return f"{year:04d}-{month:02d}-{day:02d}"

    first = matches[0]
    start_month = _MONTHS[first.group(3).lower()]
    start_iso = to_iso(int(first.group(1)), start_month)
    end_iso: str | None = None
    if len(matches) >= 2:  # "21-Jun-02-Jul" → second token is the end
        second = matches[1]
        end_month = _MONTHS[second.group(3).lower()]
        end_iso = to_iso(int(second.group(2) or second.group(1)), end_month)
    elif first.group(2):  # "16-20-Aug" → range within one month
        end_iso = to_iso(int(first.group(2)), start_month)
    return start_iso, end_iso


def _strip_leading_date(name: str) -> str:
    return _LEADING_DATE_RE.sub("", name or "").strip(" -–") or (name or "")


def _name_concept(name: str) -> str | None:
    low = (name or "").lower()
    for concept, en_kw, _vi in _CONCEPTS:
        if any(kw in low for kw in en_kw):
            return concept
    return None


def _query_concept(query: str) -> str | None:
    low = (query or "").lower()
    for concept, en_kw, vi_kw in _CONCEPTS:
        if any(kw in low for kw in en_kw) or any(kw in low for kw in vi_kw):
            return concept
    return None


def _parse_term(query: str) -> str | None:
    low = (query or "").lower()
    if re.search(r"\bfall\b", low):
        return "Fall"
    if re.search(r"\bspring\b", low):
        return "Spring"
    if re.search(r"\bsummer\b", low):
        return "Summer"
    return None


def _term_window(month: int | None) -> str | None:
    for term, months in _TERM_WINDOWS.items():
        if month in months:
            return term
    return None


def _query_event_type(query: str) -> str:
    """Bilingual (EN+VI) event-type classifier for the QUERY. Mirrors ingest infer_event_type but adds
    the Vietnamese phrasings the eval uses ('đánh giá môn', 'chấm điểm', 'đăng ký môn', ...)."""
    low = (query or "").lower()
    if "drop" in low or "hủy môn" in low or "rút môn" in low:
        return "course_drop_deadline"
    if "add" in low or "transfer credit" in low or "chuyển tín chỉ" in low:
        return "add_transfer_deadline"
    if "instruction begins" in low or "bắt đầu giảng dạy" in low or "khai giảng" in low:
        return "instruction_begins"
    if any(k in low for k in ("marking", "appeal", "grade release", "chấm điểm", "phúc khảo", "công bố điểm")):
        return "grade_release"
    if "evaluation" in low or "đánh giá môn" in low or "đánh giá học phần" in low:
        return "evaluation_period"
    if ("exam" in low or "lịch thi" in low) and ("schedule" in low or "release" in low or "công bố" in low):
        return "exam_schedule_release"
    if "exam" in low or "kỳ thi" in low or "lịch thi" in low:
        return "exam_period"
    if "timetable" in low or "thời khóa biểu" in low:
        return "timetable_release"
    if "gradebook" in low:
        return "gradebook"
    if "holiday" in low or "tết" in low or "lunar" in low or "nghỉ lễ" in low:
        return "holiday"
    if any(k in low for k in ("registration", "enrollment", "đăng ký môn", "đăng ký học phần", "đăng ký")):
        return "registration"
    return "academic_event"


def _fmt_en(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{_EN_MONTHS[int(month) - 1]} {int(day)}, {year}"


def _fmt_vi(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{int(day)} tháng {int(month)} năm {year}"


# --- Fee (Stage 2) ----------------------------------------------------------------------------
# The tuition matrix lives in a financial `table_record`: program × granularity. ORDER matters in each
# list (first keyword match wins). "standard"/"other" Bachelor map to the same "Other Bachelor" row.
_PROGRAM_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("nursing", ("nursing", "điều dưỡng", "dieu duong")),
    ("medicine", ("doctor of medicine", "medicine", "y khoa", "y đa khoa")),
    ("other_bachelor", ("other bachelor", "standard", "regular", "cử nhân khác", "cu nhan khac",
                        "tiêu chuẩn", "tieu chuan")),
)
# per_credit / per_semester checked before per_year so "theo tín chỉ" / "học kỳ" win over a stray "năm".
_GRANULARITY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("per_credit", ("per credit", "/credit", "tín chỉ", "tin chi")),
    ("per_semester", ("per semester", "/semester", "học kỳ", "hoc ky", "mỗi kỳ")),
    ("per_year", ("per year", "per academic year", "/year", "năm học", "nam hoc", "mỗi năm",
                  "hằng năm", "hàng năm", "annual")),
)
_PROGRAM_LABELS = {
    "nursing": "Bachelor of Nursing / Cử nhân Điều dưỡng",
    "medicine": "Doctor of Medicine",
    "other_bachelor": "Other Bachelor Programs / các chương trình Cử nhân khác (tiêu chuẩn)",
}
_GRANULARITY_LABELS = {
    "per_year": "mỗi năm học / per academic year",
    "per_semester": "mỗi học kỳ / per semester",
    "per_credit": "theo tín chỉ / per credit",
}


def _classify(text: str, table: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    for label, keywords in table:
        if any(kw in text for kw in keywords):
            return label
    return None


def _amount(cell: str) -> str | None:
    """Extract the comma-formatted amount from a tariff cell ("349,650,000/year" → "349,650,000")."""
    match = re.search(r"\d[\d,]{3,}\d", cell or "")
    return match.group(0) if match else None


def is_official_record(record: dict[str, Any]) -> bool:
    """True unless the record's source domain is classified ``external_low`` (unofficial).

    Used by ``scripts/build_structured_index.py`` to keep EXTERNAL pages' dates/amounts OUT of the
    authoritative deterministic calendar/fee lookup — an unofficial page must never surface as an official
    answer (it stays searchable as prose, already deprioritised ×0.7 by the retrieval trust boost). Reuses
    the canonical ``classify_domain`` so the official allowlist stays single-sourced. The import is lazy:
    this runs only at the offline index-build step, so the serving import graph stays light.
    """
    from vinchatbot.app.ingest.normalizer import classify_domain

    _, _, source_trust = classify_domain(record.get("source_url") or "")
    return source_trust != "external_low"


def is_authoritative_structured_source(record: dict[str, Any]) -> bool:
    """True only if a structured record comes from a real CALENDAR or FEE *document* — gated by the source's
    document kind, not its host. Used by ``scripts/build_structured_index.py`` to keep the DETERMINISTIC
    lookup authoritative once the corpus includes college/admissions/scholarship pages:

    - ``calendar_event`` is authoritative only from an actual academic-calendar document (``calendar_pdf`` /
      ``calendar_page``) — so the current AND older-year official calendars feed the AY-filtered lookup, but a
      date merely *mentioned* on a news/admissions page does NOT.
    - financial ``table_record`` is authoritative only from the official tariff (``financial_policy``) — a fee
      *mentioned* on a scholarship/admissions page does NOT.

    A spurious record would otherwise surface a wrong, high-confidence answer that bypasses rerank. Lazy
    import keeps the serving import graph light (offline index-build only).
    """
    from vinchatbot.app.ingest.normalizer import classify_domain, infer_source_kind

    url = record.get("source_url") or ""
    if record.get("record_type") == "calendar_event":
        # Real academic-calendar documents only (current + older academic years) — never a date merely
        # mentioned on a news/admissions/policy page.
        return infer_source_kind(url) in {"calendar_pdf", "calendar_page"}
    # Financial rows: any OFFICIAL policy.vinuni document (the tariff + other policy fee schedules) — excludes
    # fee amounts merely mentioned on admissions/scholarship/college pages.
    _, domain_type, _ = classify_domain(url)
    return domain_type == "policy"


def stream_json_array(path: Path, chunk_size: int = 1 << 20):
    """Yield top-level objects from a (possibly huge) JSON-array file WITHOUT loading it all into
    memory. The full structured_records.json is ~150 MB → ~2 GB parsed, which OOMs `json.loads` under
    the agent process's memory pressure. raw_decode peels one record at a time; memory stays bounded."""
    decoder = json.JSONDecoder()
    buffer = ""
    started = False
    with path.open(encoding="utf-8") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if chunk:
                buffer += chunk
            if not started:
                idx = buffer.find("[")
                if idx == -1:
                    if not chunk:
                        return
                    continue
                buffer = buffer[idx + 1:]
                started = True
            while True:
                stripped = buffer.lstrip()
                if not stripped:
                    buffer = stripped
                    break
                if stripped[0] == "]":
                    return
                if stripped[0] == ",":
                    stripped = stripped[1:].lstrip()
                buffer = stripped
                try:
                    obj, end = decoder.raw_decode(buffer)
                except ValueError:
                    break  # incomplete object in buffer → read more
                yield obj
                buffer = buffer[end:]
            if not chunk:
                return


class StructuredLookup:
    """In-memory deterministic index over calendar (Stage 1) structured records."""

    def __init__(self, records_path: str) -> None:
        self._calendar: dict[str, list[_CalEntry]] = {}
        self._year_min: int | None = None  # span of covered academic years (start..end)
        self._year_max: int | None = None
        self._fee_matrix: dict[str, dict[str, str]] = {}  # program -> granularity -> amount (Stage 2)
        self._fee_meta: dict[str, Any] = {}
        try:
            self._build(records_path)
        except Exception:
            logger.warning("Structured-lookup index build failed; lookups disabled.", exc_info=True)
            self._calendar = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> StructuredLookup:
        if settings.structured_lookup_records_path:
            return cls(settings.structured_lookup_records_path)
        processed = Path(settings.processed_data_dir)
        # Prefer the COMPACT derived index (scripts/build_structured_index.py) — the full
        # structured_records.json is ~150 MB and OOMs under the agent process's memory pressure.
        compact = processed / "structured_index.json"
        full = processed / "structured_records.json"
        return cls(str(compact if compact.exists() else full))

    def _build(self, records_path: str) -> None:
        path = Path(records_path)
        if not path.exists():
            logger.info("Structured lookup: records file not found at %s; lookups disabled.", path)
            return
        count = 0
        for record in stream_json_array(path):  # streamed → bounded memory even on the 150 MB full file
            # Per-record resilience: a single malformed record must never empty the whole index.
            try:
                record_type = record.get("record_type")
                if record_type == "calendar_event":
                    entry = self._to_calendar_entry(record)
                    if entry is not None:
                        self._calendar.setdefault(entry.academic_year, []).append(entry)
                        count += 1
                elif record_type == "table_record" and not self._fee_matrix:
                    self._maybe_index_fee_table(record)
            except Exception:
                logger.debug("Structured lookup: skipped a malformed record.", exc_info=True)
        starts = [b[0] for ay in self._calendar if (b := _ay_bounds(ay))]
        ends = [b[1] for ay in self._calendar if (b := _ay_bounds(ay))]
        self._year_min = min(starts) if starts else None
        self._year_max = max(ends) if ends else None
        logger.info(
            "Structured lookup: indexed %d calendar events across %d academic years (span %s-%s); "
            "fee matrix programs=%s.",
            count,
            len(self._calendar),
            self._year_min,
            self._year_max,
            sorted(self._fee_matrix),
        )

    def _to_calendar_entry(self, record: dict[str, Any]) -> _CalEntry | None:
        data = record.get("data") or {}
        academic_year = data.get("academic_year")
        event_type = data.get("event_type")
        name = data.get("event_name") or ""
        if not academic_year or not event_type or not name:
            return None
        start_iso, end_iso = _parse_event_dates(name, _ay_bounds(academic_year))
        if not start_iso:  # fall back to stored ISO only if the re-parse found nothing
            start_iso = data.get("date_start_iso")
            end_iso = end_iso or data.get("date_end_iso")
        if not start_iso:
            return None
        return _CalEntry(
            academic_year=academic_year,
            term=data.get("term"),
            event_type=event_type,
            start_iso=start_iso,
            end_iso=end_iso if end_iso and end_iso != start_iso else None,
            month_start=int(start_iso[5:7]),
            concept=_name_concept(name),
            description=_strip_leading_date(name),
            tentative="tentative" in name.lower(),
            record_id=str(record.get("record_id") or stable_hash(name)),
            parent_doc_id=str(record.get("parent_doc_id") or ""),
            source_url=data.get("source_url") or record.get("source_url") or "",
            metadata=dict(record.get("metadata") or {}),
        )

    def _maybe_index_fee_table(self, record: dict[str, Any]) -> None:
        """Index the financial tuition matrix table_record (program × granularity). Ignores other
        financial tables (admin-services fees etc.) — keyed by the 'Tuition Fee per' header."""
        if (record.get("metadata") or {}).get("subcategory") != "financial":
            return
        rows = (record.get("data") or {}).get("rows") or []
        if len(rows) < 2:
            return
        header = [str(cell).lower() for cell in rows[0]]
        if not any("tuition fee per" in cell for cell in header):
            return
        col_gran: dict[int, str] = {}
        for index, cell in enumerate(header):
            if "per credit" in cell:
                col_gran[index] = "per_credit"
            elif "per semester" in cell:
                col_gran[index] = "per_semester"
            elif "per academic year" in cell or "per year" in cell:
                col_gran[index] = "per_year"
        matrix: dict[str, dict[str, str]] = {}
        for row in rows[1:]:
            program = _classify(str(row[0]).lower(), _PROGRAM_KEYWORDS)
            if not program:
                continue
            cells = {g: amt for i, g in col_gran.items() if i < len(row) and (amt := _amount(str(row[i])))}
            if cells:
                matrix[program] = cells
        if matrix:
            self._fee_matrix = matrix
            md = dict(record.get("metadata") or {})
            md["_record_id"] = str(record.get("record_id") or "")
            md["_parent_doc_id"] = str(record.get("parent_doc_id") or "")
            md["_source_url"] = record.get("source_url") or md.get("source_url") or ""
            self._fee_meta = md

    def lookup(
        self, query: str, domain: str = "calendar", list_mode: bool = False
    ) -> dict[str, Any] | None:
        """Return the tool JSON payload on a unique deterministic hit, a definitive no-data marker
        (empty results → caller refuses, skips vector), or None (→ vector fallback). `list_mode` (Phase
        1.27/A6) enumerates ALL matching rows instead of the single point match."""
        try:
            if domain == "calendar":
                entry = self._match_calendar(query, list_mode=list_mode)
                if entry == "no_data":
                    # The query names an academic year outside the indexed span → there is definitively
                    # no calendar data. Return empty results so the agent refuses honestly instead of
                    # letting vector search surface a wrong-year neighbour the LLM might graft onto.
                    return {"results": [], "no_data": True}
                if isinstance(entry, list):  # Phase 1.27b list mode: all matching events, multi-row
                    return self._format_calendar_list(entry)
                if isinstance(entry, _CalEntry):
                    return self._format_calendar(entry)
            elif domain == "fee":
                return self._match_fee(query, list_mode=list_mode)
        except Exception:
            logger.debug("Structured lookup raised; falling back to vector search.", exc_info=True)
        return None

    def _match_fee(self, query: str, list_mode: bool = False) -> dict[str, Any] | None:
        low = query.lower().replace("-", " ")  # so "per-credit" matches the "per credit" granularity keyword
        if any(k in low for k in ("currency", "tiền tệ", "tien te", "đơn vị tiền", "don vi tien", "bằng đơn vị")):
            return self._fee_payload(
                "Học phí của VinUni được niêm yết bằng đồng Việt Nam (VND). / "
                "VinUni tuition fees are listed in Vietnamese Dong (VND).",
                fee_type="tuition",
            )
        if not self._fee_matrix:
            return None
        program = _classify(low, _PROGRAM_KEYWORDS)
        granularity = _classify(low, _GRANULARITY_KEYWORDS)
        # Phase 1.27a list mode: enumerate the full matrix when the answer spans >1 cell — a granularity
        # across ALL programs (no program named), or all granularities for one program. Deterministic from
        # the in-memory matrix → exact rows, no vector/LLM, auto-updates when the table is re-indexed.
        if list_mode:
            programs = [program] if program else list(self._fee_matrix)
            grans = [granularity] if granularity else ["per_year", "per_semester", "per_credit"]
            if len(programs) * len(grans) > 1:
                lines = []
                for prog in programs:
                    cells = self._fee_matrix.get(prog, {})
                    parts = [f"{_GRANULARITY_LABELS[g]}: {cells[g]} VND" for g in grans if g in cells]
                    if parts:
                        lines.append(f"{_PROGRAM_LABELS[prog]} — " + "; ".join(parts))
                if lines:
                    text = "Học phí niêm yết / Listed tuition fees:\n- " + "\n- ".join(lines)
                    return self._fee_payload(text, fee_type="tuition")
        # Point lookup (unchanged): one program × one granularity.
        if not program:  # no program named → MISS (don't guess a default program → no leakage)
            return None
        gran = granularity or "per_year"  # headline figure if unspecified
        amount = self._fee_matrix.get(program, {}).get(gran)
        if not amount:
            return None
        text = (
            f"Học phí niêm yết / Listed tuition fee — {_PROGRAM_LABELS[program]} — "
            f"{_GRANULARITY_LABELS[gran]}: {amount} VND."
        )
        return self._fee_payload(text, fee_type="tuition")

    def _fee_payload(self, text: str, fee_type: str) -> dict[str, Any]:
        payload = dict(self._fee_meta)
        source_url = payload.get("_source_url") or payload.get("source_url") or ""
        metadata = DocumentMetadata.model_validate(
            {
                **{k: v for k, v in payload.items() if not k.startswith("_")},
                "source_url": source_url,
                "canonical_url": payload.get("canonical_url") or source_url,
                "document_title": payload.get("document_title") or "Financial Regulations and Tariff",
                "content_hash": payload.get("content_hash") or stable_hash(text),
                "parent_doc_id": payload.get("_parent_doc_id") or stable_hash(source_url),
                "chunk_id": stable_hash(f"structured_lookup:fee:{payload.get('_record_id')}:{text}"),
                "category": payload.get("category") or "student_affairs",
                "subcategory": "financial",
                "record_type": "table_record",
                "fee_type": fee_type,
            }
        )
        return {"results": [{"text": text, "score": 1.0, "metadata": metadata.model_dump()}]}

    def _out_of_span(self, query: str) -> bool:
        """True when the query names ONLY academic years outside the covered span AND looks like a
        calendar point-lookup (term / specific event / named concept) — i.e. definitively no data."""
        if self._year_min is None or self._year_max is None:
            return False
        years = [int(y) for y in re.findall(r"20\d{2}", query)]
        if not years or not all(y < self._year_min or y > self._year_max for y in years):
            return False
        return bool(
            _parse_term(query)
            or _query_event_type(query) != "academic_event"
            or _query_concept(query)
        )

    def _resolve_academic_year(self, query: str) -> str | None:
        available = set(self._calendar)
        explicit = re.search(r"(20\d{2})\s*[-–/]\s*(20\d{2})", query)
        if explicit and int(explicit.group(2)) == int(explicit.group(1)) + 1:
            candidate = f"{explicit.group(1)}-{explicit.group(2)}"
            if candidate in available:
                return candidate
        term = _parse_term(query)
        years = [int(y) for y in re.findall(r"20\d{2}", query)]
        months = {month for month, _year in extract_month_years(query)}
        if years:
            year = years[0]
            if term == "Fall":
                candidates = [f"{year}-{year + 1}"]
            elif term in ("Spring", "Summer"):
                candidates = [f"{year - 1}-{year}"]
            elif months:
                candidates = [f"{year}-{year + 1}"] if min(months) >= 9 else [f"{year - 1}-{year}"]
            else:
                candidates = [f"{year}-{year + 1}", f"{year - 1}-{year}"]
            for candidate in candidates:
                if candidate in available:
                    return candidate
        return None

    def _match_calendar(self, query: str, list_mode: bool = False) -> _CalEntry | list[_CalEntry] | str | None:
        academic_year = self._resolve_academic_year(query)
        if not academic_year:
            return "no_data" if self._out_of_span(query) else None
        candidates = self._calendar.get(academic_year, [])
        if not candidates:
            return None

        event_type = _query_event_type(query)
        query_concept = _query_concept(query)

        if event_type == "academic_event":
            if not query_concept:  # a bare academic event we can't disambiguate → MISS
                return None
            pool = [e for e in candidates if e.event_type == "academic_event" and e.concept == query_concept]
        elif event_type == "holiday":
            pool = [e for e in candidates if e.event_type == "holiday"]
            if query_concept:
                pool = [e for e in pool if e.concept == query_concept]
        else:
            pool = [e for e in candidates if e.event_type == event_type]

        # Phase 1.27b list mode: enumerate ALL matching events (e.g. "all add/drop deadlines", "deadlines for
        # each term") — apply an optional month filter but NOT the single-term narrowing below; return the list
        # sorted by date. Deterministic from the in-memory calendar index (no vector aggregation needed).
        if list_mode:
            months = {month for month, _year in extract_month_years(query)}
            if months:
                narrowed = [e for e in pool if e.month_start in months]
                if narrowed:
                    pool = narrowed
            return sorted(pool, key=lambda e: e.start_iso) if pool else None

        term = _parse_term(query)
        if term and len(pool) > 1:
            filtered = [
                e for e in pool
                if e.term == term or (e.term is None and _term_window(e.month_start) == term)
            ]
            if filtered:
                pool = filtered

        months = {month for month, _year in extract_month_years(query)}
        if months and len(pool) > 1:
            filtered = [e for e in pool if e.month_start in months]
            if filtered:
                pool = filtered

        return pool[0] if len(pool) == 1 else None

    def _format_calendar(self, entry: _CalEntry) -> dict[str, Any]:
        start_year = entry.start_iso[:4]
        term_label = f"{entry.term} {start_year}" if entry.term else f"năm học {entry.academic_year}"
        if entry.end_iso:
            date_line = (
                f"từ {_fmt_vi(entry.start_iso)} đến {_fmt_vi(entry.end_iso)} "
                f"(from {_fmt_en(entry.start_iso)} to {_fmt_en(entry.end_iso)})"
            )
        else:
            date_line = f"{_fmt_vi(entry.start_iso)} ({_fmt_en(entry.start_iso)})"
        tentative = " (dự kiến / tentatively)" if entry.tentative else ""
        text = (
            f"Lịch học VinUni / VinUni academic calendar — {entry.description} — {term_label}.{tentative} "
            f"Thời gian / Date: {date_line}."
        )
        metadata = self._build_metadata(entry)
        return {"results": [{"text": text, "score": 1.0, "metadata": metadata.model_dump()}]}

    def _format_calendar_list(self, entries: list[_CalEntry]) -> dict[str, Any]:
        """Phase 1.27b: render MULTIPLE calendar events as a multi-row list (one source — the calendar)."""
        lines = []
        for e in entries:
            start_year = e.start_iso[:4]
            term_label = f"{e.term} {start_year}" if e.term else f"năm học {e.academic_year}"
            if e.end_iso:
                date_line = (
                    f"từ {_fmt_vi(e.start_iso)} đến {_fmt_vi(e.end_iso)} "
                    f"(from {_fmt_en(e.start_iso)} to {_fmt_en(e.end_iso)})"
                )
            else:
                date_line = f"{_fmt_vi(e.start_iso)} ({_fmt_en(e.start_iso)})"
            tentative = " (dự kiến / tentatively)" if e.tentative else ""
            lines.append(f"{e.description} — {term_label}{tentative}: {date_line}")
        text = "Lịch học VinUni / VinUni academic calendar:\n- " + "\n- ".join(lines)
        metadata = self._build_metadata(entries[0])  # all rows share the one academic-calendar source
        return {"results": [{"text": text, "score": 1.0, "metadata": metadata.model_dump()}]}

    def _build_metadata(self, entry: _CalEntry) -> DocumentMetadata:
        payload = dict(entry.metadata)
        source_url = entry.source_url or payload.get("source_url") or ""
        payload.update(
            {
                "source_url": source_url,
                "canonical_url": payload.get("canonical_url") or source_url,
                "document_title": payload.get("document_title") or "VinUni Academic Calendar",
                "content_hash": payload.get("content_hash") or stable_hash(entry.record_id),
                "parent_doc_id": entry.parent_doc_id or payload.get("parent_doc_id") or stable_hash(source_url),
                "chunk_id": stable_hash(f"structured_lookup:calendar:{entry.record_id}"),
                "academic_year": entry.academic_year,
                "term": entry.term,
                "event_type": entry.event_type,
                "record_type": "calendar_event",
                "category": payload.get("category") or "academic",
                "subcategory": payload.get("subcategory") or "calendar",
            }
        )
        return DocumentMetadata.model_validate(payload)


_INSTANCE: StructuredLookup | None = None


def get_structured_lookup(settings: Settings | None = None) -> StructuredLookup:
    """Return the process-wide cached lookup (built once from the structured-records artifact)."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = StructuredLookup.from_settings(settings or get_settings())
    return _INSTANCE


def reset_structured_lookup_for_tests() -> None:
    global _INSTANCE
    _INSTANCE = None
