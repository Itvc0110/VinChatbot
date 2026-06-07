from __future__ import annotations

import importlib.util
import logging
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from vinchatbot.app.ingest.normalizer import normalize_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrResult:
    text: str
    confidence: float | None = None
    bbox_count: int = 0
    boxes: list[Any] | None = None


def ocr_dependency_status(engine: str = "paddleocr") -> tuple[bool, str | None]:
    if engine.lower() != "paddleocr":
        return False, "skipped_unsupported_engine"
    if importlib.util.find_spec("paddleocr") is None:
        return False, "skipped_dependency_missing"
    return True, None


def run_english_ocr_image(
    image: bytes | str | Path,
    *,
    lang: str = "en",
    model: str = "PP-OCRv5",
    store_boxes: bool = False,
) -> OcrResult:
    available, reason = ocr_dependency_status("paddleocr")
    if not available:
        raise RuntimeError(reason or "PaddleOCR is not available.")

    if isinstance(image, bytes):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            handle.write(image)
            temp_path = Path(handle.name)
        try:
            return _run_paddleocr_path(temp_path, lang=lang, model=model, store_boxes=store_boxes)
        finally:
            temp_path.unlink(missing_ok=True)

    return _run_paddleocr_path(Path(image), lang=lang, model=model, store_boxes=store_boxes)


@lru_cache(maxsize=4)
def _load_paddleocr(lang: str, model: str):
    from paddleocr import PaddleOCR

    logger.info("Loading PaddleOCR engine lang=%s model=%s", lang, model)
    try:
        return PaddleOCR(lang=lang)
    except TypeError:
        return PaddleOCR(use_angle_cls=True, lang=lang)


def _run_paddleocr_path(
    image_path: Path,
    *,
    lang: str,
    model: str,
    store_boxes: bool,
) -> OcrResult:
    engine = _load_paddleocr(lang, model)
    if hasattr(engine, "predict"):
        raw_result = engine.predict(str(image_path))
    else:
        raw_result = engine.ocr(str(image_path), cls=True)

    texts, scores, boxes = _extract_text_scores_boxes(raw_result)
    text = normalize_text("\n".join(texts))
    confidence = sum(scores) / len(scores) if scores else None
    return OcrResult(
        text=text,
        confidence=confidence,
        bbox_count=len(texts),
        boxes=boxes if store_boxes else None,
    )


def _extract_text_scores_boxes(raw: Any) -> tuple[list[str], list[float], list[Any]]:
    texts: list[str] = []
    scores: list[float] = []
    boxes: list[Any] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            rec_texts = value.get("rec_texts")
            rec_scores = value.get("rec_scores")
            rec_boxes = value.get("rec_boxes") or value.get("dt_polys") or value.get("boxes")
            if isinstance(rec_texts, list):
                for item in rec_texts:
                    if item:
                        texts.append(str(item))
                if isinstance(rec_scores, list):
                    for score in rec_scores:
                        try:
                            scores.append(float(score))
                        except (TypeError, ValueError):
                            continue
                if isinstance(rec_boxes, list):
                    boxes.extend(rec_boxes)
                return
            for item in value.values():
                visit(item)
            return
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
            texts.append(value[0])
            try:
                scores.append(float(value[1]))
            except (TypeError, ValueError):
                pass
            return
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and isinstance(value[1], tuple) and len(value[1]) >= 2:
                candidate_text, candidate_score = value[1][0], value[1][1]
                if isinstance(candidate_text, str):
                    texts.append(candidate_text)
                    try:
                        scores.append(float(candidate_score))
                    except (TypeError, ValueError):
                        pass
                    boxes.append(value[0])
                    return
            for item in value:
                visit(item)

    visit(raw)
    return texts, scores, boxes
