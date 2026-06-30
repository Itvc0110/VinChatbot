from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from vinchatbot.app.api.ratelimit import _client_key
from vinchatbot.app.core.config import get_settings
from vinchatbot.app.core.observability import scrub_pii
from vinchatbot.app.dependencies.auth import get_chat_user


def _request(peer: str | None, xff: str | None = None):
    headers = {"x-forwarded-for": xff} if xff else {}
    client = SimpleNamespace(host=peer) if peer is not None else None
    return SimpleNamespace(client=client, headers=headers)


# --- A3: X-Forwarded-For trust ---------------------------------------------------------------

def test_client_key_ignores_xff_from_untrusted_peer():
    # A direct client cannot spoof its rate-limit key via XFF when no proxies are trusted.
    req = _request("1.2.3.4", xff="9.9.9.9")
    assert _client_key(req, frozenset()) == "1.2.3.4"


def test_client_key_trusts_first_xff_hop_from_known_proxy():
    req = _request("10.0.0.1", xff="9.9.9.9, 8.8.8.8")
    assert _client_key(req, frozenset({"10.0.0.1"})) == "9.9.9.9"


# --- A4: /chat auth enforcement --------------------------------------------------------------

def test_get_chat_user_requires_session_when_flag_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_auth_for_chat", True)
    with pytest.raises(HTTPException) as err:
        asyncio.run(get_chat_user(authorization=None))
    assert err.value.status_code == 401


def test_get_chat_user_allows_anonymous_when_flag_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "require_auth_for_chat", False)
    assert asyncio.run(get_chat_user(authorization=None)) is None


# --- A6: PII masking (traces/logs only) ------------------------------------------------------

def test_scrub_pii_masks_identifiers_but_keeps_course_codes_and_amounts():
    text = "advisor.cecs.demo@vinuni.edu.vn 0901234567 code D2026CECS001 in CS102, fee 815,850,000"
    out = scrub_pii(text)
    assert "[email]" in out
    assert "[phone]" in out
    assert "[student-id]" in out
    # course codes, fee amounts, dates must stay visible for debugging
    assert "CS102" in out
    assert "815,850,000" in out
    assert "@vinuni.edu.vn" not in out and "D2026CECS001" not in out


def test_scrub_pii_masks_all_student_code_shapes():
    # Covers the new DB shapes (VU25CECS005, VU24VIB025, D13CECS001) plus the legacy D2026CECS001.
    for code in ("VU25CECS005", "VU24VIB025", "D13CECS001", "D2026CECS001"):
        assert code not in scrub_pii(f"student {code} asked")
    # must NOT mask a course code or a plain term like CS102 / GEN101
    assert "CS102" in scrub_pii("enrolled in CS102")
    assert "GEN101" in scrub_pii("passed GEN101")
