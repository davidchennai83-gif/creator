"""Tamil Budget Finds script + AI-copy guard rails (no Ollama needed)."""
from datetime import date

import pytest

from app import finds, finds_agent
from app.config.settings import settings
from app.video_creator import meesho
from app.video_creator.meesho import ai_copy

PRODUCT = {
    "id": "p1",
    "title": "Steel Bottle",
    "title_ta": "ஸ்டீல் பாட்டில்",
    "category": "Home",
    "price": 299,
    "mrp": 699,
    "rating": 4.4,
    "orders_count": 18600,
    "features": ["Leak-proof lid", "1 litre capacity", "BPA free"],
    "cautions": ["Hand wash only"],
    "affiliate_url": "https://www.meesho.com/s/p/abc?aff_id=1",
    "demo": False,
}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(settings, "MEESHO_AI_COPY", False, raising=False)
    monkeypatch.setattr(finds_agent, "load_config", lambda: {})
    state = {"product": dict(PRODUCT)}
    monkeypatch.setattr(finds, "today_pick", lambda day=None: state["product"])
    return state


def test_discount_pct():
    assert ai_copy.discount_pct(PRODUCT) == 57
    assert ai_copy.discount_pct({"price": 500, "mrp": 400}) == 0
    assert ai_copy.discount_pct({"price": "x", "mrp": None}) == 0


def test_banned_claims_use_whole_words():
    assert not ai_copy._has_banned_claim("carefree secure design")
    assert ai_copy._has_banned_claim("this is the best bottle")
    assert ai_copy._has_banned_claim("free delivery")
    assert ai_copy._has_banned_claim("100% leak proof")


def test_claim_allowed_when_catalogue_says_it():
    # "BPA free" is in the product's own features, so it is grounded.
    grounded = ai_copy._product_text(PRODUCT)
    assert not ai_copy._has_banned_claim("BPA free பாட்டில்", grounded)
    assert ai_copy._has_banned_claim("free shipping", grounded) is False  # 'free' grounded
    assert ai_copy._has_banned_claim("guarantee உண்டு", grounded)


def test_sanitize_replaces_unsupported_numbers_but_keeps_discount():
    data = {
        "hook_ta": "இந்த பாட்டில் 57 சதவீதம் குறைவு",     # 57 is the real discount
        "benefits_ta": ["மூடி கசியாது 999", "1 லிட்டர் கொள்ளளவு", "BPA free"],
        "caution_ta": "கையால் கழுவுங்கள்",
        "cta_ta": "Description-ல link இருக்கு",
    }
    out = ai_copy.sanitize_copy(data, PRODUCT)
    assert "57" in out["hook_ta"]
    assert out["benefits_ta"][0] == "Leak-proof lid"  # 999 is invented -> fallback fact
    assert "1" in out["benefits_ta"][1]


def test_sanitize_survives_malformed_model_output():
    out = ai_copy.sanitize_copy({"hook_ta": None, "benefits_ta": "not a list"}, PRODUCT)
    assert out["hook_ta"] == ai_copy.DEFAULT_HOOK
    assert out["benefits_ta"] == ["Leak-proof lid", "1 litre capacity", "BPA free"]
    assert out["caution_ta"] == "Hand wash only"


def test_overlong_line_falls_back():
    out = ai_copy.sanitize_copy({"benefits_ta": ["மூடி " * 40, "", ""]}, PRODUCT)
    assert out["benefits_ta"][0] == "Leak-proof lid"


def test_extract_json_handles_fences_and_prose():
    assert ai_copy._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert ai_copy._extract_json('Here you go: {"a": 2} thanks') == {"a": 2}
    with pytest.raises(ValueError):
        ai_copy._extract_json("no json here")


def test_template_script_has_five_scenes_and_is_deterministic(patched):
    day = date(2026, 10, 28)
    first = meesho.create_script(day, lambda _m: None)
    again = meesho.create_script(day, lambda _m: None)
    assert len(first) == 5
    assert first[0]["lines"] == again[0]["lines"]          # re-render keeps the hook
    assert "57% off" in first[1]["lines"][0]
    assert first[1]["discount_pct"] == 57


def test_hook_varies_across_days(patched):
    hooks = {
        meesho.create_script(date(2026, 10, d), lambda _m: None)[0]["lines"][1]
        for d in range(1, 29)
    }
    assert len(hooks) > 1


def test_string_rating_does_not_crash(patched):
    patched["product"]["rating"] = "4.5"
    points = meesho.create_script(date(2026, 10, 28), lambda _m: None)
    assert "4.5★" in points[1]["lines"][1]


def test_disclosure_on_real_link_only(patched):
    real = meesho.create_script(date(2026, 10, 28), lambda _m: None)[4]
    assert meesho.DISCLOSURE_LINE in real["lines"]
    assert "Affiliate link" in real["text"]

    patched["product"]["demo"] = True
    demo = meesho.create_script(date(2026, 10, 28), lambda _m: None)[4]
    assert meesho.DISCLOSURE_LINE not in demo["lines"]


def test_disclosure_can_be_switched_off(patched, monkeypatch):
    monkeypatch.setattr(settings, "MEESHO_DISCLOSURE", False, raising=False)
    cta = meesho.create_script(date(2026, 10, 28), lambda _m: None)[4]
    assert meesho.DISCLOSURE_LINE not in cta["lines"]


def test_apply_copy_keeps_store_label_and_disclosure(patched):
    patched["product"]["affiliate_url"] = "https://www.amazon.in/dp/X?tag=me-21"
    points = meesho.create_script(date(2026, 10, 28), lambda _m: None)
    store_line = points[4]["lines"][1]
    copy = ai_copy.sanitize_copy({}, patched["product"])
    out = ai_copy.apply_copy(points, copy, patched["product"])
    assert out[4]["lines"][1] == store_line               # not forced to "Meesho"
    assert meesho.DISCLOSURE_LINE in out[4]["lines"]
    assert "Affiliate link" in out[4]["text"]


def test_apply_copy_ignores_unexpected_layout():
    assert ai_copy.apply_copy([{"lines": []}], {}, PRODUCT) == [{"lines": []}]
