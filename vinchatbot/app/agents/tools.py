from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from vinchatbot.app.agents.guardrails import answer_language, scan_for_injection
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.observability import get_user_message, mark_point_lookup, record_stage
from vinchatbot.app.rag.canonical_lookup import AID_URL, canonical_doc_match
from vinchatbot.app.rag.citations import excerpt
from vinchatbot.app.rag.context import dedup_by_text, reorder_for_long_context
from vinchatbot.app.rag.forms_catalog import match_forms
from vinchatbot.app.rag.policy_lookup import match as policy_doc_match
from vinchatbot.app.rag.query_engineering import (
    expand_query,
    is_list_lookup,
    is_point_lookup,
    normalize_date_phrases,
    reciprocal_rank_fusion,
)
from vinchatbot.app.rag.retriever import Retriever
from vinchatbot.app.rag.structured_lookup import get_structured_lookup


def build_retrieval_tools(retriever: Retriever):
    try:
        from langchain.tools import tool
    except ImportError as exc:
        raise RuntimeError("Install langchain to build agent tools.") from exc

    async def _search(
        query: str,
        filters: dict[str, Any] | None = None,
        enforced_filters: dict[str, Any] | None = None,
        cross_lingual: bool = False,
    ) -> str:
        settings = get_settings()
        caller_filters = {key: value for key, value in (filters or {}).items() if value}

        # Soft routing: the specialist's category goes in as a *boost hint* (not a hard
        # filter), so a mis-route never blanks out results. Otherwise enforce it.
        if settings.enable_soft_routing:
            merged_filters = caller_filters
            boost_hints = enforced_filters or None
        else:
            merged_filters = {**caller_filters, **(enforced_filters or {})}
            boost_hints = None

        max_k = settings.retrieval_max_k
        routed = enforced_filters or {}
        subcat = routed.get("subcategory") or routed.get("category")

        # Canonical doc-pin match (Phase 1.30/S15+S16) — computed ONCE up front because it must take
        # precedence over the structured fee lookup below: an aid/subsidy question ("what % subsidy")
        # is an aid-POLICY fact that lives on the scholarship page, not a tariff row, so the fee lookup
        # matching it is a false-positive that would early-return a wrong fee record and pre-empt the pin.
        if getattr(settings, "enable_canonical_doc_pin", False):
            try:
                canon_match = canonical_doc_match(get_user_message() or query)
            except Exception:
                canon_match = None
        else:
            canon_match = None
        # On the FINANCIAL route only the aid pin applies: a program/admission name there means a FEE
        # question ("tuition fee per credit for the MD program"), which the structured fee lookup answers —
        # NOT a doc-pin target. (A program-credit COUNT question routes to services, not financial, so it
        # still pins.) So a program/admission canon_match on the financial route is suppressed.
        canon_applies = bool(canon_match) and not (subcat == "financial" and canon_match != AID_URL)

        # Phase 1.27/A6 list mode: a multi-row question ("tuition for ALL programs") needs a WIDER context so
        # every row reaches the answer, and must NOT be narrowed by the point-lookup path. Detect on the USER's
        # raw question (contextvar) so the agent's reformulation can't drop the "all/each". Gated → byte-identical.
        list_mode = getattr(settings, "enable_list_mode", False) and is_list_lookup(
            get_user_message() or query, subcat
        )
        if list_mode:
            max_k = max(max_k, settings.retrieval_list_max_k)

        # Canonical policy-page boost (Phase 1.20): for policy-domain queries, prefer the dedicated
        # all-policies detail page (policy_html / financial_policy) over governance-reg PDFs. Threaded as a
        # boost hint → apply_metadata_boosts. (subcat "student_affairs" = the policy specialist's routing.)
        if getattr(settings, "enable_canonical_policy_boost", False) and subcat == "student_affairs":
            boost_hints = {**(boost_hints or {}), "prefer_canonical": True}

        # Structured lookup first (CODEX P0): a deterministic record match returns the ONE exact row —
        # never the adjacent near-identical date/fee row that vector retrieval leaks (the
        # grounded-but-wrong residuals). Stage 1 = calendar, Stage 2 = fees. Gated + fail-open: any
        # miss/error falls through to the vector path below, byte-identical to today.
        # Skip the FEE lookup when the canonical doc-pin claims this query (aid/subsidy/scholarship %): that
        # fact lives on the aid page, not a tariff row, so letting the fee lookup early-return here would
        # pre-empt the pin with a wrong record. Calendar structured lookup is never pre-empted (the pin
        # excludes calendar), and real fee queries don't match canonical_doc_match → fee lookup still fires.
        if (
            getattr(settings, "enable_structured_lookup", False)
            and subcat in ("calendar", "financial")
            and not (subcat == "financial" and canon_applies)
        ):
            domain = "calendar" if subcat == "calendar" else "fee"
            started = time.perf_counter()
            try:
                # Match on the USER's raw question (threaded via contextvar), not the agent's run-to-run
                # variable tool-query reformulation — so the deterministic lookup fires reliably (1.19).
                hit = get_structured_lookup(settings).lookup(
                    get_user_message() or query, domain, list_mode=list_mode
                )
            except Exception:
                hit = None
            if hit is not None:
                mark_point_lookup()
                # 0 model calls → the Phase-C ledger shows this turn's latency/cost DROP vs vector search.
                record_stage(
                    "structured_lookup", calls=0, latency_ms=(time.perf_counter() - started) * 1000
                )
                # no_data (year outside the indexed span): return EMPTY results so the agent refuses
                # honestly with no citation → graceful degradation, instead of grafting a wrong year.
                return json.dumps({"results": hit.get("results", [])}, ensure_ascii=False)

        point_lookup = (
            settings.enable_adaptive_retrieval and is_point_lookup(query, subcat) and not list_mode
        )
        if point_lookup:
            mark_point_lookup()
        expand_sections = point_lookup or list_mode
        fuse_then_rerank = settings.enable_rerank_after_fusion or point_lookup

        # Query expansion — two independent kinds:
        #  • paraphrase (same-language): recall for prose; OFF for calendar point-lookups, whose
        #    date-grid neighbours are distractors (Phase 1.7).
        #  • cross-lingual (VI↔EN, Phase 1.8): one translation variant on EVERY domain.
        # Both are LLM-generated and the proven source of retrieval nondeterminism (Phase 1.11).
        paraphrase = settings.enable_query_expansion and not (point_lookup and subcat == "calendar")
        # Cross-lingual (VI↔EN) is now AGENT-DECIDED (Phase 1.17 pulled forward): the specialist sets
        # cross_lingual=True on a retry when its first search in the user's language found nothing — so a
        # strong native-language query stays clean/deterministic, and the translation variant fires only
        # when actually needed (e.g. a VI question whose answer lives in an EN-only document). The global
        # ENABLE_CROSSLINGUAL_EXPANSION (default off) still forces it always-on if a deployment wants that.
        cross_lingual = bool(cross_lingual) or settings.enable_crosslingual_expansion
        # Cross-lingual policy escalation (Phase 1.20): VI policy questions undermatch the (often EN)
        # canonical policy doc (the EN twin retrieves it #1). For a VI question routed to the policy domain,
        # force the EN translation variant so the canonical doc is RRF-fused in. Matches the USER's raw
        # question (contextvar), not the agent's reformulation. Calendar/financial excluded by subcat.
        if (
            getattr(settings, "enable_crosslingual_policy", False)
            and subcat == "student_affairs"
            and answer_language(get_user_message() or query) == "vi"
        ):
            cross_lingual = True
        # Phase 1.30/S15+S16: VI fact-intent (program/admission/aid) queries undermatch the (often EN)
        # curriculum/aid doc — force the EN translation variant so it is RRF-fused in (the canonical doc-pin
        # below then guarantees the right doc leads). Detected on the USER's raw question.
        if canon_applies and answer_language(get_user_message() or query) == "vi":
            cross_lingual = True
        # Deterministic both-language date forms (Phase 1.12): "tháng 6 năm 2026" <-> "June 2026" <->
        # "6/2026". Pure regex (no LLM) → consistency-safe, and added for date queries so a date matches
        # the corpus regardless of phrasing. No-op for non-date queries.
        date_variants = (
            normalize_date_phrases(query) if settings.enable_date_normalization else []
        )

        async def _single_query() -> list:
            return await retriever.search(
                query=query,
                filters=merged_filters,
                limit=max_k,
                boost_hints=boost_hints,
                expand_sections=expand_sections,
            )

        async def _multi_search(do_paraphrase: bool, do_cross_lingual: bool) -> list:
            queries = await expand_query(
                query, settings, paraphrase=do_paraphrase, cross_lingual=do_cross_lingual
            )
            for variant in date_variants:
                if variant not in queries:
                    queries.append(variant)
            if len(queries) <= 1:
                return await _single_query()
            # Topic-targeted canonical boost (Phase 1.20): thread the expanded variants (incl. the EN
            # translation that Lever 1 forces for VI policy queries) so apply_metadata_boosts can match
            # the query topic against the (often EN) canonical page TITLE cross-lingually — only when the
            # prefer_canonical hint is set, so non-policy turns are byte-identical.
            search_hints = boost_hints
            if boost_hints and boost_hints.get("prefer_canonical"):
                search_hints = {**boost_hints, "topic_terms": " ".join(queries)}
            if fuse_then_rerank:
                # Retrieve candidates per variant WITHOUT reranking, RRF-fuse, then rerank ONCE.
                candidate_lists = await asyncio.gather(
                    *(
                        retriever.search_candidates(query=q, filters=merged_filters, limit=max_k)
                        for q in queries
                    )
                )
                fused = reciprocal_rank_fusion(candidate_lists, key=lambda chunk: chunk.metadata.chunk_id)
                fused = dedup_by_text(fused, lambda chunk: chunk.text)[: settings.retrieval_candidate_k]
                return await retriever.rerank_fused(
                    query,
                    fused,
                    limit=max_k,
                    boost_hints=search_hints,
                    reorder=settings.enable_litm_reorder,
                    expand_sections=expand_sections,
                )
            # Legacy per-variant rerank (rerank-after-fusion off and not a point-lookup).
            ranked_lists = await asyncio.gather(
                *(
                    retriever.search(
                        query=q, filters=merged_filters, limit=max_k, reorder=False, boost_hints=search_hints
                    )
                    for q in queries
                )
            )
            fused = reciprocal_rank_fusion(ranked_lists, key=lambda chunk: chunk.metadata.chunk_id)
            fused = dedup_by_text(fused, lambda chunk: chunk.text)[:max_k]
            return reorder_for_long_context(fused) if settings.enable_litm_reorder else fused

        if settings.enable_reactive_expansion:
            # Reactive expansion (Phase 1.11 + 1.13c): a CLEAN native first pass (deterministic — keeps VI
            # calendar uncontaminated). Cross-lingual is forced on the FIRST pass only if the agent/global
            # asked for it or there are date variants; otherwise the first pass is single-language.
            first_cross = cross_lingual
            first_multi = first_cross or bool(date_variants)
            chunks = await (_multi_search(False, first_cross) if first_multi else _single_query())
            top = chunks[0].score if chunks else None
            weak = (not chunks) or (top is not None and top < settings.reactive_expansion_min_score)
            if weak:
                # SECOND loop ALWAYS goes multilingual (+ paraphrase when enabled): a VI↔EN gap is the most
                # common reason a clean native pass is weak (e.g. an EN query whose answer lives in a
                # VI-only doc, or vice-versa). One extra retrieval+rerank is far cheaper than missing the
                # answer — so we escalate deterministically rather than relying on the model to retry.
                chunks = await _multi_search(paraphrase, True)
        elif paraphrase or cross_lingual or date_variants:
            chunks = await _multi_search(paraphrase, cross_lingual)
        else:
            chunks = await _single_query()

        # Policy doc-pin (Phase 1.21): on a confident single-topic match, GUARANTEE the canonical
        # all-policies detail page leads the context (deterministic doc selection). The probe showed the
        # canonical page IS retrieved but the magnet PDF / its own PDF twin / on-topic non-policy pages
        # out-rank it after rerank, with score gaps too large for any boost to fix (Lever 2 was rejected).
        # Gated + fail-open: any miss/error leaves the vector path byte-identical. (1.21b) Fire for ALL
        # routings except calendar — the magnet questions route to financial/general specialists, not just
        # the policy one, and citations = the retrieved set, so the pin must run wherever they land.
        # Calendar is excluded so date point-lookups sharing a policy keyword (e.g. "course evaluation
        # period") are untouched; structured calendar/fee lookups already early-return above.
        if getattr(settings, "enable_policy_doc_pin", False) and subcat != "calendar":
            try:
                pin_url = policy_doc_match(get_user_message() or query)
            except Exception:
                pin_url = None
            if pin_url:
                try:
                    pinned = await retriever.search(
                        query=query, filters={"source_url": pin_url}, limit=2,
                        expand_sections=expand_sections,
                    )
                except Exception:
                    pinned = []
                if pinned:
                    # Non-evicting (Phase 1.21b): prepend the canonical but KEEP the original top chunks
                    # (cap at max_k + len(pinned)) — the first A/B showed prepend+cap-to-max_k evicted the
                    # fact-bearing chunk (often the PDF twin) and regressed facts_ok on EN cases.
                    chunks = dedup_by_text(list(pinned) + list(chunks), lambda chunk: chunk.text)[
                        : max_k + len(pinned)
                    ]

        # Canonical doc-pin for fact-intents (Phase 1.30/S15+S16): admission-GPA / financial-aid-% / program-
        # credits answers live in a doc that is out-ranked (often unretrieved) by magnet prose, so a boost
        # can't help (A/B-rejected, 1.30a). Deterministically fetch the curated canonical page by source_url
        # and non-evicting-prepend it — re-ranked WITH the real query so the fact-bearing chunk leads inside
        # the doc (program PDFs are multi-chunk → limit 3). Gated + fail-open; calendar excluded.
        if canon_applies and subcat != "calendar":
            try:
                canon_pinned = await retriever.search(
                    query=query, filters={"source_url": canon_match}, limit=3,
                    expand_sections=expand_sections,
                )
            except Exception:
                canon_pinned = []
            if canon_pinned:
                chunks = dedup_by_text(list(canon_pinned) + list(chunks), lambda chunk: chunk.text)[
                    : max_k + len(canon_pinned)
                ]

        # Indirect-injection defense: drop retrieved chunks whose text carries injection
        # patterns so poisoned source content cannot steer the model.
        if settings.enable_indirect_injection_scan:
            chunks = [chunk for chunk in chunks if not scan_for_injection(chunk.text)]

        payload = {
            "results": [
                {
                    "text": excerpt(chunk.text, max_chars=900),
                    "score": chunk.score,
                    "metadata": chunk.metadata.model_dump(),
                }
                for chunk in chunks
            ]
        }
        return json.dumps(payload, ensure_ascii=False)

    @tool
    async def search_academic_calendar(
        query: str, filters: dict[str, Any] | None = None, cross_lingual: bool = False
    ) -> str:
        """Tìm thông tin về lịch học, học kỳ, deadline add/drop, kỳ thi và ngày nghỉ.

        cross_lingual: mặc định False. Chỉ đặt True khi LẦN tìm đầu (bằng ngôn ngữ câu hỏi) KHÔNG ra kết
        quả phù hợp — khi đó cũng tìm ở ngôn ngữ kia (VI↔EN), vì tài liệu có thể chỉ có ở ngôn ngữ đó.
        (Set True only to retry across languages when the first search found nothing.)
        """

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "academic", "subcategory": "calendar"},
            cross_lingual=cross_lingual,
        )

    @tool
    async def search_policy_documents(
        query: str, filters: dict[str, Any] | None = None, cross_lingual: bool = False
    ) -> str:
        """Tìm quy định, hướng dẫn và quyền/nghĩa vụ sinh viên trong tài liệu chính sách.

        cross_lingual: mặc định False. Chỉ đặt True khi lần tìm đầu (bằng ngôn ngữ câu hỏi) không ra kết
        quả — khi đó tìm thêm ở ngôn ngữ kia (VI↔EN). (Retry across languages only when nothing was found.)
        """

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "student_affairs"},
            cross_lingual=cross_lingual,
        )

    @tool
    async def search_financial_regulations(
        query: str, filters: dict[str, Any] | None = None, cross_lingual: bool = False
    ) -> str:
        """Tìm học phí, tariff, lệ phí, phạt và thông tin tài chính dành cho sinh viên.

        cross_lingual: mặc định False. Chỉ đặt True khi lần tìm đầu (bằng ngôn ngữ câu hỏi) không ra kết
        quả — khi đó tìm thêm ở ngôn ngữ kia (VI↔EN). (Retry across languages only when nothing was found.)
        """

        return await _search(
            query=query,
            filters=filters,
            enforced_filters={"category": "student_affairs", "subcategory": "financial"},
            cross_lingual=cross_lingual,
        )

    @tool
    async def search_vinuni(
        query: str, filters: dict[str, Any] | None = None, cross_lingual: bool = False
    ) -> str:
        """Tìm kiếm tổng quát trên toàn bộ tài liệu công khai của VinUni.

        Dùng cho thư viện, phòng đăng ký (registrar), đời sống sinh viên, dịch vụ sinh
        viên và mọi câu hỏi không thuộc riêng lịch học, chính sách hay tài chính. Không
        áp đặt bộ lọc category nên bao phủ được toàn bộ corpus.

        cross_lingual: mặc định False. Chỉ đặt True khi lần tìm đầu (bằng ngôn ngữ câu hỏi) không ra kết
        quả — khi đó tìm thêm ở ngôn ngữ kia (VI↔EN). (Retry across languages only when nothing was found.)
        """

        return await _search(query=query, filters=filters, cross_lingual=cross_lingual)

    @tool
    async def search_forms(
        query: str, filters: dict[str, Any] | None = None, cross_lingual: bool = False
    ) -> str:
        """Tìm BIỂU MẪU / ĐƠN TỪ chính thức của VinUni (đơn xin nghỉ học/thôi học, hủy môn, phúc khảo
        điểm, xin cấp bảng điểm/giấy chứng nhận, hoãn thi...) và ĐƯỜNG DẪN TẢI file gốc.

        Dùng tool này khi sinh viên hỏi về một biểu mẫu/đơn từ, cần tải mẫu, hoặc muốn được điền giúp.
        Kết quả trả về gồm 'results' (các đoạn văn liên quan) và 'form_files' (danh sách URL file mẫu
        chính thức .pdf/.docx). Hãy TRÍCH DẪN đúng URL file chính thức từ 'form_files', rồi CHỦ ĐỘNG hỏi
        sinh viên có muốn "Soạn giúp em mẫu này? / Draft this form for you?".

        cross_lingual: mặc định False. Chỉ đặt True khi lần tìm đầu không ra kết quả (tìm thêm VI↔EN).
        """

        # Augment the query with form cues so form pages/files outrank generic prose, then search softly
        # (no hard category) so BOTH registrar forms and policy appendix forms are reachable.
        augmented = f"{query} biểu mẫu đơn từ mẫu đơn form application"
        raw = await _search(query=augmented, filters=filters, cross_lingual=cross_lingual)
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
        # Deterministic catalog FIRST (form PDFs embed weakly — they're mostly blank fields — so the exact
        # file often ranks below the hub page in vector search), then RAG-extracted links for the long tail.
        catalog = [
            {"url": form["url"], "title": form["title"], "department": form.get("department"),
             "source": "catalog"}
            for form in match_forms(get_user_message() or query)
        ]
        seen = {entry["url"] for entry in catalog}
        for extracted in _extract_form_files(payload.get("results", [])):
            if extracted["url"] not in seen:
                seen.add(extracted["url"])
                catalog.append({**extracted, "source": "retrieved"})
        payload["form_files"] = catalog[:8]
        return json.dumps(payload, ensure_ascii=False)

    @tool
    async def get_current_datetime() -> str:
        """Trả về ngày hôm nay, năm học và học kỳ hiện tại của VinUni (dùng cho câu hỏi về thời điểm
        'hiện tại/sắp tới' hoặc tính 'còn bao nhiêu ngày/tuần đến ...')."""

        from vinchatbot.app.core.timeutils import current_time_context

        return json.dumps(current_time_context(), ensure_ascii=False)

    @tool
    async def get_source_detail(source_id_or_url: str) -> str:
        """Lấy các đoạn liên quan nhất từ một nguồn cụ thể theo URL hoặc source id."""

        chunks = await retriever.search(
            query=source_id_or_url,
            filters={"source_url": source_id_or_url} if source_id_or_url.startswith("http") else None,
            limit=5,
        )
        payload = {
            "results": [
                {
                    "text": excerpt(chunk.text, max_chars=1200),
                    "score": chunk.score,
                    "metadata": chunk.metadata.model_dump(),
                }
                for chunk in chunks
            ]
        }
        return json.dumps(payload, ensure_ascii=False)

    return [
        search_academic_calendar,
        search_policy_documents,
        search_financial_regulations,
        search_vinuni,
        search_forms,
        get_current_datetime,
        get_source_detail,
    ]


