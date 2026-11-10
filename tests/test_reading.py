from __future__ import annotations

import json
import urllib.error
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from astromind.cli import build_context, collect_signals
from astromind.generators.md_builder import ReportData
from astromind.i18n import SIGNS_AR
from astromind.models import Bundle
from astromind.reading import generate_reading
from astromind.reading.facts import build_reading_facts
from astromind.reading.openrouter import OpenRouterError, chat
from astromind.reading.story import build_fallback_story

ROOT = Path(__file__).resolve().parents[1]

SIGN_ONLY = {
    "profiles": [
        {
            "name": "مثال",
            "role": "self",
            "gender": "male",
            "sun": {"sign": "Cancer", "house": 4},
            "ascendant": {"sign": "Aries"},
            "moon": {"sign": "Aries", "house": 1},
            "mercury": {"sign": "Gemini", "house": 2},
            "venus": {"sign": "Gemini", "house": 2},
            "mars": {"sign": "Pisces", "house": 12},
            "jupiter": {"sign": "Taurus", "house": 2},
            "saturn": {"sign": "Sagittarius", "house": 9},
            "uranus": {"sign": "Sagittarius", "house": 9},
            "neptune": {"sign": "Capricorn", "house": 10},
            "pluto": {"sign": "Scorpio", "house": 8},
        }
    ]
}


AUTO_PROFILE = {
    "profiles": [
        {
            "name": "مثال",
            "role": "self",
            "house_system": "whole-sign",
            "birth": {
                "date": "1988-07-07",
                "time": "00:15",
                "tz": "Asia/Riyadh",
                "lat": 24.7136,
                "lon": 46.6753,
                "time_known": True,
            },
        }
    ]
}


def _data(day: date, *, signals=None):
    bundle = Bundle.from_dict(SIGN_ONLY)
    context = build_context(bundle)
    if signals is None:
        signals = collect_signals(context, day, day, daily=True)
    data = ReportData(
        bundle=context.bundle,
        charts=context.charts,
        composite=context.composite,
        signals=signals,
        start=day,
        end=day,
        as_of=day,
        synastry=context.synastry,
        child_guidance={},
    )
    return context, data


def test_auto_chart_has_precise_degrees_and_story_spine() -> None:
    day = date(2026, 11, 10)
    bundle = Bundle.from_dict(AUTO_PROFILE)
    context = build_context(bundle)
    signals = collect_signals(context, day, day, daily=True)
    data = ReportData(
        bundle=context.bundle,
        charts=context.charts,
        composite=context.composite,
        signals=signals,
        start=day,
        end=day,
        as_of=day,
        synastry=context.synastry,
        child_guidance={},
    )
    facts = build_reading_facts(context, data, "standard")
    assert facts["profile"]["sign_only"] is False
    assert facts["profile"]["placements"]["sun"]["degree"] != 15.0
    assert facts["profile"]["placements"]["mercury"]["house"] == 3
    assert facts["profile"]["story_spine"]["core_tension"]


def test_facts_keep_missing_birth_unknown() -> None:
    context, data = _data(date(2026, 11, 10))
    facts = build_reading_facts(context, data, "standard")
    assert facts["profile"]["birth"] is None
    assert facts["profile"]["sign_only"] is True
    assert facts["profile"]["placements"]["sun"]["sign"] == "السرطان"
    assert facts["profile"]["placements"]["sun"]["house"] == 4


def test_fallback_modes_are_progressive() -> None:
    context, data = _data(date(2026, 11, 10))
    short = generate_reading(context, data, mode="short", use_ai=False)
    standard = generate_reading(context, data, mode="standard", use_ai=False)
    deep = generate_reading(context, data, mode="deep", use_ai=False)
    assert "المفتاح" in short
    assert len(short) < len(standard) < len(deep)


def test_fallback_tells_the_story_without_reciting_placements() -> None:
    context, data = _data(date(2026, 11, 10))
    text = generate_reading(context, data, mode="standard", use_ai=False)
    assert "في البيت" not in text
    assert all(sign not in text for sign in SIGNS_AR)


def test_provider_placement_inventory_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    context, data = _data(date(2026, 11, 10))
    fake = (
        "# قراءة\n"
        "شمسك في السرطان، وقمرك في الحمل، وعطارد في الجوزاء في البيت الثاني."
    )

    def transport(request, timeout):
        return json.dumps({"choices": [{"message": {"content": fake}}]}).encode("utf-8")

    text = generate_reading(
        context,
        data,
        mode="standard",
        use_ai=True,
        transport=transport,
        model="fake/model",
    )
    assert "عطارد في الجوزاء" not in text
    assert "قراءة محلية مبنية على القواعد" in text


def test_transits_respect_as_of() -> None:
    context, data = _data(date(2026, 11, 10))
    facts = build_reading_facts(context, data, "short")
    assert facts["transits"]
    assert all(row["date"] >= "2026-11-10" for row in facts["transits"])


def test_missing_transit_data_still_returns_a_reading() -> None:
    context, data = _data(date(2026, 11, 10), signals={"self": []})
    text = generate_reading(context, data, mode="short", use_ai=False)
    assert "لا توجد إشارات عبور قوية" in text


def test_historical_date_does_not_crash() -> None:
    context, data = _data(date(2020, 1, 1))
    text = generate_reading(context, data, mode="standard", use_ai=False)
    assert "قراءة" in text
    assert "2020-01-01" in text


def test_openrouter_parses_response() -> None:
    seen = {}

    def transport(request, timeout):
        seen["body"] = json.loads(request.data.decode("utf-8"))
        return json.dumps(
            {"model": "google/gemma-4-31b-it:free", "choices": [{"message": {"content": "قراءة تجريبية"}}]}
        ).encode("utf-8")

    text = chat(
        [{"role": "user", "content": "test"}],
        api_key="secret",
        transport=transport,
    )
    assert text == "قراءة تجريبية"
    assert seen["body"]["model"] == "google/gemma-4-31b-it:free"


def test_openrouter_falls_back_to_second_free_model() -> None:
    models: list[str] = []

    def transport(request, timeout):
        body = json.loads(request.data.decode("utf-8"))
        models.append(body["model"])
        if body["model"] == "google/gemma-4-31b-it:free":
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                {},
                BytesIO(b'{"error":{"message":"temporarily rate-limited"}}'),
            )
        return json.dumps(
            {"choices": [{"message": {"content": "قراءة من النموذج البديل"}}]}
        ).encode("utf-8")

    text = chat(
        [{"role": "user", "content": "test"}],
        api_key="secret",
        transport=transport,
        retries=0,
    )
    assert text == "قراءة من النموذج البديل"
    assert models == [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
    ]


def test_openrouter_requires_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(OpenRouterError):
        chat([{"role": "user", "content": "test"}])


def test_generate_reading_uses_provider_when_key_exists(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret")
    context, data = _data(date(2026, 11, 10))

    def transport(request, timeout):
        return json.dumps(
            {"choices": [{"message": {"content": "# قراءة من المزود\nنص."}}]}
        ).encode("utf-8")

    text = generate_reading(context, data, mode="short", transport=transport)
    assert "قراءة من المزود" in text


def test_skill_file_documents_the_editorial_rules() -> None:
    skill = ROOT / "skills" / "intuitive-astrology-storytelling" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "Intuitive Astrology Storytelling" in text
    assert "as_of" in text
    assert "Never invent" in text
