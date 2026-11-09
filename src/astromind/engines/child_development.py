"""Child development guidance derived from the child's chart and age band."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from astromind.engines.charts import Chart
from astromind.engines.signals import Signal
from astromind.generators import interpretations
from astromind.i18n import sign_element
from astromind.models import Profile


@dataclass(frozen=True)
class ChildGuidance:
    child_id: str
    name: str
    age: int | None
    learning: str
    security: str
    energy: str
    talent: str
    age_note: str
    support_actions: tuple[str, ...]
    avoid: tuple[str, ...]


def _support_actions(chart: Chart) -> tuple[str, ...]:
    mercury = chart.body("mercury")
    moon = chart.body("moon")
    mars = chart.body("mars")
    actions: list[str] = []

    if mercury:
        element = sign_element(mercury.sign)
        actions.append(
            {
                "fire": "اشرح دقيقتين ثم دعه يجرب بنفسه؛ لا تُطل الجلسة النظرية.",
                "earth": "قسّم المهمة إلى 3 خطوات ملموسة، وأظهر له النتيجة النهائية.",
                "air": "اسأله أن يشرح لك ما فهمه؛ الحوار يثبّت المعلومة.",
                "water": "ابدأ بقصة أو صورة، وطمئنه أنه يستطيع السؤال دون عقاب.",
            }[element]
        )
    if moon:
        element = sign_element(moon.sign)
        actions.append(
            {
                "fire": "امدح الجهد أمامه صراحة، وامنحه حركة قبل الواجبات.",
                "earth": "حافظ على روتين النوم والطعام؛ التغيير المفاجئ يزعزعه.",
                "air": "اسأله عن يومه واسمعه دون تصحيح فوري.",
                "water": "خصّص 10 دقائق قربًا بلا شاشة قبل الكلام عن المهام.",
            }[element]
        )
    if mars:
        element = sign_element(mars.sign)
        actions.append(
            {
                "fire": "أخرج الطاقة حركيًا قبل وقت التركيز.",
                "earth": "أعطه عملًا يدويًا أو مسؤولية ملموسة.",
                "air": "اسمح بنشاط اجتماعي أو لعبة كلامية بعد الواجب.",
                "water": "وفّر وقتًا هادئًا وفنًا أو ماءً لتفريغ المشاعر.",
            }[element]
        )
    return tuple(actions[:3])


def _avoid(chart: Chart) -> tuple[str, ...]:
    mercury = chart.body("mercury")
    moon = chart.body("moon")
    mars = chart.body("mars")
    avoid: list[str] = []
    if mercury and sign_element(mercury.sign) == "water":
        avoid.append("لا تبدأ بالمنطق أو المقارنة مع الآخرين قبل الاعتراف بالشعور.")
    if mercury and sign_element(mercury.sign) == "fire":
        avoid.append("لا تُطل الشرح أو تجلسه أمام مهمة طويلة بلا حركة.")
    if mercury and sign_element(mercury.sign) == "air":
        avoid.append("لا تعطِ أمرًا بلا سبب؛ ناقشه باختصار واسمح بسؤال.")
    if moon and sign_element(moon.sign) == "earth":
        avoid.append("لا تعده بشيء صغير ثم تؤجله؛ الثبات هو الأمان.")
    if moon and sign_element(moon.sign) == "air":
        avoid.append("لا تسكت وتتوقع أن يفهم؛ اشرح سبب القرار.")
    if moon and sign_element(moon.sign) == "fire":
        avoid.append("لا تكبت الحماس أو تجبره على الجلوس الطويل؛ وفّر حركة قبل الطلب.")
    if mars and sign_element(mars.sign) == "fire":
        avoid.append("لا تؤجل تفريغ الطاقة إلى نهاية اليوم؛ سيتحول إلى توتر.")
    avoid.append("لا تستخدم الخريطة كتسمية ثابتة؛ راقب السلوك أولًا.")
    return tuple(dict.fromkeys(avoid))


def build_child_guidance(
    profile: Profile, chart: Chart, on_date: date
) -> ChildGuidance:
    age = profile.age_on(on_date)
    return ChildGuidance(
        child_id=profile.id,
        name=profile.name,
        age=age,
        learning=interpretations.child_learning(chart),
        security=interpretations.child_security(chart),
        energy=interpretations.child_energy(chart),
        talent=interpretations.child_talent(chart),
        age_note=(
            interpretations.age_advice(age)
            if age is not None
            else "العمر غير متاح لأن تاريخ الميلاد غير موجود؛ استخدم المرحلة الظاهرة سلوكيًا."
        ),
        support_actions=_support_actions(chart),
        avoid=_avoid(chart),
    )


def monthly_child_focus(signals: list[Signal], limit: int = 3) -> list[str]:
    """Pick transits that touch learning, security, and energy points."""
    priority = {"mercury": 3, "moon": 3, "mars": 2, "sun": 2, "saturn": 2}
    relevant = [
        signal
        for signal in signals
        if signal.target in priority and signal.target != "asc"
    ]
    relevant.sort(
        key=lambda item: (priority.get(item.target, 0), item.score), reverse=True
    )
    return [f"- {item.text.line} {item.text.action}" for item in relevant[:limit]]
