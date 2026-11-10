"""Arabic interpretation banks and copy generation.

The engine deliberately separates facts from prose: this module turns
planet/aspect combinations into short, actionable Arabic sentences.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from astromind.engines.charts import Chart
from astromind.engines.ephemeris import BodyPosition
from astromind.i18n import (
    ASPECTS_AR,
    ASPECT_NATURE_AR,
    BODIES_AR,
    SIGNS_AR,
    element_ar,
    modality_ar,
    sign_element,
    sign_modality,
    sign_name,
)
from astromind.engines.transits import TransitHit

PLANET_THEME: dict[str, str] = {
    "moon": "مزاجك واحتياجك العاطفي",
    "sun": "طاقتك وواجهتك",
    "mercury": "تفكيرك وكلامك",
    "venus": "قربك وتقديرك",
    "mars": "دفعك واحتكاكك",
    "jupiter": "توسعك وفرصك",
    "saturn": "ضغطك والتزاماتك",
    "uranus": "استقلالك ومفاجآتك",
    "neptune": "حساسيتك وضبابك",
    "pluto": "تحولك وعمقك",
    "node": "اتجاهك",
    "chiron": "جرحك القديم",
}

TARGET_THEME: dict[str, str] = {
    "sun": "هويتك",
    "moon": "أمانك العاطفي",
    "mercury": "تواصلك",
    "venus": "قربك وتقديرك",
    "mars": "طاقتك وحدودك",
    "jupiter": "توسعك",
    "saturn": "التزاماتك وحدودك",
    "uranus": "استقلالك",
    "neptune": "حساسيتك",
    "pluto": "تحولك",
    "node": "اتجاهك",
    "asc": "محور ظهورك",
    "mc": "محور مسارك",
    "dsc": "محور شريكك",
    "ic": "محور بيتك",
}

FEMININE_PLANETS = {"sun", "venus"}

TONE_M = {
    "friction": "يضغط على",
    "support": "يسهّل",
    "opportunity": "يفتح فرصة في",
    "info": "يلامس",
}

TONE_F = {
    "friction": "تضغط على",
    "support": "تسهّل",
    "opportunity": "تفتح فرصة في",
    "info": "تلامس",
}

TARGET_THEME_DUAL: dict[str, str] = {
    "sun": "هويتكما",
    "moon": "أمانكما العاطفي",
    "mercury": "تواصلكما",
    "venus": "قربكما وتقديركما",
    "mars": "طاقتكما وحدودكما",
    "jupiter": "توسعكما",
    "saturn": "التزاماتكما وحدودكما",
    "uranus": "استقلالكما",
    "neptune": "حساسيتكما",
    "pluto": "تحولكما",
    "node": "اتجاهكما",
    "asc": "محور ظهوركما",
    "mc": "محور مساركما",
    "dsc": "محور علاقتكما",
    "ic": "محور بيتكما",
}

DUAL_ACTION = {
    "friction": "خفّفا المطالب، واختارا خطوة واحدة مشتركة.",
    "support": "استثمرا النافذة في وقت مشترك قصير.",
    "opportunity": "ابدآ بمبادرة صغيرة.",
    "info": "اسألا بدل التخمين.",
}

DUAL_AVOID = {
    "friction": "لا تفتحا موضوعًا هيكليًا في ذروة الضغط.",
    "support": "لا تؤجلا القرار.",
    "opportunity": "لا تبالغا في التوقعات.",
    "info": "لا تحوّلا الملاحظة إلى حكم.",
}

TARGET_THEME_THIRD: dict[str, str] = {
    "sun": "هويته",
    "moon": "أمان{h} العاطفي",
    "mercury": "تواصله",
    "venus": "قربه وتقديره",
    "mars": "طاقته وحدوده",
    "jupiter": "توسعه",
    "saturn": "التزاماته وحدوده",
    "uranus": "استقلاله",
    "neptune": "حساسيته",
    "pluto": "تحوله",
    "node": "اتجاهه",
    "asc": "محور ظهوره",
    "mc": "محور مساره",
    "dsc": "محور شريكه",
    "ic": "محور بيته",
}

OTHER_ACTION = {
    "friction": "امنحه مساحة وقلّل المطالب اليوم.",
    "support": "نافذة جيدة للتواصل أو لطلب بسيط.",
    "opportunity": "اقترح خطوة مشتركة صغيرة.",
    "info": "اسأل بدل أن تخمّن.",
}

OTHER_AVOID = {
    "friction": "لا تفتح موضوعًا هيكليًا في ذروة الضغط.",
    "support": "لا تؤجل ما يمكن إنجازه الآن.",
    "opportunity": "لا تبالغ في التوقعات.",
    "info": "لا تحوّل الملاحظة إلى حكم.",
}

GENERIC = {
    "friction": {
        "action": "اختر استجابة واحدة صغيرة، ولا تحاول حل كل شيء اليوم.",
        "avoid": "لا تتخذ قرارًا دائمًا وأنت تحت الضغط.",
    },
    "support": {
        "action": "استثمر النافذة في خطوة واحدة كانت مؤجلة.",
        "avoid": "لا تفترض أن السهولة ستدوم؛ أنجز الآن.",
    },
    "opportunity": {
        "action": "ابدأ أنت؛ المبادرة ستُقابل بترحيب.",
        "avoid": "لا تنتظر الإشارة المثالية.",
    },
    "info": {
        "action": "راقب ولا تُصدر حكمًا سريعًا.",
        "avoid": "لا تبالغ في قراءة الأمور.",
    },
}

TARGET_GUIDANCE: dict[str, dict[str, tuple[str, str]]] = {
    "sun": {
        "friction": (
            "ركّز طاقتك في مهمة أساسية واحدة تعبّر عن قصدك، وخفّف استعراض القوة.",
            "لا تدخل صراع هيبة أو تستنزف نفسك لإثبات حضورك.",
        ),
        "support": (
            "تقدّم بخطوة قيادية واضحة أو اعرض مشروعك بثقة هادئة.",
            "لا تنتظر تصفيق الآخرين لتبدأ ما تعرف أنه صحيح.",
        ),
    },
    "moon": {
        "friction": (
            "احمِ مساحتك الهادئة اليوم، وسمِّ احتياجك العاطفي بجملة قصيرة ومباشرة.",
            "لا تتخذ قرارًا قاطعًا وأنت مرهق أو تحت ضغط شعوري.",
        ),
        "support": (
            "استثمر الدفء الحالي في جلسة عائلية هادئة أو راحة مبكرة ترمم طاقتك.",
            "لا تملأ وقت راحتك بالتزامات إضافية غير ضرورية.",
        ),
    },
    "mercury": {
        "friction": (
            "اكتب النقاط الأساسية قبل أي نقاش، واطلب توضيحًا بدل افتراض النية.",
            "لا ترسل ردًا سريعًا في لحظة انفعال أو تتشتت بين خمس مهام معًا.",
        ),
        "support": (
            "رتّب أوراقك، أنهِ المراسلات المؤجلة، أو افتح حوارًا يحتاج صياغة ذكية.",
            "لا تترك الأفكار الجيدة دون تدوين أو خطوة تنفيذية.",
        ),
    },
    "venus": {
        "friction": (
            "عبّر عن تقديرك بلطف، وراجع مصاريفك بهدوء قبل أي التزام مالي أو عاطفي.",
            "لا تختبر معزتك بالصمت ولا تعوّض التوتر بشراء اندفاعي.",
        ),
        "support": (
            "بادر بلفتة دافئة مع من تحب، أو رتّب أولوية مالية تضيف جمالًا وراحة ليومك.",
            "لا تؤجل كلمة طيبة يمكن أن تفتح الأبواب الآن.",
        ),
    },
    "mars": {
        "friction": (
            "وجّه فائض الطاقة إلى إنجاز عملي محدد أو حركة بدنية قبل أي تفاوض.",
            "لا تحوّل الاستعجال إلى صدام مباشر أو تكسر إيقاعك الطبيعي.",
        ),
        "support": (
            "احسم المهمة الأصعب في جدولك الآن؛ شجاعتك العملية في ذروتها.",
            "لا تبعثر هذا الزخم في معارك صغيرة لا تخدم هدفك.",
        ),
    },
    "jupiter": {
        "friction": (
            "رحّب بالفرص لكن ضع لها سقفًا واضحًا من الوقت والميزانية.",
            "لا تفرط في الوعود أو تفتح التزامات تفوق سعة يومك.",
        ),
        "support": (
            "وسّع أفقك بخطوة تعلم، أو اطلب دعمًا لمشروع يستحق النمو.",
            "لا تصغّر طموحك بدافع التردد.",
        ),
    },
    "saturn": {
        "friction": (
            "رتّب التزاماتك حسب الأهمية، وأنجز لبنة واحدة متقنة بدل القلق من الجبل كله.",
            "لا تقسُ على نفسك أو تفسّر التأخير المؤقت كفشل.",
        ),
        "support": (
            "ثبّت عادة يومية أو قاعدة عملية طويلة الأمد؛ البناء اليوم يدوم طويلًا.",
            "لا تستعجل الثمرة قبل استكمال الأساس.",
        ),
    },
    "neptune": {
        "friction": (
            "تحقق من الأرقام والمواعيد المكتوبة، وامنح ذهنك وقتًا بعيدًا عن الضجيج.",
            "لا تبنِ التزامًا ماليًا أو عاطفيًا على انطباع غامض غير مؤكد.",
        ),
        "support": (
            "استفد من صفاء حدسك في عمل إبداعي أو لحظة تأمل هادئة.",
            "لا تهمل الإلهام الصغير الذي يزورك اليوم.",
        ),
    },
    "uranus": {
        "friction": (
            "اترك هامشًا للمرونة في جدولك، وجرّب زاوية نظر جديدة عند ظهور مفاجأة.",
            "لا تهدم التزامًا مستقرًا لمجرد الرغبة اللحظية في التغيير.",
        ),
        "support": (
            "حدّث طريقتك المعتادة بتجربة أداة أو فكرة مبتكرة تختصر الجهد.",
            "لا تتمسك بروتين قديم لم يعد يخدمك.",
        ),
    },
    "pluto": {
        "friction": (
            "راقب ما يثير رغبتك في السيطرة، وحوّل التركيز إلى تنظيف ما استُهلك في يومك.",
            "لا تدخل لعبة شدّ حبل نفسية أو تفتح جرحًا قديمًا بلا داعٍ.",
        ),
        "support": (
            "تعمّق في جذور المسألة التي تعمل عليها؛ لديك قدرة عالية على التركيز الحاسم.",
            "لا تكتفِ بالحلول السطحية حين تكون قادرًا على الإصلاح الجذري.",
        ),
    },
    "asc": {
        "friction": (
            "تمهّل في انطباعك الأول، واضبط إيقاع جسدك وتنفسك قبل الرد.",
            "لا تحمل توتر المحيط على كتفيك.",
        ),
        "support": (
            "اظهر بمبادرتك الطبيعية؛ حضورك الشخصي يترك أثرًا مريحًا ومقنعًا اليوم.",
            "لا تتوارَ خلف الكواليس حين تكون المبادرة لك.",
        ),
    },
    "mc": {
        "friction": (
            "راجع أولوياتك المهنية بهدوء، واحمِ توازنك بين العمل والبيت.",
            "لا تتخذ قرارًا مهنيًا متسرعًا تحت ضغط اللحظة.",
        ),
        "support": (
            "خطوة مهنية واضحة أو تواصل مع صاحب قرار يعزز مكانتك ومسارك.",
            "لا تؤجل إبراز إنجازك الفعلي.",
        ),
    },
}
OVERRIDES: dict[tuple[str, str], dict[str, str]] = {
    ("saturn", "moon"): {
        "line": "زحل يضغط على قمرك: طاقة عاطفية محدودة وحاجة أكبر للهدوء.",
        "action": "قلّل الالتزامات، ثبّت روتينًا بسيطًا، واطلب الدعم بوضوح.",
        "avoid": "لا تفسّر انسحاب الآخرين كرفض؛ قد يكونون تحت ضغطهم أيضًا.",
    },
    ("mars", "moon"): {
        "line": "المريخ يلامس قمرك: انفعال أسرع وحاجة لتفريغ حركي.",
        "action": "فرّغ الطاقة بالمشي أو التمرين قبل أي نقاش.",
        "avoid": "لا تفتح موضوعًا حساسًا وأنت متوتر.",
    },
    ("uranus", "moon"): {
        "line": "أورانوس يلامس قمرك: حاجة مفاجئة للمساحة أو التغيير.",
        "action": "امنح نفسك مساحة قصيرة، ثم ارجع بوعي.",
        "avoid": "لا تلاحق من انسحب فجأة؛ اسأل بهدوء لاحقًا.",
    },
    ("neptune", "moon"): {
        "line": "نبتون يلامس قمرك: حساسية أعلى وضباب في التوقعات.",
        "action": "اسأل سؤالًا واضحًا بدل التخمين، واكتب ما تشعر به.",
        "avoid": "لا تبنِ قرارًا على نية لم تُصرّح بها.",
    },
    ("pluto", "moon"): {
        "line": "بلوتو يلامس قمرك: مشاعر عميقة وقديمة تطفو.",
        "action": "سمّ الشعور دون أن تتصرف فورًا؛ العمق يحتاج وقتًا.",
        "avoid": "لا تحوّل النقاش إلى صراع سيطرة.",
    },
    ("mercury", "mercury"): {
        "line": "عطارد يلامس عطاردك: رسائلك قد تُفهم أحدّ من قصدك.",
        "action": "اكتب، انتظر عشر دقائق، ثم أرسل.",
        "avoid": "لا تناقش موضوعًا حساسًا عبر الرسائل النصية.",
    },
    ("mercury", "venus"): {
        "line": "عطارد يلامس زهرتك: الكلام يصبح لغة قرب.",
        "action": "قل ما تقدّره صراحة، وسمِّ شيئًا تحبه.",
        "avoid": "لا تكتفِ بالإيماءات؛ الكلمة مطلوبة.",
    },
    ("venus", "moon"): {
        "line": "الزهرة تلامس قمرك: نافذة قرب عاطفي وسهولة في التعبير.",
        "action": "وقت بلا شاشة، لمسة، أو رسالة قصيرة صادقة.",
        "avoid": "لا تؤجل لحظة القرب بحجة الانشغال.",
    },
    ("venus", "venus"): {
        "line": "الزهرة تلامس زهرتك: تقدير وقرب أسهل من المعتاد.",
        "action": "اقترح نشاطًا مشتركًا بسيطًا.",
        "avoid": "لا تبالغ في الهدايا؛ الحضور أهم.",
    },
    ("saturn", "venus"): {
        "line": "زحل يلامس زهرتك: القرب يحتاج وقتًا ووضوحًا.",
        "action": "قل ما تريده بوضوح، وامنح الطرف الآخر وقتًا.",
        "avoid": "لا تختبر الحب بالصمت أو الغياب.",
    },
    ("mars", "venus"): {
        "line": "المريخ يلامس زهرتك: جذب قوي لكنه قد يتحول إلى احتكاك.",
        "action": "حوّل الطاقة إلى مبادرة واضحة لا إلى جدال.",
        "avoid": "لا تخلط بين الشهوة والمنافسة.",
    },
    ("mars", "mars"): {
        "line": "المريخ يلامس مريخك: احتكاك مباشر في طريقة الدفع.",
        "action": "حدّد أولوية واحدة، واترك الباقي غدًا.",
        "avoid": "لا تدخل مواجهة لا تحتاجها.",
    },
    ("saturn", "mars"): {
        "line": "زحل يقيد مريخك: توقف أو مقاومة عند كل دفعة.",
        "action": "أجّل الهجوم، ورتّب الخطوات بهدوء.",
        "avoid": "لا تدفع بقوة؛ الصدام سيكلّفك أكثر.",
    },
    ("saturn", "sun"): {
        "line": "زحل يلامس شمسك: مسؤولية وضغط إنجاز.",
        "action": "اختر واجبًا واحدًا وأتمّه، وقلّل الوعود.",
        "avoid": "لا تهرب من الالتزام؛ سيعود أكبر.",
    },
    ("jupiter", "sun"): {
        "line": "المشتري يلامس شمسك: توسع وثقة وفرصة.",
        "action": "تقدّم بطلب أو فكرة كنت تؤجلها.",
        "avoid": "لا تبالغ في الوعود أو المصروف.",
    },
    ("saturn", "mercury"): {
        "line": "زحل يلامس عطاردك: تفكير أبطأ وأكثر جدية.",
        "action": "اكتب الأفكار، وراجعها قبل الإرسال.",
        "avoid": "لا تفسّر بطء الآخر كرفض.",
    },
    ("mars", "mercury"): {
        "line": "المريخ يلامس عطاردك: حدة في الكلام وسرعة في الرد.",
        "action": "خفّض نبرتك درجة واحدة قبل الرد.",
        "avoid": "لا ترد على رسالة غاضبة فورًا.",
    },
    ("neptune", "mercury"): {
        "line": "نبتون يلامس عطاردك: ضباب معلوماتي وسوء فهم محتمل.",
        "action": "أعد صياغة ما سمعته واسأل: هل فهمت صح؟",
        "avoid": "لا توقّع عقدًا أو قرارًا بلا مراجعة.",
    },
    ("pluto", "sun"): {
        "line": "بلوتو يلامس شمسك: تحول في الهوية والطموح.",
        "action": "اترك ما لم يعد يناسبك، ولو خطوة صغيرة.",
        "avoid": "لا تتشبث بصورة قديمة عن نفسك.",
    },
    ("uranus", "venus"): {
        "line": "أورانوس يلامس زهرتك: حاجة للمساحة داخل العلاقة.",
        "action": "اتفق على مساحة متبادلة بدل الانسحاب المفاجئ.",
        "avoid": "لا تكسر شيئًا فقط لتشعر بالحرية.",
    },
    ("moon", "moon"): {
        "line": "القمر يلامس قمرك: مزاج متغير واحتياج واضح للراحة.",
        "action": "خفّف الجدول، واشرب ماءً ونم مبكرًا.",
        "avoid": "لا تتخذ قرارًا عاطفيًا في ذروة التغير.",
    },
    ("moon", "venus"): {
        "line": "القمر يلامس زهرتك: حنان سهل وتقدير صغير يكفي.",
        "action": "قل كلمة تقدير واحدة صادقة.",
        "avoid": "لا تنتظر مناسبة كبيرة.",
    },
}


@dataclass(frozen=True)
class Copy:
    title: str
    line: str
    action: str
    avoid: str


def transit_copy(
    hit: TransitHit, perspective: str = "self", pronoun: str = "m"
) -> Copy:
    planet = BODIES_AR.get(hit.transiting, hit.transiting)
    aspect = ASPECTS_AR.get(hit.aspect, hit.aspect)
    nature = ASPECT_NATURE_AR.get(hit.aspect, aspect)
    tones = TONE_F if hit.transiting in FEMININE_PLANETS else TONE_M
    tone = tones.get(hit.polarity, tones["info"])

    if perspective == "other":
        suffix = "ها" if pronoun == "f" else "ه"
        target = TARGET_THEME_THIRD.get(
            hit.target, BODIES_AR.get(hit.target, hit.target)
        ).format(h=suffix)
        return Copy(
            title=f"{planet} — {target}",
            line=f"{planet} {tone} {target} عبر {aspect} ({nature}).",
            action=OTHER_ACTION.get(hit.polarity, OTHER_ACTION["info"]),
            avoid=OTHER_AVOID.get(hit.polarity, OTHER_AVOID["info"]),
        )

    if perspective == "relationship":
        target = TARGET_THEME_DUAL.get(
            hit.target, BODIES_AR.get(hit.target, hit.target)
        )
        return Copy(
            title=f"{planet} — {target}",
            line=f"{planet} {tone} {target} عبر {aspect} ({nature}).",
            action=DUAL_ACTION.get(hit.polarity, DUAL_ACTION["info"]),
            avoid=DUAL_AVOID.get(hit.polarity, DUAL_AVOID["info"]),
        )

    target = TARGET_THEME.get(hit.target, BODIES_AR.get(hit.target, hit.target))
    override = OVERRIDES.get((hit.transiting, hit.target))
    generic = GENERIC.get(hit.polarity, GENERIC["info"])
    bucket = "friction" if hit.polarity == "friction" else "support"
    target_specific = TARGET_GUIDANCE.get(hit.target, {}).get(bucket)

    if override:
        line = override["line"]
        action = override["action"]
        avoid = override["avoid"]
    else:
        line = f"{planet} {tone} {target} عبر {aspect} ({nature})."
        if target_specific:
            action, avoid = target_specific
        else:
            action = generic["action"]
            avoid = generic["avoid"]

    title = f"{planet} — {target}"
    return Copy(title=title, line=line, action=action, avoid=avoid)


def synastry_copy(
    a_body: str,
    b_body: str,
    aspect: str,
    polarity: str,
    a_name: str = "أنت",
    b_name: str = "الطرف الآخر",
) -> Copy:
    a = BODIES_AR.get(a_body, a_body)
    b = BODIES_AR.get(b_body, b_body)
    asp = ASPECTS_AR.get(aspect, aspect)
    if polarity == "friction":
        line = f"{b} عند {b_name} في {asp} مع {a} عندك: نقطة احتكاك تحتاج صراحة."
        action = "اتفقا على إشارة توقف قبل أن يتحول النقاش إلى صراع."
        avoid = "لا تستخدم هذه النقطة كسلاح في الخلاف."
    elif polarity in {"support", "opportunity"}:
        line = f"{b} عند {b_name} في {asp} مع {a} عندك: نقطة سهولة ودفء."
        action = "استثمرها في وقت مشترك قصير ومنتظم."
        avoid = "لا تفترض أن السهولة تعني غياب الحاجة للكلام."
    else:
        line = f"{b} عند {b_name} في {asp} مع {a} عندك: تعلّم متبادل."
        action = "اسأل بدل أن تخمّن."
        avoid = "لا تحوّل الاختلاف إلى حكم على النية."
    return Copy(title=f"{a} × {b}", line=line, action=action, avoid=avoid)


# ---------------------------------------------------------------------------
# Sign-based manuals
# ---------------------------------------------------------------------------

MERCURY_STYLE = {
    "fire": {
        "title": "عطارد ناري — يتكلم ليبدأ",
        "summary": "يفكر بصوت عالٍ، ويحب الاختصار والتحدي والأفكار الكبيرة.",
        "action": "اطرح فكرة واحدة قابلة للنقاش، واتركه يكملها.",
        "avoid": "لا تُطل الشرح النظري أو التفاصيل المتكررة.",
    },
    "earth": {
        "title": "عطارد ترابي — عملي وتفصيلي",
        "summary": "يحتاج أمثلة ومصداقية ونتيجة ملموسة قبل أن يقتنع.",
        "action": "أعطِ خطوات واضحة ونتيجة متوقعة.",
        "avoid": "لا تطلب منه قرارًا بلا معطيات.",
    },
    "air": {
        "title": "عطارد هوائي — حواري وتحليلي",
        "summary": "يحتاج خيارات ونقاشًا وربطًا بين الأفكار.",
        "action": "اعرض خيارين واطلب رأيه صراحة.",
        "avoid": "لا تصمت وتتوقع أن يفهم من نفسه.",
    },
    "water": {
        "title": "عطارد مائي — شعوري واستعاري",
        "summary": "يحتاج أمانًا عاطفيًا قبل المنطق والتفاصيل.",
        "action": "ابدأ بـ«كيف تشعر؟» ثم انتقل إلى الحقائق.",
        "avoid": "لا تبدأ بالجدول أو الأرقام أو الحلول.",
    },
}

MODALITY_NOTE = {
    "cardinal": "يبدأ بسرعة ويحتاج قرارًا واضحًا.",
    "fixed": "يثبت على موقفه ويحتاج وقتًا للتحول.",
    "mutable": "يتكيف بسهولة لكنه قد يتشتت.",
}

MOON_NEEDS = {
    "fire": "تقدير + مساحة + حركة. يحتاج أن يُرى ويُشجّع، لا أن يُدار.",
    "earth": "استقرار + روتين + أفعال ملموسة. الوعود الصغيرة الملتزمة أهم من الكلام.",
    "air": "كلام + مساحة + تنويع. يحتاج أن يشرح ما يشعر به دون أن يُحكم عليه.",
    "water": "قرب + احتواء + طمأنينة. يحتاج أن يشعر أنك حاضر قبل أن تطلب منه الحل.",
}

VENUS_LOVE = {
    "fire": "إعجاب ومغامرة ومبادرة. القرب يولد من الحماس والتجربة المشتركة.",
    "earth": "التزام وأفعال وهدايا ملموسة. الثبات اليومي هو رسالة الحب.",
    "air": "كلام ورفقة خفيفة ومساحة. الحوار هو المقدمة.",
    "water": "عمق وحميمية وانتباه. يحتاج أن يشعر أنك تراه لا أنك تحلله.",
}

MARS_ANGER = {
    "fire": "انفجار سريع ثم نسيان. لا تلاحق أثر الخلاف بعد أن يهدأ.",
    "earth": "إصرار صامت ومقاومة. لا تدفعه؛ أعطه وقتًا وسببًا واضحًا.",
    "air": "جدال لفظي. يحتاج منطقًا واحترامًا، لا رفع صوت.",
    "water": "انسحاب وجرح داخلي. اسأل بلطف ولا تفسّر الصمت كبرود.",
}

SATURN_FEAR = {
    "fire": "يخشى فقدان الحماس أو الحرية؛ طمئنه أن الالتزام لا يقتل الحياة.",
    "earth": "يخشى الفوضى أو عدم الكفاءة؛ أعطه خطة وخطوات.",
    "air": "يخشى الوحدة أو عدم الفهم؛ اشرح نواياك بالكلام.",
    "water": "يخشى الهجر أو الجفاف العاطفي؛ ثبّت حضورك لا كلامك فقط.",
}

LEARNING_STYLE = {
    "fire": "يتعلم بالتجربة والحركة والمنافسة. اشرح دقيقتين ثم دعه يجرب.",
    "earth": "يتعلم بالتطبيق والتسلسل والنتيجة الملموسة. قسّم المهمة إلى خطوات.",
    "air": "يتعلم بالحوار والأسئلة والربط. اسأله أن يشرح لك ما فهمه.",
    "water": "يتعلم بالقصة والصورة والأمان. ابدأ بالقصة ثم القاعدة.",
}

TALENT_STYLE = {
    "fire": "التجربة والحركة والمنافسة",
    "earth": "التطبيق والتسلسل والنتيجة الملموسة",
    "air": "الحوار والأسئلة والربط بين الأفكار",
    "water": "القصة والصور والأمان العاطفي",
}

ENERGY_OUTLET = {
    "fire": "رياضة سريعة، تحديات حركية، مساحة للحركة والمنافسة الشريفة.",
    "earth": "عمل يدوي، بناء، ترتيب، رياضة منتظمة، ونتائج ملموسة.",
    "air": "أنشطة اجتماعية، ألعاب كلامية، تنويع وتحديات ذهنية.",
    "water": "سباحة، رسم، موسيقى، وقت هادئ قريب من شخص آمن.",
}

AGE_ADVICE = {
    (0, 3): "نظّم اليوم بالنوم والطعام واللمس. وقت الانتقال يحتاج تحذيرًا مسبقًا، لا مفاجأة.",
    (4, 6): "اللعب هو لغة التعلم. استخدم خيارين لا أوامر، وسمِّ الشعور قبل تصحيح السلوك.",
    (7, 10): "احتياج للكفاءة والقواعد الواضحة. أعطه مسؤولية صغيرة وامدح الجهد لا النتيجة فقط.",
    (11, 14): "احتياج للهوية والخصوصية. تفاوض بدل الأمر، واسأل قبل أن تنصح.",
    (15, 18): "استقلال ومسؤولية متبادلة. اشرح حدودك واترك له قرارًا آمنًا.",
}

COMM_PAIR = {
    ("air", "earth"): "أنتما تختلفان في سرعة المعالجة: أحدهما يريد الفكرة، والآخر يريد التفصيل. ابدأ بالنتيجة ثم أعطِ التفاصيل.",
    ("air", "fire"): "كلانا سريع، لكن النار تريد قرارًا والهواء يريد نقاشًا. حدّدا وقتًا للنقاش ووقتًا للقرار.",
    ("air", "water"): "الهواء يعقلن والماء يشعر. ابدأ بالشعور ثم انتقل إلى التحليل، وإلا شعر الماء أنه غير مسموع.",
    ("earth", "fire"): "النار تريد الحركة والأرض تريد الأمان. اتفقا على خطوة صغيرة قابلة للتطبيق قبل التوسع.",
    ("earth", "water"): "كلانا يحتاج أمانًا، لكن الأرض تعبّر بالأفعال والماء بالكلام. لا تفترض أن صمت الآخر رضا.",
    ("fire", "water"): "النار مباشرة والماء حساس. خفّف حدة الافتتاح، وابدأ بالنية لا بالحكم.",
}

MOON_PAIR = {
    ("air", "earth"): "أحدهما يحتاج كلامًا والآخر أفعالًا. اجمعا بين رسالة قصيرة وفعل صغير.",
    ("air", "fire"): "كلانا يحتاج حركة، لكن أحدهما يحتاج تفسيرًا. اشرح باختصار ثم اخرجا معًا.",
    ("air", "water"): "الماء يحتاج احتواءً قبل النقاش. لا تبدأ بالتحليل حين يكون الطرف الآخر متألمًا.",
    ("earth", "fire"): "أحدهما يحتاج ثباتًا والآخر حماسًا. ثبّتا روتينًا صغيرًا واتركا مساحة للمفاجأة.",
    ("earth", "water"): "كلانا يحتاج أمانًا. أفضل هدية: حضور منتظم ووعد صغير يُنفَّذ.",
    ("fire", "water"): "النار تحتاج تشجيعًا والماء يحتاج طمأنينة. لا تسخر من الحساسية ولا من الحماس.",
}


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def communication_protocol(chart_a: Chart, chart_b: Chart) -> list[str]:
    mercury_a = chart_a.body("mercury")
    mercury_b = chart_b.body("mercury")
    if mercury_a is None or mercury_b is None:
        return ["عطارد غير متوفر في إحدى الخريطتين؛ استخدم الملاحظة المباشرة."]

    sign_a, sign_b = mercury_a.sign, mercury_b.sign
    element_a, element_b = sign_element(sign_a), sign_element(sign_b)
    style_a = MERCURY_STYLE[element_a]
    style_b = MERCURY_STYLE[element_b]
    pair = COMM_PAIR.get(_pair_key(element_a, element_b))

    lines = [
        f"- عندك: {style_a['title']} ({SIGNS_AR[sign_a]}). {style_a['summary']}",
        f"- عند الطرف الآخر: {style_b['title']} ({SIGNS_AR[sign_b]}). {style_b['summary']}",
        f"- عندك: {MODALITY_NOTE[sign_modality(sign_a)]}",
        f"- عند الطرف الآخر: {MODALITY_NOTE[sign_modality(sign_b)]}",
    ]
    if pair:
        lines.append(f"- القاعدة الذهبية: {pair}")
    else:
        lines.append("- القاعدة الذهبية: تشابها في أسلوب المعالجة؛ استفيدا من ذلك، لكن لا تفترضا نفس الحاجة.")
    return lines


def moon_protocol(chart_a: Chart, chart_b: Chart) -> list[str]:
    moon_a = chart_a.body("moon")
    moon_b = chart_b.body("moon")
    if moon_a is None or moon_b is None:
        return ["القمر غير متوفر في إحدى الخريطتين."]
    element_a = sign_element(moon_a.sign)
    element_b = sign_element(moon_b.sign)
    pair = MOON_PAIR.get(_pair_key(element_a, element_b))
    lines = [
        f"- احتياجك: {element_ar(element_a)} — {MOON_NEEDS[element_a]}",
        f"- احتياج الطرف الآخر: {element_ar(element_b)} — {MOON_NEEDS[element_b]}",
    ]
    if pair:
        lines.append(f"- التقاء الاحتياجين: {pair}")
    return lines


def mars_protocol(chart_a: Chart, chart_b: Chart) -> list[str]:
    mars_a = chart_a.body("mars")
    mars_b = chart_b.body("mars")
    if mars_a is None or mars_b is None:
        return ["المريخ غير متوفر في إحدى الخريطتين."]
    return [
        f"- عندك: {MARS_ANGER[sign_element(mars_a.sign)]}",
        f"- عند الطرف الآخر: {MARS_ANGER[sign_element(mars_b.sign)]}",
        "- أثناء الخلاف: سمِّ المشكلة، لا الشخص. واتفقا على إشارة توقف.",
    ]


def venus_protocol(chart_a: Chart, chart_b: Chart) -> list[str]:
    venus_a = chart_a.body("venus")
    venus_b = chart_b.body("venus")
    if venus_a is None or venus_b is None:
        return ["الزهرة غير متوفرة في إحدى الخريطتين."]
    return [
        f"- عندك: {VENUS_LOVE[sign_element(venus_a.sign)]}",
        f"- عند الطرف الآخر: {VENUS_LOVE[sign_element(venus_b.sign)]}",
    ]


def saturn_protocol(chart: Chart) -> list[str]:
    saturn = chart.body("saturn")
    if saturn is None:
        return []
    return [f"- ما يبدو تهديدًا: {SATURN_FEAR[sign_element(saturn.sign)]}"]


def child_learning(chart: Chart) -> str:
    mercury = chart.body("mercury")
    if mercury is None:
        return "عطارد غير متوفر؛ اعتمد على الملاحظة المباشرة."
    element = sign_element(mercury.sign)
    return (
        f"{LEARNING_STYLE[element]} "
        f"(عطارد في {SIGNS_AR[mercury.sign]} — {element_ar(element)}, "
        f"{modality_ar(sign_modality(mercury.sign))})."
    )


def child_security(chart: Chart) -> str:
    moon = chart.body("moon")
    if moon is None:
        return "القمر غير متوفر؛ راقب ما يهدّئه فعليًا."
    element = sign_element(moon.sign)
    return f"{MOON_NEEDS[element]} (قمر في {SIGNS_AR[moon.sign]})."


def child_energy(chart: Chart) -> str:
    mars = chart.body("mars")
    if mars is None:
        return "المريخ غير متوفر؛ ابدأ بأنشطة بدنية متنوعة."
    element = sign_element(mars.sign)
    return f"{ENERGY_OUTLET[element]} (مريخ في {SIGNS_AR[mars.sign]})."


def child_talent(chart: Chart) -> str:
    if chart.houses is not None:
        fifth_cusp = chart.houses.cusps[4]
        sign = int(fifth_cusp // 30) % 12
        element = sign_element(sign)
        return (
            f"البيت الخامس في {SIGNS_AR[sign]} ({element_ar(element)}): "
            f"الموهبة تظهر عبر {TALENT_STYLE[element]}. "
            "قدّم تجارب قصيرة ومتنوعة، ولا تفرض التزامًا طويلًا قبل أن يختار."
        )
    sun = chart.body("sun")
    element = sign_element(sun.sign) if sun else "fire"
    return (
        f"الشمس في {element_ar(element)}: الموهبة تظهر عبر {TALENT_STYLE[element]}. "
        "راقب ما يعود إليه من تلقاء نفسه."
    )


def age_advice(age: int) -> str:
    for (low, high), text in AGE_ADVICE.items():
        if low <= age <= high:
            return text
    if age < 0:
        return "تاريخ الميلاد في المستقبل؛ تحقق من البيانات."
    return "مرحلة راشدة: استخدم الدليل كعدسة تواصل، لا كحكم على الشخص."


def mercury_sign_name(chart: Chart) -> str:
    mercury = chart.body("mercury")
    if mercury is None:
        return "غير متوفر"
    return f"{SIGNS_AR[mercury.sign]} ({element_ar(sign_element(mercury.sign))})"


def moon_sign_name(chart: Chart) -> str:
    moon = chart.body("moon")
    if moon is None:
        return "غير متوفر"
    return f"{SIGNS_AR[moon.sign]} ({element_ar(sign_element(moon.sign))})"


def venus_sign_name(chart: Chart) -> str:
    venus = chart.body("venus")
    if venus is None:
        return "غير متوفر"
    return f"{SIGNS_AR[venus.sign]} ({element_ar(sign_element(venus.sign))})"


def mars_sign_name(chart: Chart) -> str:
    mars = chart.body("mars")
    if mars is None:
        return "غير متوفر"
    return f"{SIGNS_AR[mars.sign]} ({element_ar(sign_element(mars.sign))})"
