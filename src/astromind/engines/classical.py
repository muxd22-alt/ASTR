"""Classical, Hellenistic, Lunation, and Life-Domain synthesis engine.

Grounded in foundational astrological works:
1. Astrology and the Authentic Self — Demetra George
2. Astrology of Fate — Liz Greene
3. The Anthology — Vettius Valens (tr. Mark Riley)
4. Horoscope Symbols — Robert Hand
5. A Tiny Universe's Companion — Joy Usher
6. Hellenistic Astrology — Chris Brennan
7. The Lunation Cycle — Dane Rudhyar
8. Predictive Astrology: The Eagle and the Lark — Bernadette Brady
9. The Complete Astrological Writings — Aleister Crowley
10. Ancient Astrology in Theory and Practice Vol. 1 & 2 — Demetra George
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from astromind.engines import ephemeris
from astromind.engines.charts import Chart
from astromind.engines.signals import Signal
from astromind.i18n import (
    BODIES_AR,
    SIGNS_AR,
    element_ar,
    sign_element,
    sign_of,
)
from astromind.models import Profile

# Traditional domicile rulers (Hellenistic / Valens / Brennan / George)
SIGN_RULERS: tuple[str, ...] = (
    "mars",     # 0 Aries
    "venus",    # 1 Taurus
    "mercury",  # 2 Gemini
    "moon",     # 3 Cancer
    "sun",      # 4 Leo
    "mercury",  # 5 Virgo
    "venus",    # 6 Libra
    "mars",     # 7 Scorpio
    "jupiter",  # 8 Sagittarius
    "saturn",   # 9 Capricorn
    "saturn",   # 10 Aquarius
    "jupiter",  # 11 Pisces
)

EXALTATION_SIGNS: dict[str, int] = {
    "sun": 0,      # Aries
    "moon": 1,     # Taurus
    "mercury": 5,  # Virgo
    "venus": 11,   # Pisces
    "mars": 9,     # Capricorn
    "jupiter": 3,  # Cancer
    "saturn": 6,   # Libra
}

HOUSE_TOPICS_AR: dict[int, tuple[str, str]] = {
    1: ("الهوية والحيوية", "المبادرة الشخصية، الحضور الجسدي، وبداية المسارات الجديدة"),
    2: ("المال والموارد", "الدخل، الأمان المالي، ترتيب الأولويات المادية، وما تملكه فعليًا"),
    3: ("التواصل والتعلم", "الحوار اليومي، العقود القصيرة، الكتابة، والتنقل الذهني"),
    4: ("البيت والجذور", "الاستقرار العائلي، السكن، الأمان النفسي العميق، وترميم الداخل"),
    5: ("الإبداع والأطفال", "البهجة، المشاريع الإبداعية، الحضور مع الأطفال، والتعبير العفوي"),
    6: ("العمل والصحة", "الروتين اليومي، جودة الإنجاز، العادات الجسدية، وتنظيم الوقت"),
    7: ("الشراكة والعلاقات", "العلاقة الزوجية، العقود المشتركة، التفاوض، ومرآة الطرف الآخر"),
    8: ("الموارد المشتركة والتحول", "الالتزامات المالية المشتركة، الثقة العميقة، والتخلي عما استُهلك"),
    9: ("المعنى والأفق البعيد", "التخطيط بعيد المدى، المعرفة العليا، السفر، وتوسيع الرؤية"),
    10: ("المهنة والمكانة", "السمعة المهنية، القيادة، القرارات الكبرى، والأثر العام"),
    11: ("المستقبل والتحالفات", "شبكة العلاقات الداعمة، الأهداف طويلة الأمد، والعمل الجماعي"),
    12: ("الخلوت والتشافي", "الراحة العميقة، تصفية الذهن، إغلاق الملفات القديمة، والحدس"),
}


@dataclass(frozen=True)
class LunationPhase:
    index: int
    key: str
    name_ar: str
    angle: float
    illumination: int
    rhythm_ar: str
    work_tip: str
    relation_tip: str
    energy_tip: str


@dataclass(frozen=True)
class SectProfile:
    is_diurnal: bool
    label_ar: str
    sect_light: str
    benefic_leader: str
    constructive_malefic: str
    summary_ar: str


@dataclass(frozen=True)
class ProfectionYear:
    age: int | None
    house: int
    sign: int
    time_lord: str
    topic_title: str
    topic_detail: str
    summary_ar: str


@dataclass(frozen=True)
class DomainInsight:
    key: str
    title_ar: str
    color_hex: str
    score: int
    badge_ar: str
    headline: str
    action: str
    avoid: str


@dataclass(frozen=True)
class BookPillar:
    title_en: str
    author_en: str
    concept_ar: str
    personal_insight_ar: str
    color_hex: str


LUNATION_TABLE: tuple[tuple[str, str, str, str, str, str], ...] = (
    (
        "new",
        "المحاق الوليد — طور البذرة",
        "بداية دورة جديدة؛ الطاقة تتجه للداخل لتحديد النية قبل الظهور.",
        "ضع نية مشروع واحد أو أولوية واحدة دون استعجال التنفيذ الكامل.",
        "استمع أكثر مما تشرح؛ القرب اليوم يحتاج هدوءًا لا وعودًا كبيرة.",
        "خفّف المنبهات، وامنح جسدك نومًا مبكرًا لتجديد المخزون.",
    ),
    (
        "crescent",
        "الهلال المتصاعد — طور التثبيت",
        "الطاقة تبدأ بالتحرك وتطلب كسر التردد القديم بخطوة ملموسة.",
        "اختر مهمة صغيرة قابلة للإنجاز خلال ساعة لتثبيت الزخم.",
        "شارك الطرف الآخر خطوة عملية بسيطة بدل فتح نقاش نظري طويل.",
        "حركة خفيفة أو مشي قصير يحرر التردد ويصفّي الذهن.",
    ),
    (
        "first_quarter",
        "التربيع الأول — طور حسم الفعل",
        "لحظة قرار عملي وتجاوز عقبة صغيرة لبناء هيكل واضح (Rudhyar).",
        "احسم أمرًا معلقًا في العمل أو المال؛ القرار الواضح ينهي الاستنزاف.",
        "ضع حدودًا لطيفة وواضحة، ولا تترك التوقعات غير معلنة.",
        "فرّغ التوتر الحركي بالنشاط البدني قبل جلسات التفاوض.",
    ),
    (
        "gibbous",
        "الأحدب المتزايد — طور الصقل",
        "مرحلة مراجعة التفاصيل وتجويد العمل قبل اكتمال النتيجة.",
        "راجع الأرقام والعقود والتفاصيل الدقيقة؛ الصقل الآن يضاعف العائد.",
        "اسأل: «ما الذي يجعل يومنا أسهل؟» وركّز على التحسين الصغير.",
        "تجنب السهر المفرط بدافع الكمال؛ حدّد ساعة توقف واضحة.",
    ),
    (
        "full",
        "البدر المكتمل — طور الإشراق والمرآة",
        "ذروة الوضوح؛ الحقائق والنتائج تظهر للعلن والعلاقات تعمل كمرآة.",
        "اعرض نتائج عملك أو اختتم صفقة ناضجة، وتجنب القرارات الانفعالية.",
        "الاحتياج العاطفي في ذروته؛ قدّم التقدير الصريح وتجنب الجدال الحاد.",
        "الطاقة عالية وقد تسبب أرقًا؛ هدّئ الإيقاع المسائي بعيدًا عن الشاشات.",
    ),
    (
        "disseminating",
        "الأحدب المتناقص — طور المشاركة",
        "مرحلة حصاد الخبرة وتحويل الفهم إلى تواصل مثمر وتنظيم هادئ.",
        "شارك ما أنجزته مع فريقك أو عائلتك، ورتّب خطوات المتابعة.",
        "وقت ممتاز لحوار دافئ يبني الفهم المتبادل دون ضغط.",
        "حافظ على وتيرة معتدلة؛ لا تبدأ التزامًا ضخمًا جديدًا اليوم.",
    ),
    (
        "last_quarter",
        "التربيع الأخير — طور إعادة التوجيه",
        "مفترق مراجعة الأولويات والتخلي عما لم يعد يخدم مسارك.",
        "أغلق مهمة مستنزفة أو قلّص بندًا ماليًا غير ضروري.",
        "لا تفتح عتابًا قديمًا؛ ركّز على تعديل القاعدة للمستقبل.",
        "نظّف مساحتك الشخصية ومكتبك لتخفيف العبء الذهني.",
    ),
    (
        "balsamic",
        "الهلال البلسمي — طور التصفية والكمون",
        "ختام الدورة القمرية؛ الحكمة في التهدئة وإغلاق الملفات المفتوحة.",
        "أنهِ الأعمال الروتينية المؤجلة، وأجّل الإطلاق الكبير لبداية الدورة القادمة.",
        "امنح نفسك وشريكك مساحة صامتة مريحة دون تفسير الصمت كجفاء.",
        "أولوية قصوى للراحة والتأمل وتفريغ الذهن من الضجيج.",
    ),
)


def compute_lunation(day: date, tz_name: str = "Asia/Riyadh") -> LunationPhase:
    """Compute Dane Rudhyar's 8-phase Soli-Lunar cycle for the given date."""
    jd = ephemeris.local_noon_jd(day, tz_name)
    sun = ephemeris.calc_body(jd, "sun")
    moon = ephemeris.calc_body(jd, "moon")
    if sun is None or moon is None:
        angle = 0.0
    else:
        angle = (moon.longitude - sun.longitude) % 360.0

    index = int(angle // 45.0) % 8
    # Approximate illumination percentage from elongation angle
    import math

    illum = int(round(((1.0 - math.cos(math.radians(angle))) / 2.0) * 100))
    key, name_ar, rhythm_ar, work_tip, relation_tip, energy_tip = LUNATION_TABLE[index]
    return LunationPhase(
        index=index,
        key=key,
        name_ar=name_ar,
        angle=round(angle, 1),
        illumination=illum,
        rhythm_ar=rhythm_ar,
        work_tip=work_tip,
        relation_tip=relation_tip,
        energy_tip=energy_tip,
    )


def compute_sect(chart: Chart, profile: Profile) -> SectProfile:
    """Compute Hellenistic Sect (Diurnal vs Nocturnal) per Brennan & George."""
    is_diurnal = True
    sun_house = profile.houses.get("sun")
    if sun_house is not None:
        is_diurnal = sun_house >= 7
    elif "asc" in chart.angles and "sun" in chart.positions:
        asc = chart.angles["asc"]
        sun_lon = chart.positions["sun"].longitude
        # Above horizon means between DSC (asc+180) and ASC going through MC:
        # In zodiacal longitude, houses 7..12 span from (asc + 180) to asc (mod 360).
        rel = (sun_lon - asc) % 360.0
        is_diurnal = rel >= 180.0
    elif profile.birth is not None and profile.birth.time_known:
        hour = profile.birth.local_dt().hour
        is_diurnal = 6 <= hour < 18

    if is_diurnal:
        return SectProfile(
            is_diurnal=True,
            label_ar="خريطة نهارية (Diurnal Sect)",
            sect_light="sun",
            benefic_leader="jupiter",
            constructive_malefic="saturn",
            summary_ar=(
                "خريطتك نهارية: الوضوح، الهيكلة، والتخطيط بعيد المدى (المشتري وزحل) "
                "هي مفاتيح اتزانك؛ تنجح حين تحوّل الرؤية إلى نظام عملي واضح."
            ),
        )
    return SectProfile(
        is_diurnal=False,
        label_ar="خريطة ليلية (Nocturnal Sect)",
        sect_light="moon",
        benefic_leader="venus",
        constructive_malefic="mars",
        summary_ar=(
            "خريطتك ليلية: الحدس العاطفي، جودة الروابط، والشجاعة الغريزية (القمر والزهرة) "
            "هي مصدر قوتك؛ تنجح حين تثق بإحساسك الأول وتحمي مساحتك الآمنة."
        ),
    )


def compute_profection(chart: Chart, profile: Profile, on_day: date) -> ProfectionYear:
    """Compute Annual Profection House and Time-Lord of the Year (Valens & Brennan)."""
    asc_lon = chart.angles.get("asc")
    if asc_lon is not None:
        asc_sign = sign_of(asc_lon)
    elif "asc" in profile.signs:
        asc_sign = profile.signs["asc"] % 12
    elif "sun" in chart.positions:
        asc_sign = chart.positions["sun"].sign
    else:
        asc_sign = 0

    age: int | None = None
    if profile.birth is not None:
        born = date.fromisoformat(profile.birth.date)
        years = on_day.year - born.year - (
            (on_day.month, on_day.day) < (born.month, born.day)
        )
        if years >= 0:
            age = years

    house = ((age % 12) + 1) if age is not None else 1
    profected_sign = (asc_sign + house - 1) % 12
    time_lord = SIGN_RULERS[profected_sign]
    topic_title, topic_detail = HOUSE_TOPICS_AR[house]
    lord_ar = BODIES_AR.get(time_lord, time_lord)
    sign_ar = SIGNS_AR[profected_sign]

    if age is not None:
        summary = (
            f"سنة البيت {house} ({topic_title}) في برج {sign_ar} — "
            f"حاكم سنتك الفلكية هو **{lord_ar}**: التركيز الأعمق هذا العام يدور حول {topic_detail}."
        )
    else:
        summary = (
            f"الحاكم الموجه للخريطة هو **{lord_ar}** ({topic_title}): "
            f"المحور الأساسي يرتكز على {topic_detail}."
        )

    return ProfectionYear(
        age=age,
        house=house,
        sign=profected_sign,
        time_lord=time_lord,
        topic_title=topic_title,
        topic_detail=topic_detail,
        summary_ar=summary,
    )


def compute_lots(chart: Chart, sect: SectProfile) -> dict[str, dict[str, object]]:
    """Compute Hellenistic Lot of Fortune and Lot of Spirit when Ascendant is known."""
    if "asc" not in chart.angles or "sun" not in chart.positions or "moon" not in chart.positions:
        return {}
    asc = chart.angles["asc"]
    sun = chart.positions["sun"].longitude
    moon = chart.positions["moon"].longitude
    if sect.is_diurnal:
        fortune = (asc + moon - sun) % 360.0
        spirit = (asc + sun - moon) % 360.0
    else:
        fortune = (asc + sun - moon) % 360.0
        spirit = (asc + moon - sun) % 360.0

    f_sign = sign_of(fortune)
    s_sign = sign_of(spirit)
    return {
        "fortune": {
            "name_ar": "سهم السعادة (Lot of Fortune)",
            "sign_ar": SIGNS_AR[f_sign],
            "ruler_ar": BODIES_AR[SIGN_RULERS[f_sign]],
            "meaning_ar": "مجرى الرزق والظروف المادية والحيوية الجسدية",
        },
        "spirit": {
            "name_ar": "سهم الروح (Lot of Spirit)",
            "sign_ar": SIGNS_AR[s_sign],
            "ruler_ar": BODIES_AR[SIGN_RULERS[s_sign]],
            "meaning_ar": "القصد الواعي، المسار المهني، وما تختاره بإرادتك",
        },
    }


def split_eagle_and_lark(signals: list[Signal]) -> tuple[list[Signal], list[Signal]]:
    """Separate macro destiny cycles (Eagle) from daily rhythmic transits (Lark) per Bernadette Brady."""
    eagle_planets = {"jupiter", "saturn", "uranus", "neptune", "pluto", "node"}
    lark_planets = {"moon", "sun", "mercury", "venus", "mars"}
    eagle = [s for s in signals if s.transiting in eagle_planets]
    lark = [s for s in signals if s.transiting in lark_planets]
    return eagle, lark


def build_life_domains(
    chart: Chart,
    signals: dict[str, list[Signal]],
    lunation: LunationPhase,
    as_of: date | None = None,
) -> list[DomainInsight]:
    """Synthesize light, high-utility daily/weekly/monthly guidance across 4 core life domains."""
    self_signals = [
        s for s in signals.get("self", []) if as_of is None or s.date >= as_of
    ]
    rel_signals = [
        s
        for s in (signals.get("relationship", []) + signals.get("partner", []))
        if as_of is None or s.date >= as_of
    ]

    used_keys: set[str] = set()

    def _pick(pool: list[Signal], bodies: set[str]) -> Signal | None:
        # First try matching target planet unused
        for item in pool:
            if item.key not in used_keys and item.target in bodies:
                used_keys.add(item.key)
                return item
        # Then try matching transiting planet unused
        for item in pool:
            if item.key not in used_keys and item.transiting in bodies:
                used_keys.add(item.key)
                return item
        # Then any unused signal
        for item in pool:
            if item.key not in used_keys:
                used_keys.add(item.key)
                return item
        return None

    def _score_from(sig: Signal | None, base: int) -> tuple[int, str]:
        if sig is None:
            return base, "إيقاع متزن"
        if sig.polarity == "opportunity":
            return min(96, base + 16), "نافذة مفتوحة"
        if sig.polarity == "support":
            return min(92, base + 12), "تدفق داعم"
        if sig.polarity == "friction":
            return max(48, base - 12), "يتطلب تروّيًا"
        return base, "ملاحظة واعية"

    # 1. Career, Vocation & Decision (Crowley True Will / Hand / Brady)
    work_sig = _pick(self_signals, {"sun", "saturn", "mars", "mc", "mercury"})
    work_score, work_badge = _score_from(work_sig, 78)
    work_domain = DomainInsight(
        key="work",
        title_ar="العمل والقرار",
        color_hex="#FF9F0A",  # Apple System Orange
        score=work_score,
        badge_ar=work_badge,
        headline=work_sig.text.line if work_sig else lunation.work_tip,
        action=work_sig.text.action if work_sig else lunation.work_tip,
        avoid=work_sig.text.avoid if work_sig else "لا تشتت جهدك في أكثر من أولوية واحدة.",
    )

    # 2. Money, Resources & Practical Grounding (Valens / George / Usher)
    money_sig = _pick(self_signals, {"jupiter", "venus", "saturn", "mercury"})
    money_score, money_badge = _score_from(money_sig, 80)
    money_headline = (
        f"إيقاع الموارد ({lunation.name_ar.split('—')[0].strip()}): {lunation.work_tip}"
        if money_sig is None or money_sig == work_sig
        else money_sig.text.line
    )
    money_action = (
        "راجع التزامًا ماليًا واحدًا وثبّت خطوة عملية واضحة تضيف أمانًا ملموسًا."
        if money_sig is None or money_sig == work_sig
        else money_sig.text.action
    )
    money_avoid = (
        "تجنب الشراء الاندفاعي أو الوعود المالية غير المحسوبة."
        if money_sig is None
        else money_sig.text.avoid
    )
    money_domain = DomainInsight(
        key="wealth",
        title_ar="المال والأولويات",
        color_hex="#30D158",  # Apple System Green
        score=money_score,
        badge_ar=money_badge,
        headline=money_headline,
        action=money_action,
        avoid=money_avoid,
    )

    # 3. Relationships, Family & Attachment (Liz Greene / Rudhyar / Hand)
    rel_sig = _pick(rel_signals, {"venus", "moon", "mars", "mercury", "sun", "dsc"})
    if rel_sig is None:
        rel_sig = _pick(self_signals, {"venus", "moon", "dsc"})
    rel_score, rel_badge = _score_from(rel_sig, 82)
    rel_domain = DomainInsight(
        key="relationships",
        title_ar="العلاقات والبيت",
        color_hex="#0A84FF",  # Apple System Blue
        score=rel_score,
        badge_ar=rel_badge,
        headline=rel_sig.text.line if rel_sig else lunation.relation_tip,
        action=rel_sig.text.action if rel_sig else lunation.relation_tip,
        avoid=rel_sig.text.avoid if rel_sig else "لا تفترض أن الطرف الآخر يقرأ صمتك دون توضيح.",
    )

    # 4. Vitality, Mind & Emotional Shadow (Demetra George / Liz Greene / Joy Usher)
    inner_sig = _pick(self_signals, {"moon", "neptune", "pluto", "uranus", "chiron"})
    inner_score, inner_badge = _score_from(inner_sig, 76)
    inner_color = "#FF453A" if (inner_sig and inner_sig.polarity == "friction") else "#0A84FF"
    inner_domain = DomainInsight(
        key="vitality",
        title_ar="الطاقة والاتزان",
        color_hex=inner_color,
        score=inner_score,
        badge_ar=inner_badge,
        headline=lunation.rhythm_ar,
        action=lunation.energy_tip,
        avoid=inner_sig.text.avoid if inner_sig else "لا تحمل جسدك فوق طاقته حين يحتاج تهدئة.",
    )

    return [work_domain, money_domain, rel_domain, inner_domain]


def build_book_pillars(
    chart: Chart,
    profile: Profile,
    sect: SectProfile,
    profection: ProfectionYear,
    lunation: LunationPhase,
    signals: dict[str, list[Signal]],
) -> list[BookPillar]:
    """Generate personalized insights anchored in the 10 foundational astrology books."""
    self_signals = signals.get("self", [])
    eagle, lark = split_eagle_and_lark(self_signals)
    eagle_line = (
        eagle[0].text.line
        if eagle
        else "الدورات الكبرى تدعوك لتثبيت الأساس الهيكلي بهدوء وثبات."
    )
    lark_line = (
        lark[0].text.line
        if lark
        else "الإيقاع اليومي هادئ ومناسب لإنجاز الخطوات الصغيرة المتراكمة."
    )

    sun_pos = chart.body("sun")
    moon_pos = chart.body("moon")
    saturn_pos = chart.body("saturn")
    sun_el = element_ar(sign_element(sun_pos.sign)) if sun_pos else "مائي"
    moon_el = element_ar(sign_element(moon_pos.sign)) if moon_pos else "ناري"
    saturn_el = element_ar(sign_element(saturn_pos.sign)) if saturn_pos else "ناري"

    return [
        BookPillar(
            title_en="Astrology and the Authentic Self",
            author_en="Demetra George",
            concept_ar="الذات الأصيلة والحيز الفلكي (Sect)",
            personal_insight_ar=sect.summary_ar,
            color_hex="#0A84FF",
        ),
        BookPillar(
            title_en="Astrology of Fate",
            author_en="Liz Greene",
            concept_ar="القدر والظل والتحول النفسي (Moira & Shadow)",
            personal_insight_ar=(
                f"موضع الانضباط ({saturn_el}) يكشف أن ما يبدو عائقًا متكررًا هو في الحقيقة "
                "بوابتك للنضج حين تتوقف عن مقاومته بصمت وتواجهه بوعي."
            ),
            color_hex="#FF453A",
        ),
        BookPillar(
            title_en="The Anthology",
            author_en="Vettius Valens (tr. Mark Riley)",
            concept_ar="أرباب الزمان وانتهاءات السنين (Chronocrators)",
            personal_insight_ar=profection.summary_ar.replace("**", ""),
            color_hex="#FF9F0A",
        ),
        BookPillar(
            title_en="Horoscope Symbols",
            author_en="Robert Hand",
            concept_ar="الرموز الفلكية كحقول طاقة حية",
            personal_insight_ar=(
                "كل عبور ليس حدثًا مفروضًا عليك، بل طاقة خام يمكنك اختيار تعبيرها الأرقى "
                "عبر الفعل الواعي بدل رد الفعل التلقائي."
            ),
            color_hex="#30D158",
        ),
        BookPillar(
            title_en="A Tiny Universe's Companion",
            author_en="Joy Usher",
            concept_ar="التوازن اليومي للعناصر الأربعة",
            personal_insight_ar=(
                f"الجمع بين طابع الجوهر ({sun_el}) واحتياج الداخل ({moon_el}) يطلب منك "
                "توزيع يومك بين الإنجاز الملموس ووقت الاستشفاء الشخصي."
            ),
            color_hex="#30D158",
        ),
        BookPillar(
            title_en="Hellenistic Astrology",
            author_en="Chris Brennan",
            concept_ar="نظام البيوت الكاملة والسهام الهلنستية",
            personal_insight_ar=(
                f"تركيز المرحلة الحالية يفعّل محور «{profection.topic_title}»؛ "
                "الخطوات الصغيرة في هذا الباب تعطي أثرًا مضاعفًا."
            ),
            color_hex="#0A84FF",
        ),
        BookPillar(
            title_en="The Lunation Cycle",
            author_en="Dane Rudhyar",
            concept_ar="الدورة القمرية الثمانية (Soli-Lunar Rhythm)",
            personal_insight_ar=f"{lunation.name_ar} ({lunation.angle}°): {lunation.rhythm_ar}",
            color_hex="#0A84FF",
        ),
        BookPillar(
            title_en="Predictive Astrology: The Eagle and the Lark",
            author_en="Bernadette Brady",
            concept_ar="نظرة النسر الكبرى وأغنية القبرة اليومية",
            personal_insight_ar=f"النسر (الإطار العام): {eagle_line} | القبرة (نبض اليوم): {lark_line}",
            color_hex="#FF9F0A",
        ),
        BookPillar(
            title_en="The Complete Astrological Writings",
            author_en="Aleister Crowley",
            concept_ar="الإرادة الحقة وتوجيه القوة الكوكبية",
            personal_insight_ar=(
                "قوة الخريطة تظهر حين تقود طاقتك نحو هدف واحد واضح تختاره بإرادتك، "
                "دون تبديدها في معارك جانبية."
            ),
            color_hex="#FF9F0A",
        ),
        BookPillar(
            title_en="Ancient Astrology in Theory and Practice Vol. 1 & 2",
            author_en="Demetra George",
            concept_ar="حالة الكواكب وجودة الأداء العملي",
            personal_insight_ar=(
                f"النير القائد في خريطتك ({BODIES_AR.get(sect.sect_light, '')}) والسعد الداعم "
                f"({BODIES_AR.get(sect.benefic_leader, '')}) يعملان بأفضل صورة حين تلتزم بإيقاع يومي واضح."
            ),
            color_hex="#30D158",
        ),
    ]
