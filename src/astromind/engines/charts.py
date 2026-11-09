"""Natal and composite chart construction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from astromind.engines import ephemeris
from astromind.engines.ephemeris import BodyPosition, Houses
from astromind.models import BirthData, Profile


@dataclass(frozen=True)
class Chart:
    profile_id: str
    name: str
    role: str
    birth: BirthData | None
    jd: float
    positions: dict[str, BodyPosition]
    houses: Houses | None
    angles: dict[str, float]
    house_system: str
    reliable: bool
    fingerprint: str
    composite: bool = False
    components: tuple[str, ...] = field(default_factory=tuple)
    sign_only: bool = False


    def points(self) -> dict[str, float]:
        points = {name: body.longitude for name, body in self.positions.items()}
        points.update(self.angles)
        return points

    def point(self, name: str) -> float | None:
        if name in self.positions:
            return self.positions[name].longitude
        return self.angles.get(name)

    def body(self, name: str) -> BodyPosition | None:
        return self.positions.get(name)


def build_sign_chart(profile: Profile) -> Chart:
    """Build a coarse chart from sign placements (and optional whole-sign houses)."""
    positions: dict[str, BodyPosition] = {}
    for name, sign in profile.signs.items():
        longitude = (sign % 12) * 30.0 + 15.0
        positions[name] = BodyPosition(
            name=name,
            longitude=longitude,
            latitude=0.0,
            distance=0.0,
            speed=0.0,
            retrograde=False,
        )

    angles: dict[str, float] = {}
    houses = None
    if "asc" in profile.signs:
        asc_sign = profile.signs["asc"] % 12
        asc = asc_sign * 30.0
        cusps = tuple(((asc_sign + offset) % 12) * 30.0 for offset in range(12))
        mc = cusps[9]
        angles = {
            "asc": asc,
            "mc": mc,
            "dsc": (asc + 180.0) % 360.0,
            "ic": cusps[3],
        }
        houses = Houses(
            cusps=cusps,
            asc=asc,
            mc=mc,
            system="whole-sign (sign-only)",
        )

    fingerprint = hashlib.sha256(
        repr(sorted(profile.signs.items())).encode("utf-8")
    ).hexdigest()[:16]

    if profile.birth is not None:
        jd = ephemeris.to_jd(profile.birth.utc_dt())
    else:
        jd = ephemeris.to_jd(datetime.now(timezone.utc))

    return Chart(
        profile_id=profile.id,
        name=profile.name,
        role=profile.role,
        birth=profile.birth,
        jd=jd,
        positions=positions,
        houses=houses,
        angles=angles,
        house_system=houses.system if houses else "sign-only",
        reliable=False,
        fingerprint=fingerprint,
        sign_only=True,
    )


def build_chart(profile: Profile) -> Chart:
    if profile.chart_source == "signs" and profile.signs:
        return build_sign_chart(profile)
    if profile.birth is None:
        return build_sign_chart(profile)
    jd = ephemeris.to_jd(profile.birth.utc_dt())
    positions = ephemeris.all_positions(jd)
    houses = None
    angles: dict[str, float] = {}
    if profile.birth.time_known:
        houses = ephemeris.compute_houses(
            jd, profile.birth.lat, profile.birth.lon, system=profile.house_system
        )
        if houses is not None:
            angles = {
                "asc": houses.asc,
                "mc": houses.mc,
                "dsc": houses.dsc,
                "ic": houses.ic,
            }
    return Chart(
        profile_id=profile.id,
        name=profile.name,
        role=profile.role,
        birth=profile.birth,
        jd=jd,
        positions=positions,
        houses=houses,
        angles=angles,
        house_system=houses.system if houses else "none",
        reliable=profile.birth.time_known and houses is not None,
        fingerprint=profile.birth.fingerprint(),
    )


def _midpoint(lon_a: float, lon_b: float) -> float:
    delta = ((lon_b - lon_a + 180.0) % 360.0) - 180.0
    return (lon_a + delta / 2.0) % 360.0


def build_composite(chart_a: Chart, chart_b: Chart) -> Chart:
    positions: dict[str, BodyPosition] = {}
    for name in sorted(set(chart_a.positions) & set(chart_b.positions)):
        a = chart_a.positions[name]
        b = chart_b.positions[name]
        longitude = _midpoint(a.longitude, b.longitude)
        positions[name] = BodyPosition(
            name=name,
            longitude=longitude,
            latitude=0.0,
            distance=0.0,
            speed=0.0,
            retrograde=False,
        )

    angles: dict[str, float] = {}
    for name in ("asc", "mc", "dsc", "ic"):
        if name in chart_a.angles and name in chart_b.angles:
            angles[name] = _midpoint(chart_a.angles[name], chart_b.angles[name])

    houses = None
    if chart_a.houses and chart_b.houses:
        cusps = tuple(
            _midpoint(a, b)
            for a, b in zip(chart_a.houses.cusps, chart_b.houses.cusps)
        )
        houses = Houses(
            cusps=cusps,
            asc=angles.get("asc", chart_a.houses.asc),
            mc=angles.get("mc", chart_a.houses.mc),
            system=f"composite-{chart_a.house_system}",
        )

    return Chart(
        profile_id="composite",
        name="العلاقة",
        role="relationship",
        birth=None,
        jd=(chart_a.jd + chart_b.jd) / 2.0,
        positions=positions,
        houses=houses,
        angles=angles,
        house_system=houses.system if houses else "none",
        reliable=chart_a.reliable and chart_b.reliable,
        fingerprint=f"{chart_a.fingerprint}-{chart_b.fingerprint}",
        composite=True,
        components=(chart_a.profile_id, chart_b.profile_id),
    )


def chart_facts(chart: Chart) -> dict[str, Any]:
    return {
        "profile_id": chart.profile_id,
        "name": chart.name,
        "role": chart.role,
        "jd": round(chart.jd, 6),
        "reliable": chart.reliable,
        "sign_only": chart.sign_only,
        "house_system": chart.house_system,
        "positions": {
            name: {
                "longitude": round(body.longitude, 6),
                "speed": round(body.speed, 6),
                "retrograde": body.retrograde,
                "sign": body.sign,
            }
            for name, body in chart.positions.items()
        },
        "angles": {name: round(value, 6) for name, value in chart.angles.items()},
        "cusps": [round(value, 6) for value in chart.houses.cusps]
        if chart.houses
        else [],
    }
