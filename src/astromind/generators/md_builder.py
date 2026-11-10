"""Markdown report builders for daily, weekly, monthly, and manuals."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from astromind.engines.charts import Chart
from astromind.engines.child_development import ChildGuidance
from astromind.engines.classical import (
    build_life_domains,
    compute_lunation,
    compute_profection,
    compute_sect,
    split_eagle_and_lark,
)
from astromind.engines.ephemeris import from_jd
from astromind.engines.signals import Signal
from astromind.engines.synastry import (
    SynastryAspect,
    describe_aspect,
    element_compatibility,
    top_ease,
    top_friction,
)
from astromind.generators.interpretations import synastry_copy
from astromind.generators import interpretations
from astromind.i18n import (
    ASPECTS_AR,
    BODIES_AR,
    SIGNS_AR,
    element_ar,
    format_date,
    format_date_short,
    sign_element,
    sign_modality,
    modality_ar,
)
from astromind.models import Bundle, Profile

POSITIVE = {"support", "opportunity"}


@dataclass
class ReportData:
    bundle: Bundle
    charts: dict[str, Chart]
    composite: Chart | None
    signals: dict[str, list[Signal]]
    start: date
    end: date
    as_of: date | None = None
    moon_changes: list[tuple[float, int, int]] = field(default_factory=list)
    synastry: list[SynastryAspect] = field(default_factory=list)
    child_guidance: dict[str, ChildGuidance] = field(default_factory=dict)

    @property
    def tz(self) -> str:
        return self.bundle.self_profile.tz

    @property
    def self_chart(self) -> Chart:
        return self.charts[self.bundle.self_profile.id]

    @property
    def partner_chart(self) -> Chart | None:
        partner = self.bundle.partner
        return self.charts[partner.id] if partner else None


def _local(hit_jd: float, tz: str) -> datetime:
    return from_jd(hit_jd).astimezone(ZoneInfo(tz))


def _signal_compact(signal: Signal) -> str:
    return (
        f"- **{signal.text.title}** — {signal.text.line}\n"
        f"  - افعل: {signal.text.action}\n"
        f"  - تجنّب: {signal.text.avoid}"
    )


def _signal_short(signal: Signal) -> str:
    return f"- {signal.text.line} **افعل:** {signal.text.action} **تجنّب:** {signal.text.avoid}"


def _section(title: str, signals: list[Signal], empty: str) -> str:
    if not signals:
        return f"## {title}\n{empty}\n"
    body = "\n".join(_signal_compact(signal) for signal in signals)
    return f"## {title}\n{body}\n"


def _confidence_note(data: ReportData) -> str:
    sign_only = [
        profile.name for profile in data.bundle.profiles if profile.birth is None
    ]
    manual = [
        profile.name
        for profile in data.bundle.profiles
        if profile.birth is not None
        and profile.id in data.charts
        and data.charts[profile.id].sign_only
    ]
    unknown = [
        profile.name
        for profile in data.bundle.profiles
        if profile.birth is not None and not profile.birth.time_known
    ]
    no_houses = [
        data.bundle.by_id(profile_id).name
        for profile_id, chart in data.charts.items()
        if chart.role != "relationship" and chart.houses is None and profile_id in {p.id for p in data.bundle.profiles}
    ]
    if sign_only:
        note = (
            "ثقة القراءة: منخفضة — بيانات أبراج فقط لـ "
            + "، ".join(sign_only)
            + ". بدون تاريخ/وقت ميلاد لا يمكن حساب توقيت دقيق؛ "
            "التوجيه مبني على الأبراج والبيوت الكاملة فقط."
        )
        if unknown:
            note += " ويظل وقت الميلاد غير معروف لـ " + "، ".join(unknown) + "."
        return note
    if manual:
        note = (
            "ثقة القراءة: متوسطة — مواضع أبراج وبيوت مقدمة يدويًا لـ "
            + "، ".join(manual)
            + ". تاريخ الميلاد متوفر، لكن التوقيت اليومي مبني على مستوى الأبراج "
            "لأن الدرجات الدقيقة غير متاحة."
        )
        if unknown:
            note += " ووقت الميلاد غير مؤكد لـ " + "، ".join(unknown) + "."
        return note
    if unknown:
        return (
            "ثقة القراءة: متوسطة — وقت الميلاد غير محدد لـ "
            + "، ".join(unknown)
            + ". الطالع والبيوت غير محسوبين، وموضع القمر قد يكون تقريبيًا."
        )
    if no_houses:
        return (
            "ثقة القراءة: جيدة — تعذّر حساب البيوت لـ "
            + "، ".join(no_houses)
            + " (خطوط عرض عالية أو بيانات ناقصة)؛ النصائح مبنية على الكواكب فقط."
        )
    return "ثقة القراءة: عالية — بيانات الميلاد والوقت مكتملة."


def _windows(
    data: ReportData,
    positive: bool = True,
    limit: int = 5,
) -> list[str]:
    wanted = POSITIVE if positive else {"friction"}
    floor = data.as_of or data.start
    candidates = data.signals.get("relationship", [])
    if not candidates:
        candidates = data.signals.get("self", [])
    items = [
        signal
        for signal in candidates
        if signal.polarity in wanted
        and data.start <= signal.date <= data.end
        and signal.date >= floor
        and signal.transiting in {"moon", "venus", "mercury", "sun", "jupiter", "mars", "saturn"}
        and (not signal.hit.sign_level or signal.transiting == "moon")
    ]
    items = sorted(items, key=lambda item: (item.hit.exact_jd, -item.score))
    lines = []
    seen_slots: set[tuple[int, int, int, int]] = set()
    for signal in items:
        moment = _local(signal.hit.exact_jd, data.tz)
        if signal.hit.sign_level:
            slot = (moment.year, moment.month, moment.day, 99)
        else:
            slot = (moment.year, moment.month, moment.day, moment.hour)
        if slot in seen_slots:
            continue
        seen_slots.add(slot)
        verb = "نافذة" if positive else "احذر"
        if signal.hit.sign_level:
            lines.append(
                f"- {verb} {format_date_short(moment.date())} (طوال اليوم) — {signal.text.line}"
            )
        else:
            lines.append(
                f"- {verb} {format_date_short(moment.date())} {moment:%H:%M} — {signal.text.line}"
            )
        if len(lines) >= limit:
            break
    return lines


def _moon_line(data: ReportData) -> str:
    if not data.moon_changes:
        return "لا تغيّر في برج القمر خلال هذه الفترة."
    parts = []
    for jd, _from, to in data.moon_changes:
        moment = _local(jd, data.tz)
        parts.append(f"{format_date_short(moment.date())} {moment:%H:%M} → {SIGNS_AR[to]}")
    if len(parts) <= 4:
        return "تغيّرات القمر: " + "، ".join(parts)
    return "تغيّرات القمر:\n" + "\n".join(f"- {part}" for part in parts)


def _sign_summary(chart: Chart, body: str) -> str:
    position = chart.body(body)
    if position is None:
        return f"{BODIES_AR.get(body, body)}: غير متوفر"
    element = sign_element(position.sign)
    return (
        f"{BODIES_AR.get(body, body)} في {SIGNS_AR[position.sign]} "
        f"({element_ar(element)}, {modality_ar(sign_modality(position.sign))})"
    )


def _quick_facts(chart: Chart) -> str:
    rows = [
        _sign_summary(chart, "sun"),
        _sign_summary(chart, "moon"),
        _sign_summary(chart, "mercury"),
        _sign_summary(chart, "venus"),
        _sign_summary(chart, "mars"),
        _sign_summary(chart, "saturn"),
    ]
    if chart.houses:
        asc = chart.angles.get("asc")
        if asc is not None:
            rows.insert(0, f"الطالع في {SIGNS_AR[int(asc // 30) % 12]}")
    return "\n".join(f"- {row}" for row in rows)


def _domains_block(data: ReportData, anchor: date) -> list[str]:
    lunation = compute_lunation(anchor, data.tz)
    domains = build_life_domains(
        data.self_chart,
        data.signals,
        lunation,
        as_of=data.as_of or data.start,
    )
    out = [
        "## بوصلة النواحي الأربع",
        "| الناحية | المؤشر | الخلاصة العملية | خطوة سريعة |",
        "|---|---|---|---|",
    ]
    for item in domains:
        out.append(
            f"| **{item.title_ar}** | {item.badge_ar} ({item.score}%) | {item.headline} | {item.action} |"
        )
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------


def build_daily(data: ReportData) -> str:
    day = data.start
    self_signals = data.signals.get("self", [])
    partner_signals = data.signals.get("partner", [])
    relationship = data.signals.get("relationship", [])
    lunation = compute_lunation(day, data.tz)

    primary = self_signals[0] if self_signals else None
    lines = [f"# بطاقة اليوم — {format_date(day)}", ""]
    lines.append(
        f"**طور القمر اليوم (Rudhyar):** {lunation.name_ar} ({lunation.illumination}% إضاءة) — {lunation.rhythm_ar}"
    )
    lines.append("")
    if primary:
        lines.append(f"**الجو العام:** {primary.text.line}")
        lines.append("")
        lines.append(f"**افعل:** {primary.text.action}")
        lines.append(f"**تجنّب:** {primary.text.avoid}")
    else:
        lines.append("**الجو العام:** لا إشارة قوية اليوم؛ يوم مناسب للروتين والاستكمال.")
    lines.append("")

    lines.extend(_domains_block(data, day))

    if data.bundle.partner:
        if relationship:
            item = relationship[0]
            lines.append(f"**علاقيًا:** {item.text.line} — {item.text.action}")
        elif partner_signals:
            item = partner_signals[0]
            lines.append(
                f"**علاقيًا:** لا شيء جديد بينكما، لكن طقسها: {item.text.line}"
            )
        else:
            lines.append("**علاقيًا:** لا إشارة جديدة؛ لا تفتح ملفًا قديمًا اليوم.")
        lines.append("")

    children = data.bundle.children
    if children:
        child_lines = []
        for child in children:
            signals = data.signals.get(f"child:{child.id}", [])
            if signals:
                item = signals[0]
                child_lines.append(f"- {child.name}: {item.text.line} — {item.text.action}")
            else:
                child_lines.append(
                    f"- {child.name}: لا إشارة قوية؛ حافظ على الروتين ووقت الحضور."
                )
        lines.append("**مع الأطفال:**")
        lines.extend(child_lines)
        lines.append("")

    windows = _windows(data, positive=True, limit=1)
    cautions = _windows(data, positive=False, limit=1)
    if windows:
        lines.append(f"**نافذة اليوم:** {windows[0][2:]}")
    if cautions:
        lines.append(f"**احذر:** {cautions[0][2:]}")
    if not windows and not cautions:
        lines.append("**التوقيت:** لا نافذة حرجة؛ اختر أنت وقتًا هادئًا.")
    lines.append("")
    lines.append(f"> {_confidence_note(data)}")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------


def build_weekly(data: ReportData) -> str:
    start, end = data.start, data.end
    anchor = data.as_of or start
    lunation = compute_lunation(anchor, data.tz)
    eagle, lark = split_eagle_and_lark(data.signals.get("self", []))

    title = f"# موجز الأسبوع — {format_date_short(start)} إلى {format_date_short(end)} {end.year}"
    lines = [title, ""]
    lines.append(f"**القمر هذا الأسبوع:** {_moon_line(data)}")
    lines.append(
        f"**إيقاع الدورة القمرية:** {lunation.name_ar} — {lunation.rhythm_ar}"
    )
    if eagle or lark:
        eagle_txt = eagle[0].text.line if eagle else "ثبات في الإيقاع الهيكلي العام."
        lark_txt = lark[0].text.line if lark else "حركة يومية خفيفة تدعم الإنجاز المتدرج."
        lines.append(
            f"**عدسة النسر والقبرة (Brady):** النسر (الاتجاه الأوسع): {eagle_txt} · القبرة (النبض اليومي): {lark_txt}"
        )
    lines.append("")

    lines.extend(_domains_block(data, anchor))

    lines.append(_section("طقسك الشخصي", data.signals.get("self", [])[:3], "لا إشارات قوية؛ أسبوع روتين واستكمال."))
    if data.bundle.partner:
        lines.append(
            _section(
                "ما تمر به الشريكة (طقسها)",
                data.signals.get("partner", [])[:2],
                "لا إشارات بارزة؛ لا تفسّر الهدوء كإشارة.",
            )
        )
        lines.append(
            _section(
                "بينكما (طقس العلاقة)",
                data.signals.get("relationship", [])[:3],
                "لا احتكاك بارز؛ استثمر الأسبوع في وقت مشترك بسيط.",
            )
        )

    for child in data.bundle.children:
        lines.append(
            _section(
                f"مع {child.name}",
                data.signals.get(f"child:{child.id}", [])[:2],
                "لا إشارة قوية؛ حافظ على الروتين والاحتواء.",
            )
        )

    lines.append("## تقويم الأسبوع")
    lines.append("| اليوم | أهم إشارة شخصية | إشارة علاقة |")
    lines.append("|---|---|---|")
    day = max(start, data.as_of or start)
    while day <= end:
        self_today = [
            signal for signal in data.signals.get("self", []) if signal.date == day
        ]
        rel_today = [
            signal
            for signal in data.signals.get("relationship", [])
            if signal.date == day
        ]
        self_text = self_today[0].text.title if self_today else "—"
        rel_text = rel_today[0].text.title if rel_today else "—"
        lines.append(f"| {format_date_short(day)} | {self_text} | {rel_text} |")
        day = date.fromordinal(day.toordinal() + 1)
    lines.append("")

    windows = _windows(data, positive=True, limit=4)
    cautions = _windows(data, positive=False, limit=4)
    if windows:
        lines.append("## نوافذ التواصل")
        lines.extend(windows)
        lines.append("")
    if cautions:
        lines.append("## احذر")
        lines.extend(cautions)
        lines.append("")
    if not windows and not cautions:
        lines.append("## تنبيهات")
        lines.append("- لا نوافذ أو تحذيرات متبقية في هذه الفترة.")
        lines.append("")

    lines.append("## قرار واحد هذا الأسبوع")
    candidate = next(
        (signal for signal in data.signals.get("self", []) if signal.polarity == "friction"),
        None,
    )
    if candidate:
        lines.append(f"- {candidate.text.action}")
    else:
        lines.append("- اختر موضوعًا واحدًا مؤجلًا وأنجزه في نافذة هادئة.")
    lines.append("")
    lines.append(f"> {_confidence_note(data)}")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Monthly
# ---------------------------------------------------------------------------


def build_monthly(data: ReportData) -> str:
    anchor = data.as_of or data.start
    sect = compute_sect(data.self_chart, data.bundle.self_profile)
    profection = compute_profection(data.self_chart, data.bundle.self_profile, anchor)

    lines = [
        f"# الدليل الشهري — {format_date_short(data.start)} إلى {format_date_short(data.end)} {data.end.year}",
        "",
    ]
    lines.append(f"**القمر خلال الشهر:** {_moon_line(data)}")
    lines.append("")
    lines.append("## الجذور الكلاسيكية للشهر")
    lines.append(f"- **الحيز الفلكي (George & Brennan):** {sect.summary_ar}")
    lines.append(f"- **انتهاء السنة وحاكم الزمن (Valens):** {profection.summary_ar}")
    lines.append("")

    lines.extend(_domains_block(data, anchor))

    lines.append(_section("الخط العام للشهر", data.signals.get("self", [])[:4], "شهر هادئ نسبيًا؛ راجع أولوياتك."))

    if data.bundle.partner:
        partner = data.bundle.partner
        partner_chart = data.partner_chart
        self_chart = data.self_chart
        lines.append(f"## العلاقة مع {partner.name}")
        if partner_chart:
            lines.append(f"- {element_compatibility(self_chart, partner_chart)}")
        lines.append("")
        lines.append(
            _section(
                "ما تمر به هي",
                data.signals.get("partner", [])[:3],
                "لا إشارات بارزة هذا الشهر.",
            )
        )
        lines.append(
            _section(
                "ديناميكيات العلاقة",
                data.signals.get("relationship", [])[:4],
                "لا احتكاك بارز؛ الشهر مناسب لتثبيت روتين مشترك.",
            )
        )
        if data.synastry:
            lines.append("### خريطة التقاطع الثابتة")
            lines.append("**نقاط سهولة:**")
            for aspect in top_ease(data.synastry, 3):
                copy = synastry_copy(
                    aspect.a_body, aspect.b_body, aspect.aspect, aspect.polarity,
                    self_chart.name, partner.name,
                )
                lines.append(f"- {copy.line} — {copy.action}")
            lines.append("")
            lines.append("**نقاط احتكاك:**")
            for aspect in top_friction(data.synastry, 3):
                copy = synastry_copy(
                    aspect.a_body, aspect.b_body, aspect.aspect, aspect.polarity,
                    self_chart.name, partner.name,
                )
                lines.append(f"- {copy.line} — {copy.action}")
            lines.append("")

    for child in data.bundle.children:
        guidance = data.child_guidance.get(child.id)
        lines.append(f"## دعم {child.name}")
        if guidance:
            age_text = (
                f"{guidance.age} سنة" if guidance.age is not None else "غير متاح"
            )
            lines.append(f"- **العمر:** {age_text}")
            lines.append(f"- **نمط التعلم:** {guidance.learning}")
            lines.append(f"- **الأمان العاطفي:** {guidance.security}")
            lines.append(f"- **تفريغ الطاقة:** {guidance.energy}")
            lines.append(f"- **الموهبة:** {guidance.talent}")
            lines.append(f"- **حسب العمر:** {guidance.age_note}")
        focus = data.signals.get(f"child:{child.id}", [])[:3]
        if focus:
            lines.append("- **إشارات الشهر:**")
            lines.extend(f"  - {_signal_short(item)[2:]}" for item in focus)
        lines.append("")

    windows = _windows(data, positive=True, limit=6)
    cautions = _windows(data, positive=False, limit=6)
    if windows:
        lines.append("## نوافذ الشهر")
        lines.extend(windows)
        lines.append("")
    else:
        lines.append("## نوافذ الشهر")
        lines.append("- لا نوافذ إيجابية متبقية في هذه الفترة.")
        lines.append("")
    if cautions:
        lines.append("## تواريخ تحتاج هدوءًا")
        lines.extend(cautions)
        lines.append("")
    else:
        lines.append("## تواريخ تحتاج هدوءًا")
        lines.append("- لا تواريخ حرجة متبقية في هذه الفترة.")
        lines.append("")

    lines.append("## توصية الشهر")
    primary = data.signals.get("self", [None])[0]
    if primary:
        lines.append(f"- {primary.text.action}")
    else:
        lines.append("- اختر مشروعًا واحدًا صغيرًا وأنجزه قبل نهاية الشهر.")
    lines.append("")
    lines.append(f"> {_confidence_note(data)}")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Manuals
# ---------------------------------------------------------------------------


READY_PHRASES = (
    "أحتاج 10 دقائق أسمعك فيها قبل أن أقترح حلًا.",
    "ما الذي يريحك الآن: كلام أم مساحة؟",
    "أنا لست غاضبًا منك، أنا متعب؛ أحتاج وقتًا ثم نكمل.",
    "هل تفضل أن نتكلم الآن أم بعد العشاء؟",
    "ما الشيء الصغير الذي لو فعلته اليوم شعرت أنك مسموع؟",
)

RELATIONSHIP_DO = (
    "اسأل قبل أن تحلّل.",
    "ثبّت وعدًا صغيرًا ونفّذه.",
    "افتح موضوعًا واحدًا في الجلسة.",
    "سمِّ شعورك بدل أن تشرحه.",
)

RELATIONSHIP_DONT = (
    "لا تفتح ملفات قديمة في نفس الجلسة.",
    "لا تستخدم الصمت عقابًا.",
    "لا تحلل مشاعرها بدل أن تسمعها.",
    "لا تتخذ قرارًا دائمًا في ذروة الانفعال.",
)

CHILD_PHRASES = (
    "أراك تحاول، هذا ما يهمني.",
    "خذ وقتك، أنا هنا.",
    "ما رأيك أن نجرب خطوة واحدة فقط؟",
    "شكرًا لأنك أخبرتني.",
)


def build_partner_manual(data: ReportData) -> str:
    partner = data.bundle.partner
    if partner is None or data.partner_chart is None:
        return "# لا توجد بيانات شريكة بعد\nأضف ملفًا بدور `partner` في الأسرار لتفعيل هذا الدليل.\n"

    self_chart = data.self_chart
    partner_chart = data.partner_chart
    lines = [
        f"# دليل التعامل — {partner.name}",
        "",
        "## البطاقة السريعة",
        _quick_facts(partner_chart),
        "",
        "## كيف تتواصلان",
        *interpretations.communication_protocol(self_chart, partner_chart),
        "",
        "## الاحتياجات العاطفية",
        *interpretations.moon_protocol(self_chart, partner_chart),
        "",
        "## التقدير والقرب",
        *interpretations.venus_protocol(self_chart, partner_chart),
        "",
        "## وقت الخلاف",
        *interpretations.mars_protocol(self_chart, partner_chart),
        "",
        "## ما يبدو تهديدًا",
        *interpretations.saturn_protocol(partner_chart),
        "",
    ]

    lines.append("## خريطة التقاطع")
    lines.append(f"- {element_compatibility(self_chart, partner_chart)}")
    lines.append("")
    lines.append("### نقاط سهولة (استثمرها)")
    for aspect in top_ease(data.synastry, 5):
        copy = synastry_copy(
            aspect.a_body, aspect.b_body, aspect.aspect, aspect.polarity,
            self_chart.name, partner.name,
        )
        lines.append(f"- {copy.line} — {copy.action}")
    lines.append("")
    lines.append("### نقاط احتكاك (اسمعها قبل أن تتفاقم)")
    for aspect in top_friction(data.synastry, 5):
        copy = synastry_copy(
            aspect.a_body, aspect.b_body, aspect.aspect, aspect.polarity,
            self_chart.name, partner.name,
        )
        lines.append(f"- {copy.line} — {copy.action}")
    lines.append("")

    lines.append("## صيغ جاهزة")
    lines.extend(f"- «{phrase}»" for phrase in READY_PHRASES)
    lines.append("")
    lines.append("## افعل")
    lines.extend(f"- {item}" for item in RELATIONSHIP_DO)
    lines.append("")
    lines.append("## لا تفعل")
    lines.extend(f"- {item}" for item in RELATIONSHIP_DONT)
    lines.append("")
    lines.append(f"> {_confidence_note(data)}")
    return "\n".join(lines).strip() + "\n"


def build_child_manual(
    data: ReportData, profile: Profile, guidance: ChildGuidance
) -> str:
    chart = data.charts[profile.id]
    lines = [
        f"# دليل دعم — {profile.name}",
        "",
        "**العمر الحالي:** "
        + (f"{guidance.age} سنة" if guidance.age is not None else "غير متاح"),
        "",
        "## البطاقة السريعة",
        _quick_facts(chart),
        "",
        "## نمط التعلم",
        guidance.learning,
        "",
        "## الأمان العاطفي",
        guidance.security,
        "",
        "## تفريغ الطاقة",
        guidance.energy,
        "",
        "## الموهبة والاهتمام",
        guidance.talent,
        "",
        "## حسب العمر",
        guidance.age_note,
        "",
        "## ثلاث خطوات عملية",
        *(f"- {item}" for item in guidance.support_actions),
        "",
        "## تجنّب",
        *(f"- {item}" for item in guidance.avoid),
        "",
        "## صيغ جاهزة",
        *(f"- «{phrase}»" for phrase in CHILD_PHRASES),
        "",
        "> الخريطة عدسة ثانية، لا حكم نهائي. راقب السلوك أولًا، واستخدم الدليل لفهم الاحتياج لا لتسمية الطفل.",
    ]
    return "\n".join(lines).strip() + "\n"


def build_index(entries: list[tuple[str, str]]) -> str:
    lines = ["# فهرس التقارير", ""]
    for title, path in entries:
        lines.append(f"- [{title}]({path})")
    lines.append("")
    lines.append("> الملفات تُحدَّث تلقائيًا. ابدأ دائمًا بـ `today.md`.")
    return "\n".join(lines) + "\n"
