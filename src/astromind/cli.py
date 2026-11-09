"""Command-line entry point for the Astromind multi-profile engine."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from astromind.engines import ephemeris
from astromind.engines.charts import Chart, build_chart, build_composite, chart_facts
from astromind.engines.child_development import build_child_guidance
from astromind.engines.signals import (
    Signal,
    changed_since,
    make_signals,
    mark_seen,
    rank,
)
from astromind.engines.synastry import SynastryAspect, compute_synastry
from astromind.engines.transits import (
    hits_for_day,
    scan_period,
    sign_hits_for_day,
    sign_scan_period,
)
from astromind.generators.calendar_ics import build_calendar
from astromind.generators.md_builder import (
    ReportData,
    build_child_manual,
    build_daily,
    build_index,
    build_monthly,
    build_partner_manual,
    build_weekly,
)
from astromind.models import Bundle, ProfileError
from astromind.profiles import encode_file, load_bundle
from astromind.state import default_state, load_state, prune, save_state


@dataclass
class Context:
    bundle: Bundle
    charts: dict[str, Chart]
    composite: Chart | None
    synastry: list[SynastryAspect]
    tz: str

    @property
    def self_chart(self) -> Chart:
        return self.charts[self.bundle.self_profile.id]

    @property
    def partner_chart(self) -> Chart | None:
        partner = self.bundle.partner
        return self.charts[partner.id] if partner else None


def build_context(bundle: Bundle) -> Context:
    charts = {profile.id: build_chart(profile) for profile in bundle.profiles}
    self_chart = charts[bundle.self_profile.id]
    partner = bundle.partner
    partner_chart = charts[partner.id] if partner else None
    composite = (
        build_composite(self_chart, partner_chart)
        if partner_chart is not None
        and not self_chart.sign_only
        and not partner_chart.sign_only
        else None
    )
    synastry = (
        compute_synastry(self_chart, partner_chart)
        if partner_chart is not None
        else []
    )
    return Context(
        bundle=bundle,
        charts=charts,
        composite=composite,
        synastry=synastry,
        tz=bundle.self_profile.tz,
    )


def _collect_chart(
    chart: Chart,
    domain: str,
    tz: str,
    start: date,
    end: date,
    daily: bool,
    perspective: str = "self",
    pronoun: str = "m",
) -> list[Signal]:
    if daily:
        hits = (
            sign_hits_for_day(chart, start, tz)
            if chart.sign_only
            else hits_for_day(chart, start, tz)
        )
    else:
        hits = (
            sign_scan_period(chart, start, end, tz)
            if chart.sign_only
            else scan_period(chart, start, end, tz)
        )
    return rank(
        make_signals(
            hits,
            domain,
            chart.profile_id,
            perspective=perspective,
            pronoun=pronoun,
        ),
        limit=12,
    )


def collect_signals(
    context: Context, start: date, end: date, daily: bool = False
) -> dict[str, list[Signal]]:
    signals: dict[str, list[Signal]] = {
        "self": _collect_chart(
            context.self_chart,
            "self",
            context.tz,
            start,
            end,
            daily,
        )
    }
    partner = context.bundle.partner
    if partner is not None and context.partner_chart is not None:
        signals["partner"] = _collect_chart(
            context.partner_chart,
            "partner",
            context.tz,
            start,
            end,
            daily,
            perspective="other",
            pronoun=partner.pronoun,
        )
    if context.composite is not None:
        signals["relationship"] = _collect_chart(
            context.composite,
            "relationship",
            context.tz,
            start,
            end,
            daily,
            perspective="relationship",
        )
    for child in context.bundle.children:
        signals[f"child:{child.id}"] = _collect_chart(
            context.charts[child.id],
            f"child:{child.id}",
            context.tz,
            start,
            end,
            daily,
            perspective="other",
            pronoun=child.pronoun,
        )
    return signals


def _child_guidance(context: Context, on_day: date) -> dict[str, Any]:
    return {
        child.id: build_child_guidance(child, context.charts[child.id], on_day)
        for child in context.bundle.children
    }


def _moon_changes(context: Context, start: date, end: date) -> list[tuple[float, int, int]]:
    zone = ZoneInfo(context.tz)
    start_dt = datetime.combine(start, time(0, 0), tzinfo=zone)
    end_dt = datetime.combine(end + timedelta(days=1), time(0, 0), tzinfo=zone)
    return ephemeris.moon_sign_changes(
        ephemeris.to_jd(start_dt), ephemeris.to_jd(end_dt)
    )


def outputs_root(args: argparse.Namespace) -> Path:
    if getattr(args, "out", None):
        return Path(args.out)
    return Path(os.environ.get("ASTROMIND_OUT", "outputs"))


def state_path(args: argparse.Namespace) -> Path:
    if getattr(args, "no_state", False):
        return Path(os.environ.get("ASTROMIND_STATE", "state/state.json"))
    return Path(os.environ.get("ASTROMIND_STATE", "state/state.json"))


def writes_enabled(args: argparse.Namespace) -> bool:
    return not getattr(args, "no_state", False)


def parse_day(value: str | None, tz: str) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ProfileError(f"--date must be YYYY-MM-DD, got {value!r}") from exc
    return ephemeris.today_in_tz(tz)


def week_start(day: date) -> date:
    # Sunday-based week (Saudi convention).
    return day - timedelta(days=(day.weekday() + 1) % 7)


def month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    if start.month == 12:
        following = date(start.year + 1, 1, 1)
    else:
        following = date(start.year, start.month + 1, 1)
    return start, following - timedelta(days=1)


def write_report(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def rebuild_index(root: Path) -> None:
    current_names = {"today.md", "this_week.md", "this_month.md"}
    files = [
        path
        for path in root.rglob("*.md")
        if path.name not in {"index.md"} and not path.name.startswith(".")
    ]
    files.sort(
        key=lambda path: (
            0 if path.name in current_names else 1,
            -path.stat().st_mtime,
        )
    )
    entries: list[tuple[str, str]] = []
    seen_titles: set[str] = set()
    for path in files:
        title = path.stem
        try:
            with path.open(encoding="utf-8") as handle:
                first = handle.readline().strip()
            if first.startswith("# "):
                title = first[2:].strip()
        except OSError:
            pass
        if title in seen_titles:
            continue
        seen_titles.add(title)
        entries.append((title, path.relative_to(root).as_posix()))
    if (root / "calendar.ics").exists():
        entries.append(("تقويم النوافذ والتنبيهات (ICS)", "calendar.ics"))
    write_report(root, "index.md", build_index(entries))


def _state(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "no_state", False):
        return default_state()
    return load_state(state_path(args))


def _save_state(args: argparse.Namespace, state: dict[str, Any], today: date) -> None:
    if not writes_enabled(args):
        return
    prune(state, today)
    save_state(state_path(args), state)


def _apply_daily_filter(
    context: Context,
    signals: dict[str, list[Signal]],
    day: date,
    seen: dict[str, dict[str, float]],
) -> dict[str, list[Signal]]:
    filtered: dict[str, list[Signal]] = {}
    for domain, items in signals.items():
        candidates = changed_since(items, seen, day)
        filtered[domain] = rank(candidates, limit=8)
    return filtered


def _data(
    context: Context,
    signals: dict[str, list[Signal]],
    start: date,
    end: date,
    include_month_context: bool = False,
) -> ReportData:
    return ReportData(
        bundle=context.bundle,
        charts=context.charts,
        composite=context.composite,
        signals=signals,
        start=start,
        end=end,
        moon_changes=_moon_changes(context, start, end),
        synastry=context.synastry,
        child_guidance=_child_guidance(context, end),
    )


def _write_facts(
    context: Context,
    signals: dict[str, list[Signal]],
    start: date,
    root: Path,
) -> Path:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "month": start.strftime("%Y-%m"),
        "charts": {
            profile_id: chart_facts(chart)
            for profile_id, chart in context.charts.items()
        },
        "composite": chart_facts(context.composite) if context.composite else None,
        "signals": {
            domain: [
                {
                    "key": signal.key,
                    "transiting": signal.transiting,
                    "target": signal.target,
                    "aspect": signal.aspect,
                    "orb": signal.hit.orb,
                    "score": signal.score,
                    "polarity": signal.polarity,
                    "exact": signal.date.isoformat(),
                    "applying": signal.applying,
                    "line": signal.text.line,
                    "action": signal.text.action,
                    "avoid": signal.text.avoid,
                }
                for signal in items
            ]
            for domain, items in signals.items()
        },
        "synastry": [
            {
                "a": item.a_body,
                "b": item.b_body,
                "aspect": item.aspect,
                "orb": item.orb,
                "score": item.score,
                "polarity": item.polarity,
            }
            for item in context.synastry[:40]
        ],
    }
    path = root / "facts" / f"{start.strftime('%Y-%m')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_daily(args: argparse.Namespace, context: Context) -> int:
    day = parse_day(args.date, context.tz)
    signals = collect_signals(context, day, day, daily=True)
    state = _state(args)
    seen = state.get("seen", {})
    filtered = _apply_daily_filter(context, signals, day, seen)

    data = _data(context, filtered, day, day)
    root = outputs_root(args)
    text = build_daily(data)
    write_report(root, "today.md", text)
    write_report(root, f"{day:%Y-%m}/{day.isoformat()}_card.md", text)

    state["seen"] = mark_seen(seen, [item for items in filtered.values() for item in items], day)
    state.setdefault("last_run", {})["daily"] = day.isoformat()
    _save_state(args, state, day)
    rebuild_index(root)
    print(text)
    return 0


def cmd_weekly(args: argparse.Namespace, context: Context) -> int:
    anchor = parse_day(args.date, context.tz)
    start = week_start(anchor)
    end = start + timedelta(days=6)
    signals = collect_signals(context, start, end, daily=False)
    data = _data(context, signals, start, end)
    root = outputs_root(args)
    text = build_weekly(data)

    iso = start.isocalendar()
    label = f"{iso.year}-W{iso.week:02d}"
    write_report(root, "this_week.md", text)
    write_report(root, f"{start:%Y-%m}/{label}_week.md", text)

    state = _state(args)
    state["seen"] = mark_seen(
        state.get("seen", {}),
        [item for items in signals.values() for item in items[:3]],
        end,
    )
    state.setdefault("last_run", {})["weekly"] = end.isoformat()
    _save_state(args, state, end)
    _write_facts(context, signals, start, root)
    rebuild_index(root)
    print(text)
    return 0


def cmd_monthly(args: argparse.Namespace, context: Context) -> int:
    anchor = parse_day(args.date, context.tz)
    if args.month:
        try:
            year, month = (int(part) for part in args.month.split("-", 1))
            anchor = date(year, month, 1)
        except (ValueError, TypeError) as exc:
            raise ProfileError("--month must be YYYY-MM") from exc
    start, end = month_bounds(anchor)
    signals = collect_signals(context, start, end, daily=False)
    data = _data(context, signals, start, end)
    root = outputs_root(args)
    text = build_monthly(data)

    write_report(root, "this_month.md", text)
    write_report(root, f"relational/{start:%Y-%m}.md", text)
    write_report(root, f"{start:%Y-%m}/{start:%Y-%m}_month.md", text)

    state = _state(args)
    state["seen"] = mark_seen(
        state.get("seen", {}),
        [item for items in signals.values() for item in items[:4]],
        end,
    )
    state.setdefault("last_run", {})["monthly"] = start.strftime("%Y-%m")
    _save_state(args, state, end)
    _write_facts(context, signals, start, root)
    rebuild_index(root)
    print(text)
    return 0


def cmd_manuals(args: argparse.Namespace, context: Context) -> int:
    anchor = parse_day(args.date, context.tz)
    if args.month:
        try:
            year, month = (int(part) for part in args.month.split("-", 1))
            anchor = date(year, month, 1)
        except (ValueError, TypeError) as exc:
            raise ProfileError("--month must be YYYY-MM") from exc
    start, end = month_bounds(anchor)
    signals = collect_signals(context, start, end, daily=False)
    data = _data(context, signals, start, end)
    root = outputs_root(args)

    wrote = 0
    partner = context.bundle.partner
    if partner is not None:
        text = build_partner_manual(data)
        write_report(root, f"manuals/partner_{partner.id}.md", text)
        print(f"manual: {partner.name}")
        wrote += 1

    for child in context.bundle.children:
        guidance = data.child_guidance.get(child.id)
        if guidance is None:
            continue
        text = build_child_manual(data, child, guidance)
        write_report(root, f"manuals/child_{child.id}.md", text)
        print(f"manual: {child.name}")
        wrote += 1

    if wrote == 0:
        print("لا توجد بروفايلات شريكة أو أطفال بعد. أضفها إلى السر ثم أعد التشغيل.")
    rebuild_index(root)
    return 0


def cmd_calendar(args: argparse.Namespace, context: Context) -> int:
    day = parse_day(args.date, context.tz)
    if args.month:
        try:
            year, month = (int(part) for part in args.month.split("-", 1))
            day = date(year, month, 1)
        except (ValueError, TypeError) as exc:
            raise ProfileError("--month must be YYYY-MM") from exc
    start, end = month_bounds(day)
    signals = collect_signals(context, start, end, daily=False)
    data = _data(context, signals, start, end)
    root = outputs_root(args)
    text = build_calendar(data, start, end)
    path = write_report(root, "calendar.ics", text)
    print(f"wrote {path}")
    rebuild_index(root)
    return 0


def cmd_compute(args: argparse.Namespace, context: Context) -> int:
    day = parse_day(args.date, context.tz)
    start, end = month_bounds(day)
    signals = collect_signals(context, start, end, daily=False)
    root = outputs_root(args)
    path = _write_facts(context, signals, start, root)
    print(f"wrote {path}")
    return 0


def cmd_validate(args: argparse.Namespace, context: Context) -> int:
    print("الملفات المحمّلة:")
    print(context.bundle.summary())
    print("")
    print("الخرائط:")
    for profile in context.bundle.profiles:
        chart = context.charts[profile.id]
        if chart.sign_only:
            status = "أبراج فقط (بدون تاريخ/وقت ميلاد)"
        elif profile.birth is not None and not profile.birth.time_known:
            status = "تقريبية (وقت غير معلوم)"
        else:
            status = "كاملة" if chart.reliable else "تقريبية"
        print(
            f"- {profile.name}: {len(chart.positions)} نقطة، "
            f"{chart.house_system if chart.houses else 'بلا بيوت'} — {status}"
        )
    if context.composite:
        print("- خريطة العلاقة (Composite): متاحة")
    elif context.bundle.partner is not None:
        print("- خريطة العلاقة (Composite): غير متاحة في وضع الأبراج فقط")
    else:
        print("- خريطة العلاقة: غير متاحة (لا شريكة بعد)")
    if context.bundle.children:
        print(f"- أطفال: {len(context.bundle.children)}")
    return 0


def cmd_encode(args: argparse.Namespace, context: Context | None) -> int:
    if not args.file:
        raise ProfileError("encode requires --file")
    encoded = encode_file(args.file)
    print(encoded)
    print(
        "\nانسخ السطر أعلاه إلى GitHub Secret باسم ASTROMIND_PROFILES. "
        "لا تضعه في الكود أو في سجل عام.",
        file=sys.stderr,
    )
    return 0


def _normalize_ar(text: str) -> str:
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    return text


def _stem_ar(token: str) -> str:
    token = _normalize_ar(token)
    for prefix in ("وال", "بال", "كال", "لل", "ال"):
        if token.startswith(prefix) and len(token) > len(prefix) + 2:
            token = token[len(prefix):]
            break
    for suffix in ("كما", "ها", "هم", "هن", "ات", "ين", "ون", "ه", "ك", "ي"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            token = token[: -len(suffix)]
            break
    return token


def cmd_ask(args: argparse.Namespace, context: Context) -> int:
    question = " ".join(args.question).strip()
    if not question:
        raise ProfileError("ask requires a question")
    anchor = parse_day(None, context.tz)
    start = week_start(anchor)
    end = start + timedelta(days=6)
    signals = collect_signals(context, start, end, daily=False)
    flat = [item for items in signals.values() for item in items]
    raw_tokens = [
        token
        for token in question.replace("؟", " ").replace("،", " ").split()
        if len(token) > 2
    ]
    tokens = [_stem_ar(token) for token in raw_tokens if _stem_ar(token)]
    normalized_question = _normalize_ar(question)

    wants_children = any(word in normalized_question for word in ("طفل", "ابني", "بنتي", "الاطفال", "الاول", "الثاني"))
    wants_partner = any(word in normalized_question for word in ("شريك", "زوج", "زوجه", "هي", "علاق", "حب"))
    wants_self = any(word in normalized_question for word in ("انا", "نفسي", "طاقتي", "مزاجي"))

    def score(signal: Signal) -> int:
        haystack = _normalize_ar(
            " ".join(
                [
                    signal.text.title,
                    signal.text.line,
                    signal.text.action,
                    signal.text.avoid,
                    signal.target,
                    signal.transiting,
                ]
            )
        )
        value = sum(1 for token in tokens if token in haystack)
        if wants_children and signal.domain.startswith("child:"):
            value += 3
        if wants_partner and signal.domain in {"partner", "relationship"}:
            value += 2
        if wants_self and signal.domain == "self":
            value += 2
        return value

    ranked = sorted(flat, key=lambda item: (score(item), item.score), reverse=True)
    best = [item for item in ranked if score(item) > 0][:5] or ranked[:5]

    lines = [f"# سؤال سريع — {question}", ""]
    for item in best:
        lines.append(f"- **{item.text.title}** — {item.text.line}")
        lines.append(f"  - افعل: {item.text.action}")
        lines.append(f"  - تجنّب: {item.text.avoid}")
    lines.append("")
    lines.append("> إجابة مبنية على إشارات هذا الأسبوع. للحكم النهائي، راقب الواقع أولًا.")
    text = "\n".join(lines) + "\n"
    root = outputs_root(args)
    write_report(root, "ask.md", text)
    rebuild_index(root)
    print(text)
    return 0


def cmd_run_all(args: argparse.Namespace, context: Context) -> int:
    cmd_daily(args, context)
    cmd_weekly(args, context)
    cmd_monthly(args, context)
    cmd_manuals(args, context)
    cmd_calendar(args, context)
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", help="local profiles JSON (instead of the secret)")
    common.add_argument("--out", help="output directory (default: outputs)")
    common.add_argument(
        "--no-state",
        action="store_true",
        help="do not read/write state (all signals treated as new)",
    )
    common.add_argument("--date", help="YYYY-MM-DD (default: today in self timezone)")
    common.add_argument("--month", help="YYYY-MM for monthly/calendar")

    parser = argparse.ArgumentParser(
        prog="astromind",
        description="Multi-profile astrology engine: daily, weekly, monthly, synastry.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("daily", parents=[common], help="daily card").set_defaults(func=cmd_daily)
    sub.add_parser("weekly", parents=[common], help="weekly digest").set_defaults(func=cmd_weekly)
    sub.add_parser("monthly", parents=[common], help="monthly relational guide").set_defaults(func=cmd_monthly)
    sub.add_parser("manuals", parents=[common], help="generate relationship/child manuals").set_defaults(func=cmd_manuals)
    sub.add_parser("calendar", parents=[common], help="generate .ics calendar").set_defaults(func=cmd_calendar)
    sub.add_parser("compute", parents=[common], help="write raw facts JSON").set_defaults(func=cmd_compute)
    sub.add_parser("validate", parents=[common], help="validate profiles and show chart status").set_defaults(func=cmd_validate)
    sub.add_parser("encode", parents=[common], help="encode a local JSON file for GitHub Secrets").set_defaults(func=cmd_encode)
    ask_parser = sub.add_parser("ask", parents=[common], help="answer a specific question from this week's signals")
    ask_parser.add_argument("question", nargs="+")
    ask_parser.set_defaults(func=cmd_ask)
    sub.add_parser("run-all", parents=[common], help="daily + weekly + monthly + manuals + calendar").set_defaults(func=cmd_run_all)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "encode":
            return cmd_encode(args, None)
        bundle = load_bundle(args.file)
        context = build_context(bundle)
        return args.func(args, context)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
