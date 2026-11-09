"""Signal layer: rank transit hits, deduplicate, and keep the top few."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from astromind.engines.transits import TransitHit
from astromind.generators.interpretations import Copy, transit_copy


@dataclass
class Signal:
    key: str
    domain: str
    profile_id: str
    hit: TransitHit
    text: Copy

    @property
    def score(self) -> float:
        return self.hit.score

    @property
    def date(self) -> date:
        return self.hit.exact_date

    @property
    def polarity(self) -> str:
        return self.hit.polarity

    @property
    def transiting(self) -> str:
        return self.hit.transiting

    @property
    def target(self) -> str:
        return self.hit.target

    @property
    def aspect(self) -> str:
        return self.hit.aspect

    @property
    def applying(self) -> bool:
        return self.hit.applying


def make_signal(
    hit: TransitHit,
    domain: str,
    profile_id: str,
    perspective: str = "self",
    pronoun: str = "m",
) -> Signal:
    return Signal(
        key=f"{domain}|{profile_id}|{hit.key}",
        domain=domain,
        profile_id=profile_id,
        hit=hit,
        text=transit_copy(hit, perspective=perspective, pronoun=pronoun),
    )


def make_signals(
    hits: list[TransitHit],
    domain: str,
    profile_id: str,
    perspective: str = "self",
    pronoun: str = "m",
) -> list[Signal]:
    return [
        make_signal(hit, domain, profile_id, perspective=perspective, pronoun=pronoun)
        for hit in hits
    ]


def deduplicate(signals: list[Signal]) -> list[Signal]:
    """Keep the tightest version of each aspect per domain/profile."""
    merged: dict[str, Signal] = {}
    for signal in signals:
        existing = merged.get(signal.key)
        if existing is None or signal.hit.orb < existing.hit.orb:
            merged[signal.key] = signal
    return list(merged.values())


def rank(
    signals: list[Signal], limit: int = 3, diversify: bool = True
) -> list[Signal]:
    """Top signals, optionally one per planet-aspect pair to avoid repetition."""
    unique = deduplicate(signals)
    unique.sort(key=lambda item: (item.score, -item.hit.orb), reverse=True)
    if not diversify:
        return unique[:limit]

    selected: list[Signal] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_lines: set[str] = set()
    for signal in unique:
        pair = (signal.transiting, signal.target)
        if pair in seen_pairs or signal.text.line in seen_lines:
            continue
        seen_pairs.add(pair)
        seen_lines.add(signal.text.line)
        selected.append(signal)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        selected_keys = {signal.key for signal in selected}
        for signal in unique:
            if signal.key in selected_keys or signal.text.line in seen_lines:
                continue
            seen_lines.add(signal.text.line)
            selected.append(signal)
            selected_keys.add(signal.key)
            if len(selected) >= limit:
                break
    return selected


def top_by_domain(signals: list[Signal], limit: int = 3) -> dict[str, list[Signal]]:
    grouped: dict[str, list[Signal]] = {}
    for signal in deduplicate(signals):
        grouped.setdefault(signal.domain, []).append(signal)
    return {
        domain: sorted(items, key=lambda item: item.score, reverse=True)[:limit]
        for domain, items in grouped.items()
    }


def is_exact_near(signal: Signal, day: date, tolerance_days: int = 2) -> bool:
    return abs((signal.date - day).days) <= tolerance_days


def changed_since(
    signals: list[Signal],
    seen: dict[str, dict[str, float]],
    on_day: date,
    repeat_after_days: int = 7,
    intensify_ratio: float = 1.15,
    exact_tolerance_days: int = 1,
) -> list[Signal]:
    """Keep only new signals, exact-now signals, or ones that intensified."""
    result: list[Signal] = []
    for signal in signals:
        if abs((signal.date - on_day).days) <= exact_tolerance_days:
            result.append(signal)
            continue
        previous = seen.get(signal.key)
        if previous is None:
            result.append(signal)
            continue
        previous_score = float(previous.get("score", 0.0))
        last_seen = previous.get("last_seen")
        old = False
        if isinstance(last_seen, str):
            try:
                old = (on_day - date.fromisoformat(last_seen)).days >= repeat_after_days
            except ValueError:
                old = True
        if old or signal.score >= previous_score * intensify_ratio:
            result.append(signal)
    return result


def mark_seen(
    seen: dict[str, dict[str, float]], signals: list[Signal], on_day: date
) -> dict[str, dict[str, float]]:
    updated = dict(seen)
    for signal in signals:
        updated[signal.key] = {
            "score": signal.score,
            "last_seen": on_day.isoformat(),
            "exact": signal.date.isoformat(),
        }
    return updated
