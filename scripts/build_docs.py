"""Build a static docs/index.html demo page from one profile bundle.

Designed with Apple Visual Identity (Bento Grid & Frosted Glass):
- Floating Glass Pill Navbar with backdrop-filter: saturate(180%) blur(28px) and Specular Hairline Borders
- Apple Bento Cards with 24px-26px border-radius and Ambient Mesh Gradients (#0A84FF, #FF9F0A, #30D158, #FF453A)
- Instant Theme Switcher between Pro Dark Titanium and Apple Daylight Silver with automatic Canvas chart redrawing
- Grounded in the 10 foundational astrology books for light, practical Daily, Weekly, and Monthly readings

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\build_docs.py --file profiles.local\\profiles.json --date 2026-11-09
"""

from __future__ import annotations

import argparse
import html
import json
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
from astromind.engines.classical import (
    SIGN_RULERS,
    BookPillar,
    DomainInsight,
    LunationPhase,
    ProfectionYear,
    SectProfile,
    build_book_pillars,
    build_life_domains,
    compute_lots,
    compute_lunation,
    compute_profection,
    compute_sect,
    split_eagle_and_lark,
)
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

        if stripped in {"---", "***", "___"}:
            out.append('<hr class="reading-divider">')
            index += 1
            continue

        bold_title = re.fullmatch(r"\*\*(.+?)\*\*", stripped)
        if bold_title and not out:
            out.append(
                f'<h1 class="reading-title">{inline(bold_title.group(1))}</h1>'
            )
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
                cells = [
                    cell.strip()
                    for cell in lines[index].strip().strip("|").split("|")
                ]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                out.append('<div class="table-wrap"><table>')
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
    element_colors = {
        "fire": "#FF453A",
        "earth": "#30D158",
        "air": "#0A84FF",
        "water": "#0A84FF",
    }
    cards: list[str] = []
    for body in order:
        sign = _sign_for(chart, body)
        if sign is None:
            continue
        sign_name = SIGNS_AR[sign]
        house = _house_for(chart, body, profile.houses)
        el_key = sign_element(sign)
        element = element_ar(el_key)
        color = element_colors.get(el_key, "#0A84FF")
        house_label = f"البيت {house}" if house else "بدون بيت"
        ruler_ar = BODIES_AR.get(SIGN_RULERS[sign], "")
        degree_text = ""
        if not chart.sign_only:
            longitude = (
                chart.positions[body].longitude
                if body in chart.positions
                else chart.angles.get(body)
            )
            if longitude is not None:
                degree_text = (
                    f'<div class="placement-degree">{_degree_text(longitude)}</div>'
                )
        cards.append(
            f"""
            <div class="placement bento-mini" style="--pill-accent: {color}">
              <div class="placement-top">
                <span class="placement-body">{html.escape(BODIES_AR.get(body, body))}</span>
                <span class="placement-dot"></span>
              </div>
              <div class="placement-sign">{html.escape(sign_name)}</div>
              {degree_text}
              <div class="placement-meta">
                <span>{html.escape(element)}</span>
                <span>{html.escape(house_label)}</span>
              </div>
              <div class="placement-ruler">حاكمه: {html.escape(ruler_ar)}</div>
            </div>
            """
        )
    return "\n".join(cards)


