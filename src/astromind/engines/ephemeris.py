"""Swiss Ephemeris wrapper: planets, houses, Julian dates, Moon ingresses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import swisseph as swe

from astromind.i18n import sign_of

FLAGS = swe.FLG_SWIEPH | swe.FLG_SPEED
FALLBACK_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED

BODY_IDS: dict[str, int] = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
    "node": swe.TRUE_NODE,
}

# Chiron needs the seas_18.se1 file; enable only when it is available.
OPTIONAL_BODIES: dict[str, int] = {"chiron": swe.CHIRON}

TRANSIT_BODIES: tuple[str, ...] = (
    "moon",
    "sun",
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
    "node",
)

BODY_CLASS: dict[str, str] = {
    "sun": "luminary",
    "moon": "luminary",
    "mercury": "personal",
    "venus": "personal",
    "mars": "personal",
    "jupiter": "social",
    "saturn": "social",
    "uranus": "outer",
    "neptune": "outer",
    "pluto": "outer",
    "node": "node",
    "chiron": "outer",
    "asc": "angle",
    "mc": "angle",
    "dsc": "angle",
    "ic": "angle",
}

BODY_ORB: dict[str, float] = {
    "luminary": 8.0,
    "personal": 6.0,
    "social": 5.0,
    "outer": 4.0,
    "node": 4.0,
    "angle": 6.0,
}

BODY_WEIGHT: dict[str, float] = {
    "moon": 1.25,
    "sun": 1.2,
    "mercury": 1.1,
    "venus": 1.12,
    "mars": 1.2,
    "jupiter": 1.0,
    "saturn": 1.3,
    "uranus": 1.05,
    "neptune": 0.9,
    "pluto": 1.25,
    "node": 0.75,
    "chiron": 0.8,
    "asc": 1.25,
    "mc": 1.1,
    "dsc": 1.2,
    "ic": 1.0,
}

TARGET_WEIGHT: dict[str, float] = {
    "sun": 1.2,
    "moon": 1.3,
    "mercury": 1.15,
    "venus": 1.2,
    "mars": 1.15,
    "jupiter": 0.9,
    "saturn": 1.2,
    "uranus": 0.8,
    "neptune": 0.8,
    "pluto": 1.0,
    "node": 0.7,
    "asc": 1.25,
    "mc": 1.05,
    "dsc": 1.2,
    "ic": 0.95,
}

TRANSIT_ORB: dict[str, float] = {
    "moon": 5.0,
    "sun": 3.0,
    "mercury": 3.0,
    "venus": 3.0,
    "mars": 3.0,
    "jupiter": 4.0,
    "saturn": 4.0,
    "uranus": 2.5,
    "neptune": 2.5,
    "pluto": 2.5,
    "node": 2.0,
    "chiron": 2.0,
}


@dataclass(frozen=True)
class BodyPosition:
    name: str
    longitude: float
    latitude: float
    distance: float
    speed: float
    retrograde: bool

    @property
    def sign(self) -> int:
        return sign_of(self.longitude)


@dataclass(frozen=True)
class Houses:
    cusps: tuple[float, ...]
    asc: float
    mc: float
    system: str

    @property
    def dsc(self) -> float:
        return (self.asc + 180.0) % 360.0

    @property
    def ic(self) -> float:
        return (self.mc + 180.0) % 360.0


def to_jd(value: datetime) -> float:
    """Convert an aware datetime to Julian Day (UT)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    utc = value.astimezone(timezone.utc)
    hour = (
        utc.hour
        + utc.minute / 60.0
        + utc.second / 3600.0
        + utc.microsecond / 3_600_000_000.0
    )
    return swe.julday(utc.year, utc.month, utc.day, hour)


def from_jd(jd: float) -> datetime:
    """Convert Julian Day to an aware UTC datetime."""
    year, month, day, hour = swe.revjul(jd, swe.GREG_CAL)
    whole_hour = int(hour)
    minute_float = (hour - whole_hour) * 60.0
    minute = int(minute_float)
    second = int(round((minute_float - minute) * 60.0))
    if second == 60:
        second = 0
        minute += 1
    if minute == 60:
        minute = 0
        whole_hour += 1
    base = datetime(year, month, day, tzinfo=timezone.utc)
    return base + timedelta(hours=whole_hour, minutes=minute, seconds=second)


