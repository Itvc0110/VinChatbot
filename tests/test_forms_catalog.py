from __future__ import annotations

from vinchatbot.app.core.config import get_settings
from vinchatbot.app.rag.forms_catalog import load_forms_catalog, match_forms


def test_catalog_loads_core_forms():
    forms = load_forms_catalog()
    ids = {f.get("id") for f in forms}
    assert {"FRM07", "FRM10", "GRADE_APPEAL"} <= ids
    assert all(f.get("url", "").startswith("https://") for f in forms)


def test_match_vietnamese_leave_of_absence_returns_frm07_first():
    matches = match_forms("Tôi muốn xin nghỉ học một học kỳ thì dùng mẫu nào?")
    assert matches and matches[0]["id"] == "FRM07"
    assert matches[0]["url"].endswith("FRM07_VinUni_Defer-Withdraw-Form.pdf")


def test_match_no_diacritics_still_hits():
    # A student typing without diacritics ("don xin nghi hoc") must still resolve.
    matches = match_forms("don xin nghi hoc")
    assert any(m["id"] == "FRM07" for m in matches)


def test_match_english_grade_appeal():
    matches = match_forms("How do I appeal a grade?")
    assert any(m["id"] == "GRADE_APPEAL" for m in matches)


def test_match_transfer_credit():
    matches = match_forms("transfer credit form")
    assert matches[0]["id"] == "FRM10"


def test_no_match_returns_empty():
    assert match_forms("what is the weather in Hanoi") == []
    assert match_forms("") == []


def test_fail_open_when_catalog_missing():
    settings = get_settings().model_copy(
        update={"forms_catalog_path": "data/__does_not_exist__.json"}
    )
    assert load_forms_catalog(settings) == ()
    assert match_forms("đơn xin nghỉ học", settings=settings) == []


def test_limit_is_respected():
    # A broad query that could hit several forms is capped.
    assert len(match_forms("đơn xin chuyển ngành nghỉ học chuyển tín chỉ phúc khảo", limit=2)) <= 2
