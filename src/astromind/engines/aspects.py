"""Aspect geometry and orb rules."""

from __future__ import annotations

from dataclasses import dataclass

from astromind.engines.ephemeris import BODY_CLASS, BODY_ORB

HARD_ASPECTS = {"opposition", "square", "quincunx", "semisquare", "sesquiquadrate"}
SOFT_ASPECTS = {"trine", "sextile"}
MAJOR_ASPECTS = {"conjunction", "opposition", "trine", "square", "sextile"}


@dataclass(frozen=True)
class AspectDef:
    name: str
    angle: float
    limit: float
    weight: float


ASPECT_DEFS: tuple[AspectDef, ...] = (
    AspectDef("conjunction", 0.0, 8.0, 1.00),
    AspectDef("opposition", 180.0, 8.0, 1.00),
    AspectDef("trine", 120.0, 7.0, 0.90),
    AspectDef("square", 90.0, 7.0, 1.00),
    AspectDef("sextile", 60.0, 5.0, 0.75),
    AspectDef("quincunx", 150.0, 3.0, 0.60),
    AspectDef("semisextile", 30.0, 2.0, 0.45),
    AspectDef("semisquare", 45.0, 2.0, 0.50),
    AspectDef("sesquiquadrate", 135.0, 2.0, 0.50),
)

ASPECT_BY_NAME = {item.name: item for item in ASPECT_DEFS}


@dataclass(frozen=True)
class AspectHit:
    aspect: str
    angle: float
    orb: float
    limit: float
    weight: float

    @property
    def tightness(self) -> float:
        if self.limit <= 0:
            return 0.0
        return max(0.05, 1.0 - (self.orb / self.limit))


def angular_separation(lon_a: float, lon_b: float) -> float:
    """Shortest angular distance, 0..180."""
    diff = abs((lon_a - lon_b) % 360.0)
    return diff if diff <= 180.0 else 360.0 - diff


def body_orb(name: str) -> float:
    return BODY_ORB.get(BODY_CLASS.get(name, "personal"), 5.0)


def allowed_orb(body_a: str, body_b: str) -> float:
    return (body_orb(body_a) + body_orb(body_b)) / 2.0


def detect_aspect(
    lon_a: float,
    lon_b: float,
    orb_limit: float,
    include_minor: bool = True,
) -> AspectHit | None:
    """Return the tightest aspect within the allowed orb."""
    separation = angular_separation(lon_a, lon_b)
    best: AspectHit | None = None
    for definition in ASPECT_DEFS:
        if not include_minor and definition.name not in MAJOR_ASPECTS:
            continue
        limit = min(orb_limit, definition.limit)
        if limit <= 0:
            continue
        orb = abs(separation - definition.angle)
        if orb <= limit and (best is None or orb < best.orb):
            best = AspectHit(
                aspect=definition.name,
                angle=definition.angle,
                orb=orb,
                limit=limit,
                weight=definition.weight,
            )
    return best


def is_hard(aspect: str) -> bool:
    return aspect in HARD_ASPECTS


def is_soft(aspect: str) -> bool:
    return aspect in SOFT_ASPECTS


def signed_delta(lon_a: float, lon_b: float) -> float:
    """Signed separation in (-180, 180]."""
    return ((lon_a - lon_b + 180.0) % 360.0) - 180.0