# Matches an official VinUni form/document file URL (.pdf/.doc/.docx), incl. WordPress upload paths.
_FORM_FILE_URL_RE = re.compile(
    r"https?://[^\s\"'<>)\]]+?\.(?:pdf|docx?)(?:\?[^\s\"'<>)\]]*)?", re.IGNORECASE
)
_FORM_FILE_EXT_RE = re.compile(r"\.(pdf|docx?)(?:\?|$)", re.IGNORECASE)


def _extract_form_files(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pull official form-file URLs (.pdf/.docx) out of retrieved chunks so the agent can cite the exact
    downloadable file. Looks at each chunk's metadata (asset_url / source_url / canonical_url) and scans
    the chunk text for file links. Deduped, capped, order-preserving."""
    seen: set[str] = set()
    files: list[dict[str, Any]] = []
    for result in results:
        metadata = result.get("metadata") or {}
        title = metadata.get("document_title") or metadata.get("filename")
        candidates: list[str] = []
        for key in ("asset_url", "source_url", "canonical_url"):
            value = metadata.get(key)
            if value and _FORM_FILE_EXT_RE.search(str(value)):
                candidates.append(str(value))
        candidates.extend(match.group(0) for match in _FORM_FILE_URL_RE.finditer(result.get("text") or ""))
        for url in candidates:
            url = url.rstrip(".,);]")
            if not _FORM_FILE_EXT_RE.search(url) or url in seen:
                continue
            seen.add(url)
            files.append({"url": url, "title": title, "source_page": metadata.get("source_url")})
            if len(files) >= 8:
                return files
    return files

