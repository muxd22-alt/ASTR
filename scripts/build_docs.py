"""Build a static docs/index.html demo page from one profile bundle.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\build_docs.py --file profiles.local\\profiles.json --date 2026-11-09
"""

from __future__ import annotations

import argparse
import html
import os
import re
from datetime import date
from pathlib import Path

from astromind.cli import (
    _data,
    build_context,
    collect_signals,
    month_bounds,
    parse_day,
    week_start,
)
from astromind.engines.charts import Chart
from astromind.engines.ephemeris import house_of
from astromind.generators.md_builder import (
    build_daily,
    build_monthly,
    build_weekly,
)
from astromind.i18n import (
    BODIES_AR,
    SIGNS_AR,
    element_ar,
    format_date,
    format_date_short,
    sign_element,
    sign_of,
)
from astromind.profiles import load_bundle
from astromind.reading import generate_reading


def inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                out.append("<div class=\"table-wrap\"><table>")
                out.append("<thead><tr>")
                for cell in rows[0]:
                    out.append(f"<th>{inline(cell)}</th>")
                out.append("</tr></thead><tbody>")
                for row in rows[1:]:
                    out.append("<tr>")
                    for cell in row:
                        out.append(f"<td>{inline(cell)}</td>")
                    out.append("</tr>")
                out.append("</tbody></table></div>")
            continue

        if stripped.startswith(">"):
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            out.append(f"<blockquote>{inline(' '.join(quote))}</blockquote>")
            continue

        if stripped.startswith("- "):
            items: list[tuple[int, str]] = []
            while index < len(lines):
                current = lines[index]
                if not current.strip():
                    index += 1
                    continue
                indent = len(current) - len(current.lstrip(" "))
                item = current.strip()
                if not item.startswith("- "):
                    break
                items.append((indent, item[2:]))
                index += 1
            out.append("<ul>")
            position = 0
            while position < len(items):
                indent, content = items[position]
                out.append(f"<li>{inline(content)}")
                position += 1
                if position < len(items) and items[position][0] >= 2:
                    out.append('<ul class="sublist">')
                    while position < len(items) and items[position][0] >= 2:
                        out.append(f"<li>{inline(items[position][1])}</li>")
                        position += 1
                    out.append("</ul>")
                out.append("</li>")
            out.append("</ul>")
            continue

        paragraph: list[str] = []
        while index < len(lines):
            current = lines[index]
            if (
                not current.strip()
                or current.strip().startswith(("#", "- ", ">", "|"))
            ):
                break
            paragraph.append(current.strip())
            index += 1
        out.append(f"<p>{inline(' '.join(paragraph))}</p>")

    return "\n".join(out)


def _sign_for(chart: Chart, body: str) -> int | None:
    if body in {"asc", "mc"}:
        longitude = chart.angles.get(body)
        return sign_of(longitude) if longitude is not None else None
    position = chart.positions.get(body)
    return sign_of(position.longitude) if position is not None else None


def _house_for(chart: Chart, body: str, explicit: dict[str, int]) -> int | None:
    if body in {"asc", "mc"}:
        return None
    if body in explicit:
        return explicit[body]
    if chart.houses is None:
        return None
    position = chart.positions.get(body)
    if position is None:
        return None
    return house_of(position.longitude, chart.houses.cusps)


def _degree_text(longitude: float) -> str:
    degree = longitude % 30.0
    whole = int(degree)
    minutes = int(round((degree - whole) * 60.0))
    if minutes >= 60:
        whole += 1
        minutes = 0
    return f"{whole}°{minutes:02d}′"


