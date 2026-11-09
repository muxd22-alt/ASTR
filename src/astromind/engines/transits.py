"""Transit calculation: transiting planets against a fixed chart."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from astromind.engines import ephemeris
from astromind.engines.aspects import angular_separation, body_orb, detect_aspect, is_hard, is_soft
from astromind.engines.charts import Chart
from astromind.engines.ephemeris import (
    BODY_WEIGHT,
    TARGET_WEIGHT,
    TRANSIT_BODIES,
    TRANSIT_ORB,
    BodyPosition,
    from_jd,
    local_noon_jd,
)
from astromind.i18n import sign_of

BENEFIC = {"venus", "jupiter"}
MALEFIC = {"saturn", "mars", "pluto", "uranus"}


@dataclass
class TransitHit:
    transiting: str
    target: str
    aspect: str
    orb: float
    limit: float
    applying: bool
    exact_jd: float
    exact_date: date
    active_date: date
    score: float
    polarity: str
    target_is_angle: bool = False
    sign_level: bool = False

    @property
    def key(self) -> str:
        return f"{self.transiting}|{self.target}|{self.aspect}"


def _polarity(transiting: str, aspect: str) -> str:
    if is_soft(aspect):
        return "opportunity" if transiting in BENEFIC else "support"
    if is_hard(aspect):
        return "friction"
    if transiting in MALEFIC:
        return "friction"
    if transiting in BENEFIC:
        return "opportunity"
    return "info"


def _score(transiting: str, target: str, orb: float, limit: float, applying: bool, aspect_weight: float) -> float:
    tightness = max(0.05, 1.0 - (orb / limit)) if limit > 0 else 0.05
    base = (
        BODY_WEIGHT.get(transiting, 1.0)
        * TARGET_WEIGHT.get(target, 1.0)
        * aspect_weight
        * tightness
    )
    if applying:
        base *= 1.15
    return round(base * 10.0, 3)


def hits_at(
    jd: float,
    chart: Chart,
    on_day: date,
    tz_name: str,
    transiting_positions: dict[str, BodyPosition] | None = None,
    next_positions: dict[str, BodyPosition] | None = None,
    targets: tuple[str, ...] | None = None,
) -> list[TransitHit]:
    """All transit aspects active at this moment for a fixed chart."""
    now = transiting_positions or ephemeris.all_positions(jd)
    later = next_positions or ephemeris.all_positions(jd + 0.1)

    chart_points = chart.points()
    if targets is not None:
        chart_points = {name: value for name, value in chart_points.items() if name in targets}

    hits: list[TransitHit] = []
    for transiting in TRANSIT_BODIES:
        current = now.get(transiting)
        later_body = later.get(transiting)
        if current is None or later_body is None:
            continue
        transit_orb = TRANSIT_ORB.get(transiting, 3.0)
        for target, target_lon in chart_points.items():
            limit = min(transit_orb, body_orb(target))
            if limit <= 0:
                continue
            hit = detect_aspect(current.longitude, target_lon, limit)
            if hit is None:
                continue

            separation_now = angular_separation(current.longitude, target_lon)
            separation_later = angular_separation(later_body.longitude, target_lon)
            rate = (separation_later - separation_now) / 0.1
            applying = rate < 0
            if abs(rate) > 1e-6:
                exact_jd = jd + (hit.angle - separation_now) / rate
            else:
                exact_jd = jd
            # Do not extrapolate absurdly far from the active moment.
            max_shift = max(1.0, hit.limit / max(abs(rate), 1e-4))
            exact_jd = max(jd - max_shift, min(jd + max_shift, exact_jd))

            exact_local = from_jd(exact_jd).astimezone(ZoneInfo(tz_name))
            polarity = _polarity(transiting, hit.aspect)
            hits.append(
                TransitHit(
                    transiting=transiting,
                    target=target,
                    aspect=hit.aspect,
                    orb=round(hit.orb, 2),
                    limit=round(hit.limit, 2),
                    applying=applying,
                    exact_jd=exact_jd,
                    exact_date=exact_local.date(),
                    active_date=on_day,
                    score=_score(
                        transiting,
                        target,
                        hit.orb,
                        hit.limit,
                        applying,
                        hit.weight,
                    ),
                    polarity=polarity,
                    target_is_angle=target in {"asc", "mc", "dsc", "ic"},
                )
            )
    return hits


def scan_period(
    chart: Chart,
    start: date,
    end: date,
    tz_name: str,
    targets: tuple[str, ...] | None = None,
) -> list[TransitHit]:
    """Scan each local day in [start, end] and keep the tightest hit per aspect."""
    if end < start:
        start, end = end, start
    merged: dict[str, TransitHit] = {}

    day = start
    while day <= end:
        # Two samples per day keep the fast Moon inside its 5° orb window.
        for hour in (0, 12):
            jd = ephemeris.local_jd(day, hour, tz_name)
            positions = ephemeris.all_positions(jd)
            later = ephemeris.all_positions(jd + 0.1)
            for hit in hits_at(
                jd,
                chart,
                day,
                tz_name,
                transiting_positions=positions,
                next_positions=later,
                targets=targets,
            ):
                existing = merged.get(hit.key)
                if existing is None or hit.orb < existing.orb:
                    merged[hit.key] = hit
        day += timedelta(days=1)

    # `active_days` is intentionally not used to overwrite active_date:
    # the tightest day is more useful for a weekly calendar.
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


def hits_for_day(
    chart: Chart,
    day: date,
    tz_name: str,
    targets: tuple[str, ...] | None = None,
) -> list[TransitHit]:
    merged: dict[str, TransitHit] = {}
    for hour in (0, 8, 16, 23):
        jd = ephemeris.local_jd(day, hour, tz_name)
        for hit in hits_at(
            jd,
            chart,
            day,
            tz_name,
            transiting_positions=ephemeris.all_positions(jd),
            next_positions=ephemeris.all_positions(jd + 0.1),
            targets=targets,
        ):
            existing = merged.get(hit.key)
            if existing is None or hit.orb < existing.orb:
                merged[hit.key] = hit
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


SIGN_ASPECT_MAP: dict[int, tuple[str, float] | None] = {
    0: ("conjunction", 1.00),
    1: None,
    2: ("sextile", 0.75),
    3: ("square", 1.00),
    4: ("trine", 0.90),
    5: ("quincunx", 0.60),
    6: ("opposition", 1.00),
    7: ("quincunx", 0.60),
    8: ("trine", 0.90),
    9: ("square", 1.00),
    10: ("sextile", 0.75),
    11: None,
}


def sign_aspect(sign_a: int, sign_b: int) -> tuple[str, float] | None:
    """Aspect by zodiac sign only (0 = conjunction, 6 = opposition, ...)."""
    return SIGN_ASPECT_MAP.get((sign_a - sign_b) % 12)


def _sign_hits(
    chart: Chart,
    on_day: date,
    positions: dict[str, BodyPosition],
    exact_jd: float,
    tz_name: str,
) -> list[TransitHit]:
    exact_local = from_jd(exact_jd).astimezone(ZoneInfo(tz_name))
    hits: list[TransitHit] = []
    for transiting in TRANSIT_BODIES:
        current = positions.get(transiting)
        if current is None:
            continue
        transit_sign = sign_of(current.longitude)
        for target, target_lon in chart.points().items():
            match = sign_aspect(transit_sign, sign_of(target_lon))
            if match is None:
                continue
            aspect, weight = match
            polarity = _polarity(transiting, aspect)
            score = round(
                BODY_WEIGHT.get(transiting, 1.0)
                * TARGET_WEIGHT.get(target, 1.0)
                * weight
                * 10.0,
                3,
            )
            hits.append(
                TransitHit(
                    transiting=transiting,
                    target=target,
                    aspect=aspect,
                    orb=0.0,
                    limit=1.0,
                    applying=False,
                    exact_jd=exact_jd,
                    exact_date=exact_local.date(),
                    active_date=on_day,
                    score=score,
                    polarity=polarity,
                    target_is_angle=target in {"asc", "mc", "dsc", "ic"},
                    sign_level=True,
                )
            )
    return hits


def sign_hits_for_day(
    chart: Chart,
    day: date,
    tz_name: str,
) -> list[TransitHit]:
    """Sign-level transits for one local day (used for sign-only profiles)."""
    day_start = ephemeris.local_jd(day, 0, tz_name)
    next_start = ephemeris.local_jd(day + timedelta(days=1), 0, tz_name)
    changes = ephemeris.moon_sign_changes(day_start, next_start)
    noon = local_noon_jd(day, tz_name)

    merged: dict[str, TransitHit] = {}
    for hour in (0, 8, 16, 23):
        jd = ephemeris.local_jd(day, hour, tz_name)
        positions = ephemeris.all_positions(jd)
        moon = positions.get("moon")
        exact_jd = noon
        if moon is not None:
            exact_jd = day_start
            for change_jd, _previous_sign, new_sign in changes:
                if new_sign == moon.sign:
                    exact_jd = change_jd
                    break
        for hit in _sign_hits(chart, day, positions, exact_jd, tz_name):
            existing = merged.get(hit.key)
            if existing is None or hit.exact_jd < existing.exact_jd:
                merged[hit.key] = hit
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


def sign_scan_period(
    chart: Chart,
    start: date,
    end: date,
    tz_name: str,
) -> list[TransitHit]:
    """Merge sign-level hits across a period, keeping the first occurrence."""
    if end < start:
        start, end = end, start
    merged: dict[str, TransitHit] = {}
    day = start
    while day <= end:
        for hit in sign_hits_for_day(chart, day, tz_name):
            existing = merged.get(hit.key)
            if existing is None or hit.exact_jd < existing.exact_jd:
                merged[hit.key] = hit
        day += timedelta(days=1)
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)


def exact_datetime(hit: TransitHit, tz_name: str) -> str:
    local = from_jd(hit.exact_jd).astimezone(ZoneInfo(tz_name))
    return local.strftime("%Y-%m-%d %H:%M")
