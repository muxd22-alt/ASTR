from __future__ import annotations

from datetime import date

import pytest

from astromind.engines.aspects import angular_separation, detect_aspect
from astromind.engines.signals import make_signals, rank
from astromind.engines.transits import TransitHit


def test_angular_separation_wraps() -> None:
    assert angular_separation(10, 350) == pytest.approx(20)
    assert angular_separation(0, 180) == pytest.approx(180)


def test_detect_conjunction_and_square() -> None:
    conjunction = detect_aspect(10.0, 12.0, 8.0)
    assert conjunction is not None
    assert conjunction.aspect == "conjunction"
    assert conjunction.orb == pytest.approx(2.0)

    square = detect_aspect(10.0, 99.0, 8.0)
    assert square is not None
    assert square.aspect == "square"
    assert square.orb == pytest.approx(1.0)


def test_detect_respects_orb_limit() -> None:
    assert detect_aspect(0.0, 10.0, 2.0) is None


def _hit(transiting: str, target: str, aspect: str, score: float) -> TransitHit:
    return TransitHit(
        transiting=transiting,
        target=target,
        aspect=aspect,
        orb=1.0,
        limit=6.0,
        applying=True,
        exact_jd=2460000.0,
        exact_date=date(2026, 11, 9),
        active_date=date(2026, 11, 9),
        score=score,
        polarity="friction",
        target_is_angle=False,
    )


def test_rank_diversifies_planet_target_pairs() -> None:
    hits = [
        _hit("moon", "sun", "square", 12.0),
        _hit("moon", "asc", "square", 11.0),
        _hit("saturn", "moon", "opposition", 10.0),
        _hit("mars", "venus", "square", 9.0),
    ]
    signals = make_signals(hits, "self", "self")
    top = rank(signals, limit=3)
    assert len(top) == 3
    assert len({(item.transiting, item.target) for item in top}) == 3
    assert top[0].transiting == "moon"