def placement_cards(chart: Chart, profile) -> str:
    order = [
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
        "node",
        "asc",
        "mc",
    ]
    cards: list[str] = []
    for body in order:
        sign = _sign_for(chart, body)
        if sign is None:
            continue
        sign_name = SIGNS_AR[sign]
        house = _house_for(chart, body, profile.houses)
        element = element_ar(sign_element(sign))
        house_label = f"البيت {house}" if house else "بدون بيت"
        degree_text = ""
        if not chart.sign_only:
            longitude = (
                chart.positions[body].longitude
                if body in chart.positions
                else chart.angles.get(body)
            )
            if longitude is not None:
                degree_text = f'<div class="placement-degree">{_degree_text(longitude)}</div>'
        cards.append(
            f"""
            <div class="placement">
              <div class="placement-body">{html.escape(BODIES_AR.get(body, body))}</div>
              <div class="placement-sign">{html.escape(sign_name)}</div>
              {degree_text}
              <div class="placement-meta"><span>{html.escape(element)}</span><span>{html.escape(house_label)}</span></div>
            </div>
            """
        )
    return "\n".join(cards)


def big_three(chart: Chart) -> str:
    items = [
        ("الشمس", _sign_for(chart, "sun"), "جوهر الهوية"),
        ("القمر", _sign_for(chart, "moon"), "الأمان العاطفي"),
        ("الطالع", _sign_for(chart, "asc"), "طريقة الظهور"),
    ]
    cards: list[str] = []
    for label, sign, caption in items:
        if sign is None:
            continue
        cards.append(
            f"""
            <div class="big-card">
              <div class="big-label">{label}</div>
              <div class="big-sign">{html.escape(SIGNS_AR[sign])}</div>
              <div class="big-caption">{caption}</div>
            </div>
            """
        )
    return "\n".join(cards)


def signature(chart: Chart) -> str:
    parts = []
    for body, label in (("sun", "الشمس"), ("moon", "القمر"), ("asc", "الطالع")):
        sign = _sign_for(chart, body)
        if sign is not None:
            parts.append(f"{label} {SIGNS_AR[sign]}")
    return " · ".join(parts)


def birth_line(profile, city: str) -> str:
    if profile.birth is None:
        return "بيانات أبراج فقط — بدون تاريخ ميلاد."
    born = date.fromisoformat(profile.birth.date)
    return (
        f"بيانات الميلاد: {format_date(born, include_weekday=False)} — "
        f"{profile.birth.time} · {city}"
    )


def signal_chips(data, limit: int = 4) -> str:
    floor = data.as_of or data.start
    chips: list[str] = []
    for domain, label in (("self", "شخصي"), ("relationship", "علاقة")):
        for signal in data.signals.get(domain, []):
            if signal.date < floor:
                continue
            chips.append(
                f'<span class="chip"><b>{html.escape(label)}</b> '
                f'{html.escape(format_date_short(signal.date))} · '
                f'{html.escape(signal.text.title)}</span>'
            )
            if len(chips) >= limit:
                break
        if len(chips) >= limit:
            break
    if not chips:
        return '<span class="chip muted">لا إشارات قوية اليوم</span>'
    return "\n".join(chips)


