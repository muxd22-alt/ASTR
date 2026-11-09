"""Generate an importable .ics calendar of contact and caution windows."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from astromind.engines.ephemeris import from_jd
from astromind.engines.signals import Signal
from astromind.generators.md_builder import POSITIVE, ReportData


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str, limit: int = 73) -> str:
    encoded = line.encode("utf-8")
    if len(encoded) <= limit:
        return line
    chunks: list[bytes] = []
    current = b""
    for char in line:
        piece = char.encode("utf-8")
        if len(current) + len(piece) > limit:
            chunks.append(current)
            current = b""
        current += piece
    if current:
        chunks.append(current)
    return "\r\n ".join(chunk.decode("utf-8") for chunk in chunks)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _uid(prefix: str, signal: Signal) -> str:
    raw = f"{prefix}|{signal.key}|{signal.hit.exact_jd:.4f}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{digest}@astromind.local"


def _events_for(
    signals: list[Signal],
    data: ReportData,
    month_start: date,
    month_end: date,
    kind: str,
    limit: int,
) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    floor = data.as_of or month_start
    for signal in signals:
        if signal.date < month_start or signal.date > month_end:
            continue
        if signal.date < floor:
            continue
        if signal.key in seen:
            continue
        seen.add(signal.key)
        start = from_jd(signal.hit.exact_jd).astimezone(ZoneInfo(data.tz))
        if kind == "window":
            duration = timedelta(minutes=75)
            summary = f"نافذة تواصل: {signal.text.title}"
            description = f"{signal.text.line}\nافعل: {signal.text.action}"
        else:
            duration = timedelta(minutes=90)
            summary = f"هدّئ النقاش: {signal.text.title}"
            description = f"{signal.text.line}\nتجنّب: {signal.text.avoid}"
        end = start + duration
        output.append(
            "\r\n".join(
                [
                    "BEGIN:VEVENT",
                    _fold(f"UID:{_uid(kind, signal)}"),
                    f"DTSTAMP:{_stamp(datetime.now(timezone.utc))}",
                    f"DTSTART:{_stamp(start)}",
                    f"DTEND:{_stamp(end)}",
                    _fold(f"SUMMARY:{_escape(summary)}"),
                    _fold(f"DESCRIPTION:{_escape(description)}"),
                    "TRANSP:TRANSPARENT",
                    "END:VEVENT",
                ]
            )
        )
        if len(output) >= limit:
            break
    return output


def build_calendar(data: ReportData, month_start: date, month_end: date) -> str:
    events: list[str] = []

    relationship = data.signals.get("relationship", [])
    events.extend(
        _events_for(
            [s for s in relationship if s.polarity in POSITIVE],
            data,
            month_start,
            month_end,
            "window",
            8,
        )
    )
    events.extend(
        _events_for(
            [s for s in relationship if s.polarity == "friction"],
            data,
            month_start,
            month_end,
            "caution",
            8,
        )
    )

    self_signals = data.signals.get("self", [])
    events.extend(
        _events_for(
            [s for s in self_signals if s.polarity in POSITIVE],
            data,
            month_start,
            month_end,
            "window",
            6,
        )
    )
    events.extend(
        _events_for(
            [s for s in self_signals if s.polarity == "friction"],
            data,
            month_start,
            month_end,
            "caution",
            4,
        )
    )

    for child in data.bundle.children:
        child_signals = data.signals.get(f"child:{child.id}", [])
        events.extend(
            _events_for(
                [s for s in child_signals if s.polarity in POSITIVE],
                data,
                month_start,
                month_end,
                "window",
                4,
            )
        )

    header = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Astromind//Multi-Profile Engine//AR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:أستروماند — نوافذ وتنبيهات",
        "X-WR-TIMEZONE:UTC",
    ]
    footer = ["END:VCALENDAR"]
    return "\r\n".join(header + events + footer) + "\r\n"
