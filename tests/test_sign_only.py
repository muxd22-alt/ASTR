from __future__ import annotations

from datetime import date

from astromind.cli import build_context, collect_signals
from astromind.engines.charts import build_chart
from astromind.engines.signals import make_signals, rank
from astromind.engines.transits import TransitHit, sign_aspect, sign_hits_for_day
from astromind.generators.md_builder import (
    ReportData,
    build_daily,
    build_monthly,
    build_weekly,
)
from astromind.models import Bundle

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


def test_sign_only_profile_parses_nested_signs_and_houses() -> None:
    bundle = Bundle.from_dict(SIGN_ONLY)
    profile = bundle.self_profile
    assert profile.id == "self"
    assert profile.birth is None
    assert profile.sign_only is True
    assert profile.signs["sun"] == 3  # Cancer
    assert profile.signs["asc"] == 0  # Aries
    assert profile.houses["sun"] == 4
    assert profile.houses["mars"] == 12
    assert profile.tz == "Asia/Riyadh"


def test_sign_only_chart_uses_whole_sign_houses() -> None:
    bundle = Bundle.from_dict(SIGN_ONLY)
    chart = build_chart(bundle.self_profile)
    assert chart.sign_only is True
    assert chart.reliable is False
    assert chart.houses is not None
    assert chart.house_system.startswith("whole-sign")
    assert chart.angles["asc"] == 0.0
    assert chart.houses.cusps[0] == 0.0
    assert chart.positions["sun"].longitude == 105.0


def test_sign_aspect_uses_sign_distance() -> None:
    assert sign_aspect(0, 0) == ("conjunction", 1.0)
    assert sign_aspect(0, 3) == ("square", 1.0)
    assert sign_aspect(0, 4) == ("trine", 0.90)
    assert sign_aspect(0, 6) == ("opposition", 1.0)
    assert sign_aspect(0, 1) is None
    assert sign_aspect(0, 11) is None


def test_sign_hits_are_flagged_and_sorted() -> None:
    bundle = Bundle.from_dict(SIGN_ONLY)
    chart = build_chart(bundle.self_profile)
    hits = sign_hits_for_day(chart, date(2026, 11, 9), bundle.self_profile.tz)
    assert hits
    assert all(hit.sign_level for hit in hits)
    assert hits == sorted(hits, key=lambda item: item.score, reverse=True)


def _data(day: date, daily: bool = False) -> ReportData:
    bundle = Bundle.from_dict(SIGN_ONLY)
    context = build_context(bundle)
    signals = collect_signals(context, day, day, daily=daily)
    return ReportData(
        bundle=context.bundle,
        charts=context.charts,
        composite=context.composite,
        signals=signals,
        start=day,
        end=day,
        synastry=context.synastry,
        child_guidance={},
    )


def test_sign_only_reports_render_with_low_confidence() -> None:
    day = date(2026, 11, 9)
    daily = build_daily(_data(day, daily=True))
    weekly = build_weekly(_data(day))
    monthly = build_monthly(_data(day))
    for text in (daily, weekly, monthly):
        assert "ثقة القراءة: منخفضة" in text
        assert "بيانات أبراج فقط" in text
    assert "بطاقة اليوم" in daily
    assert "موجز الأسبوع" in weekly
    assert "الدليل الشهري" in monthly


def _hit(
    transiting: str,
    target: str,
    aspect: str,
    score: float,
    polarity: str = "friction",
) -> TransitHit:
    return TransitHit(
        transiting=transiting,
        target=target,
        aspect=aspect,
        orb=0.0,
        limit=1.0,
        applying=False,
        exact_jd=2460000.0,
        exact_date=date(2026, 11, 9),
        active_date=date(2026, 11, 9),
        score=score,
        polarity=polarity,
        target_is_angle=False,
        sign_level=True,
    )


def test_rank_does_not_repeat_identical_copy_lines() -> None:
    hits = [
        _hit("saturn", "moon", "square", 12.0),
        _hit("moon", "moon", "quincunx", 10.0),
        _hit("moon", "moon", "trine", 9.0, polarity="support"),
    ]
    top = rank(make_signals(hits, "self", "self"), limit=3)
    lines = [signal.text.line for signal in top]
    assert len(lines) == len(set(lines))
    assert len([item for item in top if item.transiting == "moon"]) == 1