def build_page(
    bundle,
    context,
    day: date,
    city: str = "الرياض",
    *,
    use_ai: bool = True,
    model: str | None = None,
) -> str:
    daily_signals = collect_signals(context, day, day, daily=True)
    daily_data = _data(context, daily_signals, day, day, as_of=day)
    daily = build_daily(daily_data)
    reading = generate_reading(
        context,
        daily_data,
        mode="standard",
        use_ai=use_ai,
        model=model,
    )

    week_start_day = week_start(day)
    week_end_day = date.fromordinal(week_start_day.toordinal() + 6)
    weekly_signals = collect_signals(context, week_start_day, week_end_day, daily=False)
    weekly = build_weekly(
        _data(context, weekly_signals, week_start_day, week_end_day, as_of=day)
    )

    month_start, month_end = month_bounds(day)
    monthly_signals = collect_signals(context, month_start, month_end, daily=False)
    monthly = build_monthly(
        _data(context, monthly_signals, month_start, month_end, as_of=day)
    )

    profile = bundle.self_profile
    chart = context.charts[profile.id]
    if chart.sign_only:
        if profile.birth is None:
            confidence = (
                "ثقة منخفضة — بيانات أبراج وبيوت فقط، بدون تاريخ أو وقت ميلاد. "
                "التوقيت اليومي تقريبي، والبيوت محسوبة بنظام البيوت الكاملة انطلاقًا من الطالع."
            )
        else:
            confidence = (
                "ثقة متوسطة — مواضع أبراج وبيوت مقدمة يدويًا مع تاريخ ميلاد. "
                "التوقيت اليومي مبني على مستوى الأبراج لأن الدرجات الدقيقة غير متاحة."
            )
    elif profile.birth is not None and not profile.birth.time_known:
        confidence = (
            "ثقة متوسطة — تاريخ الميلاد متوفر لكن وقت الميلاد غير مؤكد؛ "
            "الطالع والبيوت قد يكونان تقريبيين."
        )
    elif not chart.reliable:
        confidence = "ثقة جيدة — تاريخ ووقت الميلاد متوفران، مع بعض القيود الحسابية."
    else:
        confidence = "ثقة عالية — تاريخ ووقت الميلاد متوفران والخريطة مكتملة."

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Astromind — عرض حي لـ {html.escape(profile.name)}</title>
<style>
  @font-face {{
    font-family: "Thmanyah Sans";
    src: url("font/thmanyah-sans-Light.woff2") format("woff2");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Sans";
    src: url("font/thmanyah-sans-Regular.woff2") format("woff2");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Sans";
    src: url("font/thmanyah-sans-Medium.woff2") format("woff2");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Sans";
    src: url("font/thmanyah-sans-Bold.woff2") format("woff2");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Sans";
    src: url("font/thmanyah-sans-Black.woff2") format("woff2");
    font-weight: 900;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Serif Display";
    src: url("font/thmanyah-serif-display-Light.woff2") format("woff2");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Serif Display";
    src: url("font/thmanyah-serif-display-Regular.woff2") format("woff2");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Serif Display";
    src: url("font/thmanyah-serif-display-Medium.woff2") format("woff2");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Serif Display";
    src: url("font/thmanyah-serif-display-Bold.woff2") format("woff2");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
  }}
  @font-face {{
    font-family: "Thmanyah Serif Display";
    src: url("font/thmanyah-serif-display-Black.woff2") format("woff2");
    font-weight: 900;
    font-style: normal;
    font-display: swap;
  }}
  :root {{
    --bg: #070b18;
    --bg-2: #0d1428;
    --card: rgba(255, 255, 255, 0.045);
    --card-strong: rgba(255, 255, 255, 0.075);
    --line: rgba(232, 192, 125, 0.18);
    --gold: #e8c07d;
    --gold-soft: #f4ddb0;
    --text: #eef1f8;
    --muted: #9aa6bf;
    --accent: #8fb8ff;
    --danger: #ffb9a8;
    --radius: 20px;
  }}
  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family: "Thmanyah Sans", "Segoe UI", Tahoma, sans-serif;
    background:
      radial-gradient(circle at 15% 10%, rgba(143, 184, 255, 0.16), transparent 32rem),
      radial-gradient(circle at 85% 0%, rgba(232, 192, 125, 0.14), transparent 28rem),
      radial-gradient(circle at 50% 100%, rgba(120, 90, 200, 0.12), transparent 36rem),
      linear-gradient(180deg, var(--bg), var(--bg-2) 55%, #060912);
    line-height: 1.85;
  }}
  .stars {{
    position: fixed;
    inset: 0;
    pointer-events: none;
    opacity: 0.55;
    background-image:
      radial-gradient(1px 1px at 12% 18%, #fff, transparent),
      radial-gradient(1px 1px at 28% 42%, rgba(255,255,255,0.8), transparent),
      radial-gradient(1.5px 1.5px at 64% 12%, #ffe9bd, transparent),
      radial-gradient(1px 1px at 76% 58%, rgba(255,255,255,0.7), transparent),
      radial-gradient(1px 1px at 88% 32%, #cfe0ff, transparent),
      radial-gradient(1px 1px at 44% 82%, rgba(255,255,255,0.6), transparent),
      radial-gradient(1.5px 1.5px at 8% 72%, #ffe9bd, transparent);
  }}
  .wrap {{ position: relative; width: min(1120px, calc(100% - 2rem)); margin: 0 auto; padding: 3.2rem 0 4rem; }}
  header.hero {{ text-align: center; padding: 1rem 0 2.4rem; }}
  .badge {{
    display: inline-flex; align-items: center; gap: 0.5rem;
    border: 1px solid var(--line); border-radius: 999px;
    padding: 0.35rem 0.95rem; color: var(--gold-soft);
    background: rgba(232, 192, 125, 0.06); font-size: 0.85rem; letter-spacing: 0.02em;
  }}
  .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--gold); box-shadow: 0 0 12px var(--gold); }}
  h1 {{ font-size: clamp(2.4rem, 6vw, 4.4rem); line-height: 1.1; margin: 1rem 0 0.4rem; letter-spacing: -0.02em; font-family: "Thmanyah Serif Display", serif; font-weight: 900; }}
  h1 span {{ background: linear-gradient(120deg, #fff 10%, var(--gold-soft) 55%, var(--accent)); -webkit-background-clip: text; background-clip: text; color: transparent; }}
  .subtitle {{ color: var(--muted); font-size: clamp(1rem, 2vw, 1.2rem); margin: 0; }}
  .big-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 2.2rem 0 1rem; }}
  .big-card {{
    position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: var(--radius);
    padding: 1.4rem 1rem; background: linear-gradient(160deg, var(--card-strong), var(--card));
    text-align: center; backdrop-filter: blur(8px);
  }}
  .big-card::after {{
    content: ""; position: absolute; inset: auto -20% -60% -20%; height: 80%;
    background: radial-gradient(circle, rgba(232, 192, 125, 0.12), transparent 70%);
  }}
  .big-label {{ color: var(--muted); font-size: 0.9rem; }}
  .big-sign {{ font-size: clamp(1.6rem, 4vw, 2.3rem); font-weight: 700; color: var(--gold-soft); margin: 0.2rem 0; font-family: "Thmanyah Serif Display", serif; }}
  .big-caption {{ color: var(--muted); font-size: 0.82rem; }}
  .note {{
    margin: 1.2rem 0 2.4rem; padding: 1rem 1.2rem; border-radius: 16px;
    border: 1px solid rgba(255, 185, 168, 0.28); background: rgba(255, 185, 168, 0.06);
    color: #ffd8cd; font-size: 0.95rem;
  }}
  .note strong {{ color: #fff0eb; }}
  .birth {{ display: block; margin-top: 0.35rem; color: var(--muted); font-size: 0.84rem; }}
  .reading-card {{
    position: relative;
    border: 1px solid rgba(232, 192, 125, 0.32);
    background:
      radial-gradient(circle at 92% 4%, rgba(232, 192, 125, 0.13), transparent 24rem),
      linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.025));
    box-shadow: 0 24px 70px rgba(0, 0, 0, 0.28);
  }}
  .reading-card h1 {{ font-size: clamp(1.5rem, 3vw, 2rem); }}
  .reading-card h2 {{ color: var(--gold-soft); }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 0.9rem 0 0; }}
  .chip {{
    display: inline-flex; align-items: center; gap: 0.35rem;
    border: 1px solid rgba(255,255,255,0.11); border-radius: 999px;
    padding: 0.28rem 0.7rem; color: var(--muted); font-size: 0.78rem;
    background: rgba(255,255,255,0.035);
  }}
  .chip b {{ color: var(--gold-soft); font-weight: 700; }}
  .chip.muted {{ opacity: 0.72; }}
  .fold {{
    margin-top: 1.5rem; border: 1px solid rgba(255,255,255,0.09);
    border-radius: var(--radius); background: rgba(255,255,255,0.025);
    overflow: hidden;
  }}
  .fold > summary {{
    cursor: pointer; list-style: none; padding: 1rem 1.2rem;
    font-family: "Thmanyah Serif Display", serif; font-weight: 700;
    color: var(--gold-soft); display: flex; align-items: center; justify-content: space-between;
  }}
  .fold > summary::-webkit-details-marker {{ display: none; }}
  .fold > summary::after {{ content: "+"; color: var(--muted); font-size: 1.1rem; }}
  .fold[open] > summary {{ border-bottom: 1px solid rgba(255,255,255,0.08); }}
  .fold[open] > summary::after {{ content: "−"; }}
  .fold-body {{ padding: 1rem 1.2rem 1.3rem; }}
  .fold-note {{ margin: 0 0 0.8rem; color: var(--muted); font-size: 0.86rem; }}
  section {{ margin-top: 2.6rem; }}
  .section-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }}
  h2 {{ font-size: clamp(1.4rem, 3vw, 1.9rem); margin: 0; font-family: "Thmanyah Serif Display", serif; font-weight: 700; }}
  .section-head p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
  .placements {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.8rem; }}
  .placement {{
    border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 16px; padding: 0.9rem 1rem;
    background: var(--card);
  }}
  .placement-body {{ color: var(--muted); font-size: 0.82rem; }}
  .placement-sign {{ color: var(--gold-soft); font-size: 1.35rem; font-weight: 700; margin: 0.1rem 0 0.25rem; font-family: "Thmanyah Serif Display", serif; }}
  .placement-degree {{ color: var(--muted); font-size: 0.78rem; margin-bottom: 0.15rem; font-variant-numeric: tabular-nums; }}
  .placement-meta {{ display: flex; justify-content: space-between; gap: 0.5rem; color: var(--muted); font-size: 0.76rem; }}
  .tabs {{ display: flex; flex-wrap: wrap; gap: 0.55rem; margin: 1.2rem 0 1rem; }}
  .tab {{
    appearance: none; border: 1px solid var(--line); border-radius: 999px; cursor: pointer;
    background: transparent; color: var(--muted); font-family: inherit; font-size: 0.95rem;
    padding: 0.5rem 1.15rem; transition: 0.2s ease;
  }}
  .tab:hover {{ color: var(--text); border-color: rgba(232, 192, 125, 0.4); }}
  .tab.active {{ background: linear-gradient(120deg, rgba(232, 192, 125, 0.22), rgba(143, 184, 255, 0.16)); color: #fff; border-color: rgba(232, 192, 125, 0.55); }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .report {{
    border: 1px solid rgba(255, 255, 255, 0.09); border-radius: var(--radius);
    background: linear-gradient(180deg, rgba(255,255,255,0.055), rgba(255,255,255,0.025));
    padding: clamp(1.1rem, 3vw, 2rem); backdrop-filter: blur(10px);
  }}
  .report h1 {{ font-size: 1.6rem; margin: 0 0 1rem; color: var(--gold-soft); font-family: "Thmanyah Serif Display", serif; }}
  .report h2 {{ font-size: 1.22rem; margin: 1.6rem 0 0.65rem; padding-bottom: 0.4rem; border-bottom: 1px solid rgba(255,255,255,0.08); font-family: "Thmanyah Serif Display", serif; }}
  .report h3 {{ font-size: 1.05rem; margin: 1.2rem 0 0.4rem; }}
  .report p {{ margin: 0.65rem 0; }}
  .report strong {{ color: #fff; font-weight: 700; }}
  .report ul {{ margin: 0.4rem 0 0.9rem; padding-inline-start: 1.2rem; }}
  .report li {{ margin: 0.35rem 0; }}
  .report ul.sublist {{ margin: 0.15rem 0 0.35rem; color: var(--muted); font-size: 0.92rem; }}
  .report blockquote {{
    margin: 1.2rem 0 0; padding: 0.8rem 1rem; border-radius: 12px;
    border-inline-start: 3px solid var(--gold); background: rgba(232, 192, 125, 0.06);
    color: var(--muted);
  }}
  .table-wrap {{ overflow-x: auto; margin: 0.8rem 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ padding: 0.55rem 0.6rem; border-bottom: 1px solid rgba(255,255,255,0.08); text-align: right; }}
  th {{ color: var(--gold-soft); font-weight: 700; background: rgba(232, 192, 125, 0.05); }}
  footer {{ margin-top: 3rem; padding-top: 1.4rem; border-top: 1px solid rgba(255,255,255,0.08); color: var(--muted); font-size: 0.86rem; display: flex; flex-wrap: wrap; gap: 0.6rem 1.2rem; justify-content: space-between; }}
  footer a {{ color: var(--gold-soft); text-decoration: none; }}
  @media (max-width: 620px) {{
    .big-grid {{ grid-template-columns: 1fr; }}
    .section-head {{ flex-direction: column; gap: 0.2rem; }}
  }}
</style>
</head>
<body>
<div class="stars"></div>
<div class="wrap">
  <header class="hero">
    <div class="badge"><span class="dot"></span> قراءة تأملية · تُحدَّث آليًا</div>
    <h1><span>{html.escape(profile.name)}</span></h1>
    <p class="subtitle">{html.escape(signature(chart))}</p>
  </header>

  <div class="big-grid">
    {big_three(chart)}
  </div>

  <div class="note">
    <strong>حدود القراءة:</strong> {html.escape(confidence)}
    <span class="birth">{html.escape(birth_line(profile, city))}</span>
  </div>

  <section>
    <div class="section-head">
      <h2>قراءة اليوم</h2>
      <p>{html.escape(format_date(day, include_weekday=True))}</p>
    </div>
    <div class="report reading-card">{markdown_to_html(reading)}</div>
    <div class="chips">
      {signal_chips(daily_data)}
    </div>
  </section>

  <details class="fold">
    <summary>المواضع الكاملة</summary>
    <div class="fold-body">
      <p class="fold-note">الأبراج + البيوت {html.escape("بنظام البيوت الكاملة" if chart.sign_only else f"بنظام {chart.house_system}")}. افتح القسم فقط عند الحاجة.</p>
      <div class="placements">
        {placement_cards(chart, profile)}
      </div>
    </div>
  </details>

  <details class="fold">
    <summary>التقارير الكاملة</summary>
    <div class="fold-body">
      <p class="fold-note">نفس المخرجات التي تُرفع كـ Artifacts في GitHub Actions.</p>
      <div class="tabs" role="tablist">
        <button class="tab active" data-panel="daily" role="tab">اليوم</button>
        <button class="tab" data-panel="weekly" role="tab">الأسبوع</button>
        <button class="tab" data-panel="monthly" role="tab">الشهر</button>
      </div>
      <div class="panel active" id="daily"><div class="report">{markdown_to_html(daily)}</div></div>
      <div class="panel" id="weekly"><div class="report">{markdown_to_html(weekly)}</div></div>
      <div class="panel" id="monthly"><div class="report">{markdown_to_html(monthly)}</div></div>
    </div>
  </details>

  <footer>
    <span>تم التوليد بتاريخ {day.isoformat()} · محرك Astromind</span>
    <span><a href="https://github.com/muxd22-alt/ASTR">المستودع على GitHub</a></span>
  </footer>
</div>
<script>
  const tabs = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".panel");
  tabs.forEach((tab) => {{
    tab.addEventListener("click", () => {{
      tabs.forEach((item) => item.classList.remove("active"));
      panels.forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(tab.dataset.panel).classList.add("active");
    }});
  }});
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build docs/index.html from a profile bundle")
    parser.add_argument("--file", default=None)
    parser.add_argument("--date", default=None)
    parser.add_argument("--city", default="الرياض")
    parser.add_argument("--out", default="docs/index.html")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="use the local fallback reading even when OPENROUTER_API_KEY is set",
    )
    args = parser.parse_args()

    bundle = load_bundle(Path(args.file) if args.file else None)
    context = build_context(bundle)
    day = parse_day(args.date, context.tz)
    page = build_page(
        bundle,
        context,
        day,
        city=args.city,
        use_ai=not args.no_ai,
        model=args.model,
    )

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {output} ({len(page)} chars) for {bundle.self_profile.name} on {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