def calc_body(jd: float, name: str) -> BodyPosition | None:
    """Calculate one body. Returns None when the ephemeris data is unavailable."""
    body_id = BODY_IDS.get(name, OPTIONAL_BODIES.get(name))
    if body_id is None:
        return None
    try:
        values, _flags = swe.calc_ut(jd, body_id, FLAGS)
    except Exception:
        try:
            values, _flags = swe.calc_ut(jd, body_id, FALLBACK_FLAGS)
        except Exception:
            return None
    longitude, latitude, distance, speed = values[0], values[1], values[2], values[3]
    return BodyPosition(
        name=name,
        longitude=longitude % 360.0,
        latitude=latitude,
        distance=distance,
        speed=speed,
        retrograde=speed < 0,
    )


def all_positions(jd: float, include_chiron: bool = False) -> dict[str, BodyPosition]:
    names: Iterable[str] = TRANSIT_BODIES
    if include_chiron:
        names = tuple(names) + ("chiron",)
    positions: dict[str, BodyPosition] = {}
    for name in names:
        position = calc_body(jd, name)
        if position is not None:
            positions[name] = position
    return positions


def compute_houses(
    jd: float, lat: float, lon: float, system: str = "placidus"
) -> Houses | None:
    """Compute houses. Falls back between Placidus and whole-sign."""
    wanted = (system or "placidus").strip().lower()
    if wanted in {"whole", "whole-sign", "whole_sign", "wholesign", "w"}:
        order = (("whole-sign", b"W"), ("Placidus", b"P"))
    else:
        order = (("Placidus", b"P"), ("whole-sign", b"W"))
    for name, code in order:
        try:
            cusps, ascmc = swe.houses(jd, lat, lon, code)
        except Exception:
            continue
        if len(cusps) >= 12:
            return Houses(
                cusps=tuple(cusps[:12]),
                asc=ascmc[0] % 360.0,
                mc=ascmc[1] % 360.0,
                system=name,
            )
    return None


def house_of(longitude: float, cusps: tuple[float, ...]) -> int:
    """Return 1..12 for a longitude using cusp boundaries (handles wrap)."""
    lon = longitude % 360.0
    normalized = [cusp % 360.0 for cusp in cusps]
    for index in range(12):
        start = normalized[index]
        end = normalized[(index + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return index + 1
        else:
            if lon >= start or lon < end:
                return index + 1
    return 1


def moon_sign_changes(start_jd: float, end_jd: float) -> list[tuple[float, int, int]]:
    """Return (jd, from_sign, to_sign) for every Moon ingress in the interval."""
    changes: list[tuple[float, int, int]] = []
    step = 0.25
    previous_jd = start_jd
    previous = calc_body(start_jd, "moon")
    if previous is None:
        return changes
    previous_sign = previous.sign

    while previous_jd < end_jd:
        current_jd = min(previous_jd + step, end_jd)
        current = calc_body(current_jd, "moon")
        if current is None:
            break
        if current.sign != previous_sign:
            low, high = previous_jd, current_jd
            low_sign = previous_sign
            for _ in range(24):
                middle = (low + high) / 2.0
                middle_body = calc_body(middle, "moon")
                if middle_body is None:
                    break
                if middle_body.sign == low_sign:
                    low = middle
                else:
                    high = middle
            changes.append(((low + high) / 2.0, previous_sign, current.sign))
        previous_sign = current.sign
        previous_jd = current_jd
    return changes


def local_jd(day: date, hour: int, tz_name: str) -> float:
    """Julian Day for a given local hour on a given date."""
    from zoneinfo import ZoneInfo

    local = datetime(day.year, day.month, day.day, hour, 0, tzinfo=ZoneInfo(tz_name))
    return to_jd(local)


def local_noon_jd(day: date, tz_name: str) -> float:
    """Julian Day for 12:00 local time on a given date."""
    return local_jd(day, 12, tz_name)


def today_in_tz(tz_name: str) -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo(tz_name)).date()