def big_three(chart: Chart) -> str:
    items = [
        ("الشمس", _sign_for(chart, "sun"), "جوهر الهوية والإرادة", "#FF9F0A"),
        ("القمر", _sign_for(chart, "moon"), "الأمان العاطفي والاحتياج", "#0A84FF"),
        ("الطالع", _sign_for(chart, "asc"), "الأسلوب المباشر وربان الخريطة", "#30D158"),
    ]
    cards: list[str] = []
    for label, sign, caption, accent in items:
        if sign is None:
            continue
        ruler = BODIES_AR.get(SIGN_RULERS[sign], "")
        cards.append(
            f"""
            <div class="bento-card big-card" style="--card-accent: {accent}">
              <div class="big-header">
                <span class="big-label">{label}</span>
                <span class="big-pill">حاكمه {html.escape(ruler)}</span>
              </div>
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


def signal_chips(data, limit: int = 5) -> str:
    floor = data.as_of or data.start
    chips: list[str] = []
    polarity_colors = {
        "support": "#30D158",
        "opportunity": "#0A84FF",
        "friction": "#FF453A",
        "info": "#FF9F0A",
    }
    for domain, label in (("self", "شخصي"), ("relationship", "علاقة")):
        for signal in data.signals.get(domain, []):
            if signal.date < floor:
                continue
            color = polarity_colors.get(signal.polarity, "#0A84FF")
            chips.append(
                f'<span class="chip" style="--chip-color: {color}">'
                f'<span class="chip-dot"></span>'
                f'<b>{html.escape(label)}</b> '
                f'{html.escape(format_date_short(signal.date))} · '
                f'{html.escape(signal.text.title)}</span>'
            )
            if len(chips) >= limit:
                break
        if len(chips) >= limit:
            break
    if not chips:
        return '<span class="chip muted">لا إشارات قوية اليوم — إيقاع هادئ</span>'
    return "\n".join(chips)


def render_domain_cards(domains: list[DomainInsight]) -> str:
    cards: list[str] = []
    for item in domains:
        cards.append(
            f"""
            <article class="bento-card domain-card" style="--card-accent: {item.color_hex}">
              <div class="domain-head">
                <div>
                  <span class="domain-kicker">{html.escape(item.badge_ar)}</span>
                  <h3 class="domain-title">{html.escape(item.title_ar)}</h3>
                </div>
                <div class="domain-ring" aria-label="{item.score}%">
                  <span>{item.score}%</span>
                </div>
              </div>
              <div class="domain-bar"><div class="domain-bar-fill" style="width: {item.score}%"></div></div>
              <p class="domain-headline">{html.escape(item.headline)}</p>
              <div class="domain-actions">
                <div class="action-row do-row">
                  <span class="action-tag do-tag">افعل</span>
                  <span>{html.escape(item.action)}</span>
                </div>
                <div class="action-row avoid-row">
                  <span class="action-tag avoid-tag">تجنّب</span>
                  <span>{html.escape(item.avoid)}</span>
                </div>
              </div>
            </article>
            """
        )
    return "\n".join(cards)


def render_classical_cards(
    sect: SectProfile,
    profection: ProfectionYear,
    lunation: LunationPhase,
    lots: dict[str, dict[str, object]],
    eagle_count: int,
    lark_count: int,
) -> str:
    lots_html = ""
    if lots:
        f_lot = lots["fortune"]
        s_lot = lots["spirit"]
        lots_html = f"""
        <div class="classical-pills">
          <span class="mini-pill" style="--pill-color: #30D158">سهم السعادة: {html.escape(str(f_lot['sign_ar']))} (حاكمه {html.escape(str(f_lot['ruler_ar']))})</span>
          <span class="mini-pill" style="--pill-color: #0A84FF">سهم الروح: {html.escape(str(s_lot['sign_ar']))} (حاكمه {html.escape(str(s_lot['ruler_ar']))})</span>
        </div>
        """

    lord_ar = BODIES_AR.get(profection.time_lord, profection.time_lord)
    sign_ar = SIGNS_AR[profection.sign]
    return f"""
    <article class="bento-card classical-card" style="--card-accent: #0A84FF">
      <div class="card-kicker">Dane Rudhyar · The Lunation Cycle</div>
      <h3>{html.escape(lunation.name_ar)}</h3>
      <p>{html.escape(lunation.rhythm_ar)}</p>
      <div class="classical-pills">
        <span class="mini-pill" style="--pill-color: #0A84FF">زاوية القمر والشمس: {lunation.angle}°</span>
        <span class="mini-pill" style="--pill-color: #30D158">نسبة الإضاءة: {lunation.illumination}%</span>
      </div>
    </article>

    <article class="bento-card classical-card" style="--card-accent: #FF9F0A">
      <div class="card-kicker">Vettius Valens & Chris Brennan · Time-Lord</div>
      <h3>حاكم السنة: {html.escape(lord_ar)} · البيت {profection.house} ({html.escape(profection.topic_title)})</h3>
      <p>يفعّل برج <strong>{html.escape(sign_ar)}</strong> محور {html.escape(profection.topic_detail)}.</p>
      <div class="classical-pills">
        <span class="mini-pill" style="--pill-color: #FF9F0A">عدسة النسر الكبرى: {eagle_count} إشارات</span>
        <span class="mini-pill" style="--pill-color: #30D158">نبض القبرة اليومي: {lark_count} إشارات</span>
      </div>
    </article>

    <article class="bento-card classical-card" style="--card-accent: #30D158">
      <div class="card-kicker">Demetra George · Authentic Self & Sect</div>
      <h3>{html.escape(sect.label_ar)}</h3>
      <p>{html.escape(sect.summary_ar)}</p>
      {lots_html}
    </article>
    """


def render_book_shelf(books: list[BookPillar]) -> str:
    cards: list[str] = []
    for idx, book in enumerate(books, start=1):
        cards.append(
            f"""
            <article class="bento-card book-card" style="--card-accent: {book.color_hex}">
              <div class="book-head">
                <span class="book-num">{idx:02d}</span>
                <span class="book-author">{html.escape(book.author_en)}</span>
              </div>
              <h3 class="book-title" dir="ltr">{html.escape(book.title_en)}</h3>
              <div class="book-concept">{html.escape(book.concept_ar)}</div>
              <p class="book-insight">{html.escape(book.personal_insight_ar)}</p>
            </article>
            """
        )
    return "\n".join(cards)


def _chart_visualization_payload(
    chart: Chart,
    profile,
    domains: list[DomainInsight],
    lunation: LunationPhase,
    daily_data,
) -> str:
    planet_Glyphs = {
        "sun": "☉",
        "moon": "☽",
        "mercury": "☿",
        "venus": "♀",
        "mars": "♂",
        "jupiter": "♃",
        "saturn": "♄",
        "uranus": "♅",
        "neptune": "♆",
        "pluto": "♇",
        "node": "☊",
        "asc": "ASC",
        "mc": "MC",
    }
    element_counts = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    points = []
    for body, glyph in planet_Glyphs.items():
        sign = _sign_for(chart, body)
        if sign is None:
            continue
        el = sign_element(sign)
        if body not in {"asc", "mc", "node"}:
            element_counts[el] = element_counts.get(el, 0) + 1
        lon = (
            chart.positions[body].longitude
            if body in chart.positions
            else chart.angles.get(body, sign * 30.0 + 15.0)
        )
        points.append(
            {
                "id": body,
                "label": BODIES_AR.get(body, body),
                "glyph": glyph,
                "lon": round(float(lon), 2),
                "sign": SIGNS_AR[sign],
                "element": el,
                "house": _house_for(chart, body, profile.houses) or 1,
            }
        )

    active_aspects = []
    for sig in daily_data.signals.get("self", [])[:6]:
        active_aspects.append(
            {
                "from": sig.transiting,
                "to": sig.target,
                "aspect": sig.aspect,
                "polarity": sig.polarity,
                "title": sig.text.title,
            }
        )

    payload = {
        "signs": SIGNS_AR,
        "points": points,
        "aspects": active_aspects,
        "lunation": {
            "name": lunation.name_ar,
            "angle": lunation.angle,
            "illumination": lunation.illumination,
        },
        "domains": [
            {
                "title": d.title_ar,
                "score": d.score,
                "color": d.color_hex,
            }
            for d in domains
        ],
        "elements": [
            {"label": "ناري", "key": "fire", "count": element_counts["fire"], "color": "#FF453A"},
            {"label": "ترابي", "key": "earth", "count": element_counts["earth"], "color": "#30D158"},
            {"label": "هوائي", "key": "air", "count": element_counts["air"], "color": "#0A84FF"},
            {"label": "مائي", "key": "water", "count": element_counts["water"], "color": "#FF9F0A"},
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


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
    weekly_data = _data(context, weekly_signals, week_start_day, week_end_day, as_of=day)
    weekly = build_weekly(weekly_data)

    month_start, month_end = month_bounds(day)
    monthly_signals = collect_signals(context, month_start, month_end, daily=False)
    monthly_data = _data(context, monthly_signals, month_start, month_end, as_of=day)
    monthly = build_monthly(monthly_data)

    profile = bundle.self_profile
    chart = context.charts[profile.id]

    lunation = compute_lunation(day, context.tz)
    sect = compute_sect(chart, profile)
    profection = compute_profection(chart, profile, day)
    lots = compute_lots(chart, sect)
    domains = build_life_domains(chart, daily_signals, lunation, as_of=day)
    eagle_sigs, lark_sigs = split_eagle_and_lark(monthly_signals.get("self", []))
    books = build_book_pillars(chart, profile, sect, profection, lunation, monthly_signals)
    chart_json = _chart_visualization_payload(chart, profile, domains, lunation, daily_data)

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
<html lang="ar" dir="rtl" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Astromind — {html.escape(profile.name)} · Apple Bento Edition</title>
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

  /* Official Apple System Colors & Pro Dark Titanium (Default) */
  :root,
  html[data-theme="dark"] {{
    --apple-blue: #0A84FF;
    --apple-orange: #FF9F0A;
    --apple-green: #30D158;
    --apple-red: #FF453A;

    --bg-base: #090A0F;
    --bg-elevated: #12141D;
    --bento-bg: rgba(24, 26, 36, 0.62);
    --bento-bg-strong: rgba(32, 35, 48, 0.78);
    --pill-nav-bg: rgba(20, 22, 32, 0.58);
    --specular-border: rgba(255, 255, 255, 0.13);
    --specular-top: rgba(255, 255, 255, 0.24);
    --hairline-divider: rgba(255, 255, 255, 0.08);

    --text: #F5F5F7;
    --text-secondary: #A1A1AA;
    --muted: #8E8E93;
    --heading-gradient: linear-gradient(135deg, #FFFFFF 0%, #D2E8FF 52%, #0A84FF 100%);
    --card-shadow: 0 22px 48px -12px rgba(0, 0, 0, 0.55), inset 0 1px 0 0 rgba(255, 255, 255, 0.18);
    --nav-shadow: 0 16px 40px rgba(0, 0, 0, 0.5), inset 0 1px 0 0 rgba(255, 255, 255, 0.24);
    --mesh-opacity: 0.16;
    --bento-radius: 25px;
    --radius: 25px;
  }}

  /* Apple Daylight Silver Theme */
  html[data-theme="light"] {{
    --apple-blue: #0A84FF;
    --apple-orange: #FF9F0A;
    --apple-green: #30D158;
    --apple-red: #FF453A;

    --bg-base: #F5F5F7;
    --bg-elevated: #FFFFFF;
    --bento-bg: rgba(255, 255, 255, 0.74);
    --bento-bg-strong: rgba(255, 255, 255, 0.88);
    --pill-nav-bg: rgba(255, 255, 255, 0.68);
    --specular-border: rgba(15, 23, 42, 0.09);
    --specular-top: rgba(255, 255, 255, 0.92);
    --hairline-divider: rgba(15, 23, 42, 0.08);

    --text: #1D1D1F;
    --text-secondary: #48484A;
    --muted: #6E6E73;
    --heading-gradient: linear-gradient(135deg, #1D1D1F 0%, #0A84FF 70%, #FF9F0A 100%);
    --card-shadow: 0 18px 40px -14px rgba(15, 23, 42, 0.09), inset 0 1px 0 0 rgba(255, 255, 255, 0.95);
    --nav-shadow: 0 12px 32px rgba(15, 23, 42, 0.1), inset 0 1px 0 0 rgba(255, 255, 255, 0.95);
    --mesh-opacity: 0.11;
  }}

  * {{ box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    margin: 0;
    min-height: 100vh;
    color: var(--text);
    font-family: "Thmanyah Sans", -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", sans-serif;
    background-color: var(--bg-base);
    background-image:
      radial-gradient(circle at 14% 8%, rgba(10, 132, 255, var(--mesh-opacity)), transparent 34rem),
      radial-gradient(circle at 86% 12%, rgba(255, 159, 10, var(--mesh-opacity)), transparent 30rem),
      radial-gradient(circle at 18% 82%, rgba(48, 209, 88, calc(var(--mesh-opacity) * 0.85)), transparent 32rem),
      radial-gradient(circle at 84% 88%, rgba(255, 69, 58, calc(var(--mesh-opacity) * 0.75)), transparent 32rem);
    background-attachment: fixed;
    line-height: 1.8;
    transition: background-color 0.35s cubic-bezier(0.16, 1, 0.3, 1), color 0.35s ease;
  }}

  /* Floating Glass Pill Navbar */
  .floating-nav-wrap {{
    position: sticky;
    top: 1rem;
    z-index: 100;
    display: flex;
    justify-content: center;
    padding: 0 1rem;
    margin-top: 1rem;
  }}
  .floating-pill-nav {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.65rem;
    width: min(1160px, 100%);
    padding: 0.55rem 0.85rem;
    border-radius: 999px;
    background: var(--pill-nav-bg);
    backdrop-filter: saturate(180%) blur(28px);
    -webkit-backdrop-filter: saturate(180%) blur(28px);
    border: 1px solid var(--specular-border);
    box-shadow: var(--nav-shadow);
    transition: background 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  }}
  .nav-brand {{
    display: inline-flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.25rem 0.65rem;
    font-weight: 700;
    font-size: 0.92rem;
    color: var(--text);
    text-decoration: none;
    white-space: nowrap;
  }}
  .brand-orb {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--apple-blue), var(--apple-orange));
    box-shadow: 0 0 12px var(--apple-blue);
  }}
  .nav-links {{
    display: flex;
    align-items: center;
    gap: 0.25rem;
    overflow-x: auto;
    scrollbar-width: none;
  }}
  .nav-links::-webkit-scrollbar {{ display: none; }}
  .nav-link {{
    appearance: none;
    border: 1px solid transparent;
    background: transparent;
    color: var(--text-secondary);
    font-family: inherit;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.38rem 0.82rem;
    border-radius: 999px;
    text-decoration: none;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.22s ease;
  }}
  .nav-link:hover,
  .nav-link.active {{
    color: var(--text);
    background: rgba(10, 132, 255, 0.14);
    border-color: rgba(10, 132, 255, 0.34);
  }}

  /* Instant Theme Switcher Pill (Pro Dark Titanium <-> Apple Daylight Silver) */
  .theme-toggle {{
    appearance: none;
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.42rem 0.9rem;
    border-radius: 999px;
    border: 1px solid var(--specular-border);
    background: linear-gradient(135deg, rgba(10, 132, 255, 0.16), rgba(255, 159, 10, 0.14));
    color: var(--text);
    font-family: inherit;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    white-space: nowrap;
    box-shadow: inset 0 1px 0 0 var(--specular-top);
    transition: transform 0.2s ease, border-color 0.2s ease;
  }}
  .theme-toggle:hover {{
    transform: translateY(-1px);
    border-color: var(--apple-blue);
  }}
  .theme-indicator {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--apple-orange);
    box-shadow: 0 0 8px var(--apple-orange);
  }}

  .wrap {{
    position: relative;
    width: min(1180px, calc(100% - 2rem));
    margin: 0 auto;
    padding: 1.8rem 0 4.5rem;
  }}

  /* Apple Bento Cards & Specular Hairline Borders */
  .bento-card {{
    position: relative;
    overflow: hidden;
    border-radius: var(--bento-radius);
    background: var(--bento-bg);
    backdrop-filter: saturate(180%) blur(28px);
    -webkit-backdrop-filter: saturate(180%) blur(28px);
    border: 1px solid var(--specular-border);
    box-shadow: var(--card-shadow);
    padding: 1.5rem;
    transition: transform 0.28s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.28s ease, background 0.3s ease;
  }}
  .bento-card::before {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: inherit;
    background: radial-gradient(
      circle at 90% 10%,
      color-mix(in srgb, var(--card-accent, var(--apple-blue)) 18%, transparent),
      transparent 62%
    );
    opacity: 0.9;
  }}
  .bento-card > * {{
    position: relative;
    z-index: 1;
  }}

  /* Hero Bento Header */
  header.hero-bento {{
    display: grid;
    grid-template-columns: 1.35fr 1fr;
    gap: 1.1rem;
    margin-bottom: 1.1rem;
  }}
  .hero-main {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 2rem;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    width: fit-content;
    border: 1px solid var(--specular-border);
    border-radius: 999px;
    padding: 0.32rem 0.9rem;
    color: var(--text-secondary);
    background: rgba(10, 132, 255, 0.1);
    font-size: 0.82rem;
    font-weight: 500;
  }}
  .dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--apple-green);
    box-shadow: 0 0 10px var(--apple-green);
  }}
  h1 {{
    font-size: clamp(2.1rem, 4.6vw, 3.5rem);
    line-height: 1.12;
    margin: 0.85rem 0 0.35rem;
    letter-spacing: -0.02em;
    font-family: "Thmanyah Serif Display", serif;
    font-weight: 900;
  }}
  h1 span {{
    background: var(--heading-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }}
  .subtitle {{
    color: var(--text-secondary);
    font-size: clamp(1rem, 1.8vw, 1.15rem);
    margin: 0 0 1rem;
    font-weight: 500;
  }}
  .hero-meta-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.6rem;
  }}
  .meta-tag {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--specular-border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-secondary);
  }}
  .meta-tag strong {{ color: var(--text); }}

  /* Hero Quick Pulse Card */
  .hero-pulse {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 0.75rem;
  }}
  .pulse-kicker {{
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--apple-orange);
    letter-spacing: 0.03em;
  }}
  .pulse-title {{
    font-family: "Thmanyah Serif Display", serif;
    font-size: 1.35rem;
    font-weight: 700;
    margin: 0.15rem 0;
  }}
  .pulse-desc {{
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.92rem;
  }}
  .confidence-banner {{
    padding: 0.75rem 0.95rem;
    border-radius: 18px;
    border: 1px solid rgba(255, 159, 10, 0.28);
    background: rgba(255, 159, 10, 0.08);
    font-size: 0.82rem;
    color: var(--text-secondary);
  }}
  .confidence-banner strong {{ color: var(--text); }}

  /* Big Three Bento Row */
  .big-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.1rem;
    margin-bottom: 1.6rem;
  }}
  .big-card {{
    padding: 1.35rem 1.4rem;
  }}
  .big-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }}
  .big-label {{
    color: var(--text-secondary);
    font-size: 0.88rem;
    font-weight: 500;
  }}
  .big-pill {{
    font-size: 0.74rem;
    padding: 0.18rem 0.6rem;
    border-radius: 999px;
    border: 1px solid var(--specular-border);
    color: var(--text-secondary);
  }}
  .big-sign {{
    font-size: clamp(1.65rem, 3.5vw, 2.25rem);
    font-weight: 900;
    margin: 0.35rem 0 0.2rem;
    font-family: "Thmanyah Serif Display", serif;
    color: var(--text);
  }}
  .big-caption {{
    color: var(--muted);
    font-size: 0.83rem;
  }}

  /* Section Headers */
  section {{ margin-top: 2.4rem; }}
  .section-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }}
  h2 {{
    font-size: clamp(1.35rem, 2.6vw, 1.85rem);
    margin: 0;
    font-family: "Thmanyah Serif Display", serif;
    font-weight: 700;
  }}
  .section-head p {{
    margin: 0;
    color: var(--muted);
    font-size: 0.9rem;
  }}

  /* 4 Life-Domains Bento Grid */
  .domains-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1.1rem;
  }}
  .domain-card {{
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }}
  .domain-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
  }}
  .domain-kicker {{
    display: inline-block;
    font-size: 0.76rem;
    font-weight: 700;
    color: var(--card-accent);
  }}
  .domain-title {{
    margin: 0.1rem 0 0;
    font-size: 1.25rem;
    font-family: "Thmanyah Serif Display", serif;
  }}
  .domain-ring {{
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 2px solid var(--card-accent);
    background: color-mix(in srgb, var(--card-accent) 12%, transparent);
    font-weight: 700;
    font-size: 0.84rem;
    font-variant-numeric: tabular-nums;
  }}
  .domain-bar {{
    height: 6px;
    border-radius: 999px;
    background: var(--hairline-divider);
    overflow: hidden;
  }}
  .domain-bar-fill {{
    height: 100%;
    border-radius: 999px;
    background: var(--card-accent);
  }}
  .domain-headline {{
    margin: 0;
    font-size: 0.95rem;
    color: var(--text);
  }}
  .domain-actions {{
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    margin-top: auto;
    padding-top: 0.4rem;
    border-top: 1px solid var(--hairline-divider);
    font-size: 0.86rem;
  }}
  .action-row {{
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    color: var(--text-secondary);
  }}
  .action-tag {{
    flex-shrink: 0;
    font-size: 0.73rem;
    font-weight: 700;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
  }}
  .do-tag {{
    background: rgba(48, 209, 88, 0.16);
    color: var(--apple-green);
    border: 1px solid rgba(48, 209, 88, 0.35);
  }}
  .avoid-tag {{
    background: rgba(255, 69, 58, 0.15);
    color: var(--apple-red);
    border: 1px solid rgba(255, 69, 58, 0.35);
  }}

  /* Segmented Apple Pill Tabs for Daily / Weekly / Monthly / Story */
  .reading-hub-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.8rem;
    margin-bottom: 1rem;
  }}
  .tabs {{
    display: inline-flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    padding: 0.35rem;
    border-radius: 999px;
    background: var(--pill-nav-bg);
    backdrop-filter: saturate(180%) blur(28px);
    -webkit-backdrop-filter: saturate(180%) blur(28px);
    border: 1px solid var(--specular-border);
    box-shadow: inset 0 1px 0 0 var(--specular-top);
  }}
  .tab {{
    appearance: none;
    border: 1px solid transparent;
    border-radius: 999px;
    cursor: pointer;
    background: transparent;
    color: var(--text-secondary);
    font-family: inherit;
    font-size: 0.9rem;
    font-weight: 700;
    padding: 0.48rem 1.15rem;
    transition: all 0.22s ease;
  }}
  .tab:hover {{ color: var(--text); }}
  .tab.active {{
    background: var(--apple-blue);
    color: #FFFFFF;
    box-shadow: 0 6px 18px rgba(10, 132, 255, 0.38);
  }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; animation: fadeIn 0.28s ease; }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}

  /* Report & Reading Card Typography */
  .report {{
    border-radius: var(--bento-radius);
    background: var(--bento-bg-strong);
    backdrop-filter: saturate(180%) blur(28px);
    -webkit-backdrop-filter: saturate(180%) blur(28px);
    border: 1px solid var(--specular-border);
    box-shadow: var(--card-shadow);
    padding: clamp(1.25rem, 3vw, 2.2rem);
  }}
  .report h1,
  .report .reading-title {{
    font-size: clamp(1.45rem, 2.8vw, 1.95rem);
    font-family: "Thmanyah Serif Display", serif;
    font-weight: 900;
    margin: 0 0 1rem;
    background: var(--heading-gradient);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
  }}
  .report h2 {{
    font-size: 1.22rem;
    margin: 1.5rem 0 0.6rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--hairline-divider);
    color: var(--apple-blue);
    font-family: "Thmanyah Serif Display", serif;
  }}
  .report h3 {{
    font-size: 1.06rem;
    margin: 1.15rem 0 0.4rem;
    color: var(--apple-orange);
    font-family: "Thmanyah Serif Display", serif;
  }}
  .report p {{ margin: 0.65rem 0; color: var(--text); }}
  .report strong {{ color: var(--text); font-weight: 700; }}
  .report ul {{ margin: 0.45rem 0 0.9rem; padding-inline-start: 1.25rem; }}
  .report li {{ margin: 0.35rem 0; }}
  .report ul.sublist {{ margin: 0.2rem 0 0.4rem; color: var(--text-secondary); font-size: 0.92rem; }}
  .report blockquote {{
    margin: 1.2rem 0 0;
    padding: 0.85rem 1.1rem;
    border-radius: 16px;
    border-inline-start: 3px solid var(--apple-blue);
    background: rgba(10, 132, 255, 0.08);
    color: var(--text-secondary);
    font-size: 0.9rem;
  }}
  .reading-divider {{
    border: 0;
    height: 1px;
    margin: 1.1rem 0;
    background: linear-gradient(90deg, transparent, var(--specular-border), transparent);
  }}

  .table-wrap {{ overflow-x: auto; margin: 0.85rem 0; border-radius: 16px; border: 1px solid var(--hairline-divider); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th, td {{ padding: 0.65rem 0.75rem; border-bottom: 1px solid var(--hairline-divider); text-align: right; }}
  th {{ color: var(--apple-blue); font-weight: 700; background: rgba(10, 132, 255, 0.06); }}

  /* Signal Chips */
  .chips {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0 0; }}
  .chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    border: 1px solid var(--specular-border);
    border-radius: 999px;
    padding: 0.32rem 0.8rem;
    color: var(--text-secondary);
    font-size: 0.8rem;
    background: var(--bento-bg);
    backdrop-filter: blur(16px);
  }}
  .chip-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--chip-color, var(--apple-blue));
    box-shadow: 0 0 8px var(--chip-color, var(--apple-blue));
  }}
  .chip b {{ color: var(--text); font-weight: 700; }}

  /* Interactive Charts Bento Grid */
  .charts-bento-grid {{
    display: grid;
    grid-template-columns: 1.15fr 0.85fr;
    gap: 1.1rem;
  }}
  .chart-box {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: space-between;
  }}
  .chart-box-head {{
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.6rem;
  }}
  .chart-box-head h3 {{
    margin: 0;
    font-size: 1.12rem;
    font-family: "Thmanyah Serif Display", serif;
  }}
  .chart-legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    font-size: 0.76rem;
    color: var(--text-secondary);
    margin-top: 0.65rem;
  }}
  .legend-item {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
  }}
  .legend-swatch {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }}
  canvas.astro-canvas {{
    width: 100%;
    max-width: 420px;
    height: auto;
    aspect-ratio: 1 / 1;
    display: block;
  }}

  /* Classical Trio Bento Grid */
  .classical-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.1rem;
  }}
  .classical-card h3 {{
    margin: 0.25rem 0 0.45rem;
    font-size: 1.15rem;
    font-family: "Thmanyah Serif Display", serif;
  }}
  .classical-card p {{
    margin: 0 0 0.8rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }}
  .card-kicker {{
    font-size: 0.74rem;
    font-weight: 700;
    color: var(--card-accent);
    letter-spacing: 0.02em;
  }}
  .classical-pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: auto;
  }}
  .mini-pill {{
    font-size: 0.75rem;
    padding: 0.22rem 0.65rem;
    border-radius: 999px;
    border: 1px solid color-mix(in srgb, var(--pill-color, var(--apple-blue)) 40%, transparent);
    background: color-mix(in srgb, var(--pill-color, var(--apple-blue)) 12%, transparent);
    color: var(--text);
  }}

  /* Top 10 Books Bento Shelf */
  .books-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1rem;
  }}
  .book-card {{
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }}
  .book-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.76rem;
    color: var(--muted);
  }}
  .book-num {{
    font-weight: 900;
    color: var(--card-accent);
    font-variant-numeric: tabular-nums;
  }}
  .book-title {{
    margin: 0.1rem 0;
    font-size: 0.98rem;
    font-weight: 700;
    color: var(--text);
    text-align: left;
  }}
  .book-concept {{
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--card-accent);
  }}
  .book-insight {{
    margin: 0.2rem 0 0;
    font-size: 0.86rem;
    color: var(--text-secondary);
  }}

  /* Natal Placements Fold & Cards */
  .fold {{
    margin-top: 1.8rem;
    border: 1px solid var(--specular-border);
    border-radius: var(--bento-radius);
    background: var(--bento-bg);
    backdrop-filter: saturate(180%) blur(28px);
    -webkit-backdrop-filter: saturate(180%) blur(28px);
    box-shadow: var(--card-shadow);
    overflow: hidden;
  }}
  .fold > summary {{
    cursor: pointer;
    list-style: none;
    padding: 1.15rem 1.4rem;
    font-family: "Thmanyah Serif Display", serif;
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--text);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .fold > summary::-webkit-details-marker {{ display: none; }}
  .fold > summary::after {{ content: "+"; color: var(--apple-blue); font-size: 1.25rem; font-weight: 700; }}
  .fold[open] > summary {{ border-bottom: 1px solid var(--hairline-divider); }}
  .fold[open] > summary::after {{ content: "−"; }}
  .fold-body {{ padding: 1.2rem 1.4rem 1.5rem; }}
  .fold-note {{ margin: 0 0 1rem; color: var(--muted); font-size: 0.86rem; }}

  .placements {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
    gap: 0.85rem;
  }}
  .placement {{
    border: 1px solid var(--specular-border);
    border-radius: 20px;
    padding: 0.95rem 1rem;
    background: var(--bento-bg-strong);
    box-shadow: inset 0 1px 0 0 var(--specular-top);
  }}
  .placement-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .placement-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--pill-accent, var(--apple-blue));
  }}
  .placement-body {{ color: var(--text-secondary); font-size: 0.82rem; font-weight: 500; }}
  .placement-sign {{
    color: var(--text);
    font-size: 1.35rem;
    font-weight: 700;
    margin: 0.15rem 0 0.2rem;
    font-family: "Thmanyah Serif Display", serif;
  }}
  .placement-degree {{
    color: var(--apple-blue);
    font-size: 0.78rem;
    margin-bottom: 0.2rem;
    font-variant-numeric: tabular-nums;
  }}
  .placement-meta {{
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    color: var(--muted);
    font-size: 0.76rem;
  }}
  .placement-ruler {{
    margin-top: 0.35rem;
    padding-top: 0.35rem;
    border-top: 1px solid var(--hairline-divider);
    font-size: 0.74rem;
    color: var(--text-secondary);
  }}

  footer {{
    margin-top: 3.2rem;
    padding-top: 1.4rem;
    border-top: 1px solid var(--hairline-divider);
    color: var(--muted);
    font-size: 0.85rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem 1.2rem;
    justify-content: space-between;
  }}
  footer a {{ color: var(--apple-blue); text-decoration: none; font-weight: 500; }}

  @media (max-width: 900px) {{
    header.hero-bento,
    .charts-bento-grid,
    .classical-grid,
    .domains-grid {{
      grid-template-columns: 1fr;
    }}
    .big-grid {{
      grid-template-columns: 1fr;
    }}
  }}
</style>
</head>
<body>

<!-- Floating Glass Pill Navbar -->
<div class="floating-nav-wrap">
  <nav class="floating-pill-nav" aria-label="التنقل الرئيسي">
    <a class="nav-brand" href="#top">
      <span class="brand-orb"></span>
      <span>Astromind</span>
    </a>
    <div class="nav-links">
      <button type="button" class="nav-link active" data-jump-panel="daily">قراءة اليوم</button>
      <button type="button" class="nav-link" data-jump-panel="weekly">موجز الأسبوع</button>
      <button type="button" class="nav-link" data-jump-panel="monthly">الدليل الشهري</button>
      <button type="button" class="nav-link" data-jump-panel="story">القراءة التأملية</button>
      <a class="nav-link" href="#compass">النواحي الأربع</a>
      <a class="nav-link" href="#charts">المخططات الحية</a>
      <a class="nav-link" href="#books">الكتب العشرة</a>
    </div>
    <button type="button" class="theme-toggle" id="themeToggle" aria-label="تبديل المظهر بين الليلي والنهاري">
      <span class="theme-indicator"></span>
      <span id="themeLabel">Pro Dark Titanium</span>
    </button>
  </nav>
</div>

<div class="wrap" id="top">
  <!-- Hero Apple Bento Section -->
  <header class="hero-bento">
    <div class="bento-card hero-main" style="--card-accent: #0A84FF">
      <div>
        <div class="badge"><span class="dot"></span> قراءة يومية وأسبوعية وشهرية · جذور التنجيم الكلاسيكي والنفسي</div>
        <h1><span>{html.escape(profile.name)}</span></h1>
        <p class="subtitle">{html.escape(signature(chart))}</p>
      </div>
      <div class="hero-meta-bar">
        <span class="meta-tag"><strong>التاريخ:</strong> {html.escape(format_date(day, include_weekday=True))}</span>
        <span class="meta-tag"><strong>الحيز:</strong> {html.escape(sect.label_ar)}</span>
        <span class="meta-tag"><strong>حاكم السنة:</strong> {html.escape(BODIES_AR.get(profection.time_lord, profection.time_lord))} (البيت {profection.house})</span>
      </div>
    </div>

    <div class="bento-card hero-pulse" style="--card-accent: #FF9F0A">
      <div>
        <div class="pulse-kicker">طور القمر اليوم · Dane Rudhyar</div>
        <div class="pulse-title">{html.escape(lunation.name_ar)}</div>
        <p class="pulse-desc">{html.escape(lunation.rhythm_ar)}</p>
      </div>
      <div class="confidence-banner">
        <strong>حدود القراءة:</strong> {html.escape(confidence)}
        <div style="margin-top:0.25rem">{html.escape(birth_line(profile, city))}</div>
      </div>
    </div>
  </header>

  <!-- Big Three Bento Row -->
  <div class="big-grid">
    {big_three(chart)}
  </div>

  <!-- Primary Interactive Reading Hub (Daily / Weekly / Monthly / Story) -->
  <section id="readings">
    <div class="reading-hub-bar">
      <div>
        <h2>القراءات الذكية — اليوم · الأسبوع · الشهر</h2>
        <p>مصممة لتكون خفيفة، سريعة الفهم، وشاملة لكل نواحي حياتك اليومية</p>
      </div>
      <div class="tabs" role="tablist" aria-label="تبديل القراءة">
        <button class="tab active" data-panel="daily" role="tab" aria-selected="true">قراءة اليوم</button>
        <button class="tab" data-panel="weekly" role="tab" aria-selected="false">موجز الأسبوع</button>
        <button class="tab" data-panel="monthly" role="tab" aria-selected="false">الدليل الشهري</button>
        <button class="tab" data-panel="story" role="tab" aria-selected="false">القراءة التأملية</button>
      </div>
    </div>

    <div class="panel active" id="daily">
      <div class="report reading-card">{markdown_to_html(daily)}</div>
    </div>
    <div class="panel" id="weekly">
      <div class="report reading-card">{markdown_to_html(weekly)}</div>
    </div>
    <div class="panel" id="monthly">
      <div class="report reading-card">{markdown_to_html(monthly)}</div>
    </div>
    <div class="panel" id="story">
      <div class="report reading-card">{markdown_to_html(reading)}</div>
    </div>

    <div class="chips">
      {signal_chips(daily_data)}
    </div>
  </section>

  <!-- 4 Life-Domains Bento Compass -->
  <section id="compass">
    <div class="section-head">
      <h2>بوصلة النواحي الأربع الشاملة</h2>
      <p>خلاصة تطبيقية خفيفة للعمل، المال، العلاقات، والطاقة اليومية</p>
    </div>
    <div class="domains-grid">
      {render_domain_cards(domains)}
    </div>
  </section>

  <!-- Interactive Astrological Charts Bento (Auto-redraws on Theme Switch) -->
  <section id="charts">
    <div class="section-head">
      <h2>المخططات الفلكية الحية</h2>
      <p>تُعاد رسمها تلقائيًا عند التبديل بين Pro Dark Titanium و Apple Daylight Silver</p>
    </div>
    <div class="charts-bento-grid">
      <div class="bento-card chart-box" style="--card-accent: #0A84FF">
        <div class="chart-box-head">
          <h3>دائرة البروج والعبورات الفعالة</h3>
          <span class="mini-pill" style="--pill-color: #0A84FF">Whole-Sign / Ecliptic</span>
        </div>
        <canvas id="wheelCanvas" class="astro-canvas" width="440" height="440"></canvas>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-swatch" style="background:#30D158"></span> تدفق ودعم</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#0A84FF"></span> فرصة وتواصل</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#FF9F0A"></span> حيوية وقرار</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#FF453A"></span> تقاطع يحتاج هدوءًا</span>
        </div>
      </div>

      <div class="bento-card chart-box" style="--card-accent: #30D158">
        <div class="chart-box-head">
          <h3>توازن النواحي الأربع والعناصر</h3>
          <span class="mini-pill" style="--pill-color: #30D158">مؤشر الاتزان الحي</span>
        </div>
        <canvas id="radarCanvas" class="astro-canvas" width="440" height="440"></canvas>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-swatch" style="background:#FF9F0A"></span> العمل</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#30D158"></span> المال</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#0A84FF"></span> العلاقات</span>
          <span class="legend-item"><span class="legend-swatch" style="background:#FF453A"></span> الطاقة</span>
        </div>
      </div>
    </div>
  </section>

  <!-- Classical Pillars Trio (Rudhyar, Valens/Brennan, George) -->
  <section id="classical">
    <div class="section-head">
      <h2>المرتكزات الكلاسيكية النشطة</h2>
      <p>قراءة الحيز الفلكي، حاكم السنة، والدورة القمرية</p>
    </div>
    <div class="classical-grid">
      {render_classical_cards(sect, profection, lunation, lots, len(eagle_sigs), len(lark_sigs))}
    </div>
  </section>

  <!-- The 10 Foundational Astrology Books Shelf -->
  <section id="books">
    <div class="section-head">
      <h2>الكتب العشرة المؤسسة للقراءة</h2>
      <p>كيف تُترجم أمهات كتب التنجيم الكلاسيكي والحديث خريطتك اليوم بلغة واضحة</p>
    </div>
    <div class="books-grid">
      {render_book_shelf(books)}
    </div>
  </section>

  <!-- Full Natal Placements Fold -->
  <details class="fold">
    <summary>المواضع الفلكية الكاملة وحكامها</summary>
    <div class="fold-body">
      <p class="fold-note">الأبراج + البيوت {html.escape("بنظام البيوت الكاملة" if chart.sign_only else f"بنظام {chart.house_system}")} مع حاكم كل موضع حسب القواعد الكلاسيكية.</p>
      <div class="placements">
        {placement_cards(chart, profile)}
      </div>
    </div>
  </details>

  <footer>
    <span>تم التوليد بتاريخ {day.isoformat()} · محرك Astromind · هوية Apple Bento & Frosted Glass</span>
    <span><a href="https://github.com/muxd22-alt/ASTR">المستودع على GitHub</a></span>
  </footer>
</div>

<script>
  const ASTRO_DATA = {chart_json};

  // Reading Tab & Navbar Switcher
  const tabs = document.querySelectorAll(".tab");
  const navJumpButtons = document.querySelectorAll("[data-jump-panel]");
  const panels = document.querySelectorAll(".panel");

  function activatePanel(panelId) {{
    tabs.forEach((item) => {{
      const active = item.dataset.panel === panelId;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", active ? "true" : "false");
    }});
    navJumpButtons.forEach((btn) => {{
      btn.classList.toggle("active", btn.dataset.jumpPanel === panelId);
    }});
    panels.forEach((item) => {{
      item.classList.toggle("active", item.id === panelId);
    }});
  }}

  tabs.forEach((tab) => {{
    tab.addEventListener("click", () => activatePanel(tab.dataset.panel));
  }});

  navJumpButtons.forEach((btn) => {{
    btn.addEventListener("click", () => {{
      activatePanel(btn.dataset.jumpPanel);
      document.getElementById("readings").scrollIntoView({{ behavior: "smooth", block: "start" }});
    }});
  }});

  // Theme Toggle (Pro Dark Titanium <-> Apple Daylight Silver) with automatic chart redraw
  const rootHtml = document.documentElement;
  const themeToggle = document.getElementById("themeToggle");
  const themeLabel = document.getElementById("themeLabel");

  function currentTheme() {{
    return rootHtml.getAttribute("data-theme") || "dark";
  }}

  function applyTheme(theme) {{
    rootHtml.setAttribute("data-theme", theme);
    themeLabel.textContent = theme === "dark" ? "Pro Dark Titanium" : "Apple Daylight Silver";
    try {{
      localStorage.setItem("astromind-apple-theme", theme);
    }} catch (_) {{}}
    redrawAllCharts();
  }}

  themeToggle.addEventListener("click", () => {{
    const next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
  }});

  // High-DPI Canvas setup helper
  function prepareCanvas(canvas) {{
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const size = Math.max(280, Math.min(rect.width || 400, 440));
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return {{ ctx, size }};
  }}

  function drawWheelChart(theme) {{
    const canvas = document.getElementById("wheelCanvas");
    if (!canvas) return;
    const {{ ctx, size }} = prepareCanvas(canvas);
    const cx = size / 2;
    const cy = size / 2;
    const outerR = size * 0.45;
    const signR = size * 0.36;
    const planetR = size * 0.27;
    const innerR = size * 0.16;

    const isDark = theme === "dark";
    const strokeRing = isDark ? "rgba(255,255,255,0.16)" : "rgba(15,23,42,0.14)";
    const strokeSubtle = isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)";
    const textMain = isDark ? "#F5F5F7" : "#1D1D1F";
    const textMuted = isDark ? "#A1A1AA" : "#6E6E73";
    const centerFill = isDark ? "rgba(18, 20, 29, 0.85)" : "rgba(255, 255, 255, 0.9)";

    ctx.clearRect(0, 0, size, size);

    // Subtle ambient ring glow
    const grad = ctx.createRadialGradient(cx, cy, innerR * 0.4, cx, cy, outerR);
    grad.addColorStop(0, isDark ? "rgba(10, 132, 255, 0.12)" : "rgba(10, 132, 255, 0.08)");
    grad.addColorStop(0.65, isDark ? "rgba(255, 159, 10, 0.06)" : "rgba(255, 159, 10, 0.05)");
    grad.addColorStop(1, "transparent");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, outerR, 0, Math.PI * 2);
    ctx.fill();

    // Concentric rings
    [outerR, signR, innerR].forEach((r, idx) => {{
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = idx === 0 ? strokeRing : strokeSubtle;
      ctx.lineWidth = idx === 0 ? 1.5 : 1;
      ctx.stroke();
    }});

    // 12 Zodiac Sign sectors
    const elColors = ["#FF453A", "#30D158", "#0A84FF", "#FF9F0A"];
    ASTRO_DATA.signs.forEach((signName, i) => {{
      const startAng = ((i * 30 - 90) * Math.PI) / 180;
      const midAng = (((i * 30 + 15) - 90) * Math.PI) / 180;
      const x1 = cx + Math.cos(startAng) * innerR;
      const y1 = cy + Math.sin(startAng) * innerR;
      const x2 = cx + Math.cos(startAng) * outerR;
      const y2 = cy + Math.sin(startAng) * outerR;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = strokeSubtle;
      ctx.lineWidth = 1;
      ctx.stroke();

      const labelR = (outerR + signR) / 2;
      const lx = cx + Math.cos(midAng) * labelR;
      const ly = cy + Math.sin(midAng) * labelR;
      ctx.fillStyle = elColors[i % 4];
      ctx.font = `700 ${{Math.max(10, Math.round(size * 0.027))}}px "Thmanyah Sans", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(signName, lx, ly);
    }});

    // Map planet coordinates
    const coords = {{}};
    ASTRO_DATA.points.forEach((pt, idx) => {{
      const ang = ((pt.lon - 90) * Math.PI) / 180;
      const rOffset = (idx % 2 === 0 ? 0 : -14);
      const r = planetR + rOffset;
      const x = cx + Math.cos(ang) * r;
      const y = cy + Math.sin(ang) * r;
      coords[pt.id] = {{ x, y, pt }};
    }});

    // Draw active aspect chords
    const polColor = {{
      support: "#30D158",
      opportunity: "#0A84FF",
      friction: "#FF453A",
      info: "#FF9F0A"
    }};
    ASTRO_DATA.aspects.forEach((asp) => {{
      const a = coords[asp.from];
      const b = coords[asp.to];
      if (!a || !b) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = polColor[asp.polarity] || "#0A84FF";
      ctx.lineWidth = 1.6;
      ctx.globalAlpha = 0.72;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }});

    // Draw planet nodes
    const elNodeColor = {{
      fire: "#FF453A",
      earth: "#30D158",
      air: "#0A84FF",
      water: "#FF9F0A"
    }};
    Object.values(coords).forEach(({{ x, y, pt }}) => {{
      const c = elNodeColor[pt.element] || "#0A84FF";
      ctx.beginPath();
      ctx.arc(x, y, 11, 0, Math.PI * 2);
      ctx.fillStyle = centerFill;
      ctx.fill();
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = c;
      ctx.stroke();

      ctx.fillStyle = textMain;
      ctx.font = `700 10px "Thmanyah Sans", sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(pt.glyph, x, y);
    }});

    // Center hub (Lunation illumination)
    ctx.beginPath();
    ctx.arc(cx, cy, innerR - 4, 0, Math.PI * 2);
    ctx.fillStyle = centerFill;
    ctx.fill();

    ctx.fillStyle = textMain;
    ctx.font = `700 ${{Math.round(size * 0.036)}}px "Thmanyah Serif Display", serif`;
    ctx.textAlign = "center";
    ctx.fillText(`${{ASTRO_DATA.lunation.illumination}}%`, cx, cy - 8);

    ctx.fillStyle = textMuted;
    ctx.font = `500 ${{Math.round(size * 0.024)}}px "Thmanyah Sans", sans-serif`;
    ctx.fillText("إضاءة القمر", cx, cy + 12);
  }}

  function drawDomainsChart(theme) {{
    const canvas = document.getElementById("radarCanvas");
    if (!canvas) return;
    const {{ ctx, size }} = prepareCanvas(canvas);
    const isDark = theme === "dark";
    const textMain = isDark ? "#F5F5F7" : "#1D1D1F";
    const textMuted = isDark ? "#A1A1AA" : "#6E6E73";
    const trackBg = isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)";

    ctx.clearRect(0, 0, size, size);

    const padX = size * 0.08;
    let y = size * 0.11;

    ctx.fillStyle = textMain;
    ctx.font = `700 ${{Math.round(size * 0.033)}}px "Thmanyah Serif Display", serif`;
    ctx.textAlign = "right";
    ctx.fillText("حيوية النواحي الأربع اليوم", size - padX, y);
    y += size * 0.07;

    const barW = size - padX * 2;
    ASTRO_DATA.domains.forEach((d) => {{
      ctx.fillStyle = textMain;
      ctx.font = `700 ${{Math.round(size * 0.028)}}px "Thmanyah Sans", sans-serif`;
      ctx.textAlign = "right";
      ctx.fillText(d.title, size - padX, y);

      ctx.fillStyle = d.color;
      ctx.textAlign = "left";
      ctx.fillText(`${{d.score}}%`, padX, y);

      y += size * 0.032;
      ctx.fillStyle = trackBg;
      ctx.beginPath();
      ctx.roundRect(padX, y, barW, 10, 6);
      ctx.fill();

      const fillW = (barW * d.score) / 100;
      ctx.fillStyle = d.color;
      ctx.beginPath();
      ctx.roundRect(size - padX - fillW, y, fillW, 10, 6);
      ctx.fill();

      y += size * 0.082;
    }});

    y += size * 0.02;
    ctx.fillStyle = textMain;
    ctx.font = `700 ${{Math.round(size * 0.033)}}px "Thmanyah Serif Display", serif`;
    ctx.textAlign = "right";
    ctx.fillText("توزيع العناصر الأربعة في الخريطة", size - padX, y);
    y += size * 0.065;

    const totalEl = ASTRO_DATA.elements.reduce((acc, item) => acc + item.count, 0) || 1;
    const pillW = (barW - 18) / 4;
    ASTRO_DATA.elements.forEach((el, idx) => {{
      const x = size - padX - (idx + 1) * pillW - idx * 6;
      const pct = Math.round((el.count / totalEl) * 100);
      ctx.fillStyle = trackBg;
      ctx.beginPath();
      ctx.roundRect(x, y, pillW, size * 0.16, 14);
      ctx.fill();

      ctx.strokeStyle = el.color;
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ctx.fillStyle = el.color;
      ctx.font = `700 ${{Math.round(size * 0.036)}}px "Thmanyah Serif Display", serif`;
      ctx.textAlign = "center";
      ctx.fillText(`${{pct}}%`, x + pillW / 2, y + size * 0.065);

      ctx.fillStyle = textMuted;
      ctx.font = `500 ${{Math.round(size * 0.025)}}px "Thmanyah Sans", sans-serif`;
      ctx.fillText(el.label, x + pillW / 2, y + size * 0.12);
    }});
  }}

  function redrawAllCharts() {{
    const theme = currentTheme();
    drawWheelChart(theme);
    drawDomainsChart(theme);
  }}

  // Restore saved theme or default to Pro Dark Titanium, and draw charts
  try {{
    const saved = localStorage.getItem("astromind-apple-theme");
    if (saved === "light" || saved === "dark") {{
      rootHtml.setAttribute("data-theme", saved);
      themeLabel.textContent = saved === "dark" ? "Pro Dark Titanium" : "Apple Daylight Silver";
    }}
  }} catch (_) {{}}

  window.addEventListener("resize", redrawAllCharts);
  redrawAllCharts();
</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build docs/index.html from a profile bundle"
    )
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
    print(
        f"wrote {output} ({len(page)} chars) for {bundle.self_profile.name} on {day}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
