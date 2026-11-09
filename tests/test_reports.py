from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from astromind.cli import build_context, collect_signals, month_bounds, week_start
from astromind.generators.md_builder import (
    ReportData,
    build_child_manual,
    build_daily,
    build_monthly,
    build_partner_manual,
    build_weekly,
)
from astromind.engines.child_development import build_child_guidance
from astromind.profiles import load_bundle

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "profiles" / "profiles.example.json"


def _data(day: date, daily: bool = False) -> ReportData:
    bundle = load_bundle(EXAMPLES)
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
        child_guidance={
            child.id: build_child_guidance(child, context.charts[child.id], day)
            for child in context.bundle.children
        },
    )


def test_daily_report() -> None:
    text = build_daily(_data(date(2026, 11, 9), daily=True))
    assert "بطاقة اليوم" in text
    assert "ثقة القراءة" in text


def test_weekly_report() -> None:
    text = build_weekly(_data(date(2026, 11, 9)))
    assert "موجز الأسبوع" in text
    assert "تقويم الأسبوع" in text


def test_monthly_and_weekly_alerts_are_future_only() -> None:
    day = date(2026, 11, 9)
    bundle = load_bundle(EXAMPLES)
    context = build_context(bundle)

    start, end = month_bounds(day)
    monthly_signals = collect_signals(context, start, end, daily=False)
    monthly = build_monthly(
        ReportData(
            bundle=context.bundle,
            charts=context.charts,
            composite=context.composite,
            signals=monthly_signals,
            start=start,
            end=end,
            as_of=day,
            synastry=context.synastry,
            child_guidance={},
        )
    )
    caution_section = monthly.split("## تواريخ تحتاج هدوءًا", 1)[1].split("##", 1)[0]
    caution_days = [
        int(match.group(1))
        for match in re.finditer(r"احذر (\d+) نوفمبر", caution_section)
    ]
    assert all(number >= day.day for number in caution_days)

    week_start_day = week_start(day)
    week_end_day = date.fromordinal(week_start_day.toordinal() + 6)
    weekly_signals = collect_signals(
        context, week_start_day, week_end_day, daily=False
    )
    weekly = build_weekly(
        ReportData(
            bundle=context.bundle,
            charts=context.charts,
            composite=context.composite,
            signals=weekly_signals,
            start=week_start_day,
            end=week_end_day,
            as_of=day,
            synastry=context.synastry,
            child_guidance={},
        )
    )
    calendar_section = weekly.split("## تقويم الأسبوع", 1)[1].split("##", 1)[0]
    assert "8 نوفمبر" not in calendar_section
    assert "9 نوفمبر" in calendar_section


def test_monthly_report_and_manuals() -> None:
    data = _data(date(2026, 11, 9))
    text = build_monthly(data)
    assert "الدليل الشهري" in text
    assert "ديناميكيات العلاقة" in text

    partner = build_partner_manual(data)
    assert "كيف تتواصلان" in partner
    assert "نقاط سهولة" in partner

    child = data.bundle.children[0]
    manual = build_child_manual(data, child, data.child_guidance[child.id])
    assert "نمط التعلم" in manual
    assert "ثلاث خطوات عملية" in manual
