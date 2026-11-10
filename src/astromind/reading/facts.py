"""Convert deterministic chart and transit objects into prompt-safe facts."""

from __future__ import annotations

from datetime import date

from astromind.engines.aspects import allowed_orb, detect_aspect
from astromind.engines.charts import Chart
from astromind.engines.ephemeris import house_of
from astromind.generators.md_builder import ReportData
from astromind.i18n import BODIES_AR, SIGNS_AR, element_ar, sign_element, sign_of
from astromind.models import Profile

NATAL_POINTS = (
    "sun",
    "moon",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
    "asc",
    "mc",
)


def _sign_payload(longitude: float) -> dict[str, object]:
    sign = sign_of(longitude)
    return {
        "sign": SIGNS_AR[sign],
        "element": element_ar(sign_element(sign)),
        "degree": round(longitude % 30.0, 2),
    }


def _house_for(chart: Chart, profile: Profile, body: str, longitude: float) -> int | None:
    if body in {"asc", "mc", "dsc", "ic"}:
        return None
    if body in profile.houses:
        return profile.houses[body]
    if chart.houses is None:
        return None
    return house_of(longitude, chart.houses.cusps)


def _natal_aspects(chart: Chart) -> list[dict[str, object]]:
    if chart.sign_only:
        return []
    points = {name: value for name, value in chart.points().items() if name in NATAL_POINTS}
    aspects: list[dict[str, object]] = []
    names = list(points)
    for index, a_body in enumerate(names):
        for b_body in names[index + 1 :]:
            hit = detect_aspect(
                points[a_body],
                points[b_body],
                allowed_orb(a_body, b_body),
                include_minor=False,
            )
            if hit is None:
                continue
            aspects.append(
                {
                    "a": BODIES_AR.get(a_body, a_body),
                    "b": BODIES_AR.get(b_body, b_body),
                    "aspect": hit.aspect,
                    "orb": round(hit.orb, 2),
                }
            )
    aspects.sort(key=lambda item: float(item["orb"]))
    return aspects[:10]


def chart_facts(chart: Chart, profile: Profile) -> dict[str, object]:
    placements: dict[str, dict[str, object]] = {}
    for body, position in chart.positions.items():
        payload = _sign_payload(position.longitude)
        payload["house"] = _house_for(chart, profile, body, position.longitude)
        payload["retrograde"] = position.retrograde
        placements[body] = payload

    angles: dict[str, dict[str, object]] = {}
    for body, longitude in chart.angles.items():
        if body in {"asc", "mc"}:
            angles[body] = _sign_payload(longitude)

    birth = None
    if profile.birth is not None:
        birth = {
            "date": profile.birth.date,
            "time": profile.birth.time if profile.birth.time_known else None,
            "time_known": profile.birth.time_known,
            "tz": profile.birth.tz,
            "lat": profile.birth.lat,
            "lon": profile.birth.lon,
        }

    return {
        "name": profile.name,
        "role": profile.role,
        "birth": birth,
        "chart_source": profile.chart_source,
        "house_system": chart.house_system,
        "sign_only": chart.sign_only,
        "sign_only_note": (
            "الدرجات الدقيقة غير متاحة؛ استخدم مستوى الأبراج فقط ولا تدّعِ درجات أو بيوتًا محسوبة."
            if chart.sign_only
            else ""
        ),
        "placements": placements,
        "angles": angles,
        "aspects": _natal_aspects(chart),
    }


def signal_facts(data: ReportData, limit: int = 10) -> list[dict[str, object]]:
    floor = data.as_of or data.start
    rows: list[dict[str, object]] = []
    for domain, signals in data.signals.items():
        for signal in signals:
            if signal.date < floor:
                continue
            rows.append(
                {
                    "domain": domain,
                    "date": signal.date.isoformat(),
                    "transiting": BODIES_AR.get(signal.transiting, signal.transiting),
                    "target": BODIES_AR.get(signal.target, signal.target),
                    "aspect": signal.aspect,
                    "polarity": signal.polarity,
                    "score": signal.score,
                    "sign_level": signal.hit.sign_level,
                    "line": signal.text.line,
                    "action": signal.text.action,
                    "avoid": signal.text.avoid,
                }
            )
    rows.sort(key=lambda item: (item["date"], -float(item["score"])))
    return rows[:limit]


def moon_facts(data: ReportData) -> list[dict[str, object]]:
    from astromind.engines.ephemeris import from_jd
    from astromind.i18n import SIGNS_AR
    from zoneinfo import ZoneInfo

    floor = data.as_of or data.start
    rows: list[dict[str, object]] = []
    for jd, _previous, new_sign in data.moon_changes:
        moment = from_jd(jd).astimezone(ZoneInfo(data.tz))
        if moment.date() < floor:
            continue
        rows.append(
            {
                "date": moment.date().isoformat(),
                "time": moment.strftime("%H:%M"),
                "sign": SIGNS_AR[new_sign],
            }
        )
    return rows


def build_reading_facts(context, data: ReportData, mode: str) -> dict[str, object]:
    profile = context.bundle.self_profile
    chart = context.charts[profile.id]
    facts: dict[str, object] = {
        "as_of": data.as_of.isoformat() if data.as_of else data.start.isoformat(),
        "period": {
            "start": data.start.isoformat(),
            "end": data.end.isoformat(),
        },
        "mode": mode,
        "profile": chart_facts(chart, profile),
        "transits": signal_facts(data),
        "moon_changes": moon_facts(data),
        "relationship": None,
        "children": [],
    }

    partner = context.bundle.partner
    if partner is not None:
        partner_chart = context.charts[partner.id]
        facts["relationship"] = {
            "partner": chart_facts(partner_chart, partner),
            "composite_available": context.composite is not None,
            "synastry": [
                {
                    "a": aspect.a_body,
                    "b": aspect.b_body,
                    "aspect": aspect.aspect,
                    "polarity": aspect.polarity,
                    "orb": round(aspect.orb, 2),
                }
                for aspect in context.synastry[:8]
            ],
        }

    for child in context.bundle.children:
        child_chart = context.charts[child.id]
        facts["children"].append(chart_facts(child_chart, child))

    return facts
