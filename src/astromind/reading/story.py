"""Generate an intuitive astrology reading with a local fallback.

The deterministic chart facts are always built first. The optional provider
only rewrites those facts into prose; it cannot add or change placements.
"""

from __future__ import annotations

import os
import sys
from datetime import date

from astromind.generators.interpretations import (
    MARS_ANGER,
    MOON_NEEDS,
    SATURN_FEAR,
    VENUS_LOVE,
)
from astromind.i18n import format_date_short
from astromind.reading.facts import build_reading_facts
from astromind.reading.openrouter import ENV_KEY, OpenRouterError, chat
from astromind.reading.prompts import SYSTEM_PROMPT, build_user_prompt

ELEMENT_KEY = {
    "ناري": "fire",
    "ترابي": "earth",
    "هوائي": "air",
    "مائي": "water",
}

SUN_TONE = {
    "fire": "طاقة تبدأ قبل أن تجد الكلمات، وحاجة أن تُختبر لا أن تُدار",
    "earth": "حاجة إلى أثر ملموس وثبات يُبنى خطوة بخطوة",
    "air": "عقل يربط الأفكار ويحتاج حوارًا قبل أن يستقر",
    "water": "ذاكرة عاطفية عميقة وحاسة تلتقط ما لم يُقل",
}

MOON_TONE = {
    "fire": "استجابة سريعة واشتعال عاطفي ثم حاجة للحركة",
    "earth": "احتياج إلى روتين ملموس ووعود صغيرة تُنفَّذ",
    "air": "احتياج إلى كلام ومساحة وتنويع قبل الهدوء",
    "water": "احتياج إلى قرب واحتواء وطمأنينة قبل الحل",
}

ASC_TONE = {
    "fire": "تدخل المشهد مباشرة وتجعل الآخرين يرون المبادرة أولًا",
    "earth": "تظهر هادئًا وعمليًا، وتثق بما يُبنى لا بما يُقال",
    "air": "تظهر خفيفًا واجتماعيًا، وتفتح الأبواب بالكلام",
    "water": "تظهر متحفظًا ثم تكشف عمقك لمن يربح ثقتك",
}


def _placement(facts: dict, body: str) -> dict:
    return facts.get("profile", {}).get("placements", {}).get(body, {})


def _element(facts: dict, body: str) -> str:
    return ELEMENT_KEY.get(str(_placement(facts, body).get("element", "")), "water")


def _sign(facts: dict, body: str) -> str:
    return str(_placement(facts, body).get("sign") or "غير متاح")


def _house(facts: dict, body: str) -> str:
    house = _placement(facts, body).get("house")
    return f" في البيت {house}" if house else ""


def _angles(facts: dict) -> dict:
    return facts.get("profile", {}).get("angles", {})


def _future_transits(facts: dict) -> list[dict]:
    return [row for row in facts.get("transits", []) if row.get("date")]


def _transit_line(row: dict) -> str:
    when = format_date_short(date.fromisoformat(row["date"]))
    return f"{when}: {row.get('line', '')} — {row.get('action', '')}"


def _opening(facts: dict) -> str:
    sun, moon, asc = _sign(facts, "sun"), _sign(facts, "moon"), _sign(facts, "asc")
    sun_e, moon_e, asc_e = _element(facts, "sun"), _element(facts, "moon"), _element(facts, "asc")
    asc_text = f"، وطالعك {asc}" if asc != "غير متاح" else ""
    return (
        f"تجمع خريطتك بين شمس {sun}{_house(facts, 'sun')} وقمر {moon}{_house(facts, 'moon')}"
        f"{asc_text}. شمسك تحمل {SUN_TONE[sun_e]}، وقمرك يتحرك بـ{MOON_TONE[moon_e]}، "
        f"بينما طالعك يجعلك {ASC_TONE[asc_e]}. "
        "القراءة هنا لا تفصل هذه الطبقات؛ بل تحاول أن تسمع الحوار بينها."
    )


def _inner(facts: dict) -> str:
    moon_e = _element(facts, "moon")
    return (
        f"احتياجك العاطفي الأساسي: {MOON_NEEDS[moon_e]} "
        "قد يبدو هذا الاحتياج بسيطًا، لكنه يصبح واضحًا في اللحظات التي تشعر فيها "
        "أن أحدًا لا يرى ما تحتاجه فعلًا. حين تهدأ، اسأل: هل أطلب القرب بطريقة "
        "يمكن للآخر أن يفهمها، أم أطلب أن يخمّن؟"
    )


def _outer(facts: dict) -> str:
    venus_e = _element(facts, "venus")
    mars_e = _element(facts, "mars")
    return (
        f"في العلاقات، زهرتك تميل إلى {VENUS_LOVE[venus_e]} "
        f"أما مريخك فيخرج عند الاحتكاك بـ{MARS_ANGER[mars_e]} "
        "الفرق بين ما تحتاجه وما تُظهره هو غالبًا مساحة سوء الفهم. "
        "قل احتياجك قبل أن تختبره بالصمت."
    )


def _shadow(facts: dict) -> str:
    saturn_e = _element(facts, "saturn")
    return (
        "الظل هنا ليس عيبًا؛ إنه الطريقة التي تحمي بها نفسك من ألم قديم. "
        f"{SATURN_FEAR[saturn_e]} "
        "راقب اللحظة التي تنسحب فيها قبل أن تشرح، أو التي تشرح فيها أكثر من "
        "حاجتك. كلاهما محاولة للسيطرة على ألم لا يحتاج سيطرة، بل حضورًا."
    )


def _current(facts: dict) -> str:
    transits = _future_transits(facts)
    if not transits:
        return "لا توجد إشارات عبور قوية في هذه الفترة؛ استخدم الهدوء لترتيب أولوياتك."
    lines = [_transit_line(row) for row in transits[:3]]
    return "\n".join(f"- {line}" for line in lines)


def _gift(facts: dict) -> str:
    sun_e = _element(facts, "sun")
    gifts = {
        "fire": "قدرتك على بدء ما يخافه الآخرون، وإشعال حركة في مكان ساكن.",
        "earth": "قدرتك على تحويل النية إلى واقع صغير ملموس، مرة بعد مرة.",
        "air": "قدرتك على رؤية العلاقة بين الأشياء وصياغة ما يعجز عنه غيرك.",
        "water": "قدرتك على احتواء ما لا يُقال، ومنح الآخر إحساسًا بأنه مرئي.",
    }
    return gifts[sun_e]


def _closing(facts: dict) -> str:
    return (
        "لا تحتاج أن تحل نفسك اليوم. اختر جملة واحدة صادقة تقولها لشخص آمن، "
        "وخطوة واحدة صغيرة تثبت أنك تسمع نفسك. التغيير الحقيقي غالبًا بهذا الحجم."
    )


def _aspects_note(facts: dict) -> str:
    aspects = facts.get("profile", {}).get("aspects", [])
    if not aspects:
        return ""
    rows = []
    for aspect in aspects[:4]:
        rows.append(
            f"- {aspect.get('a')} و{aspect.get('b')} في {aspect.get('aspect')} "
            f"(orb {aspect.get('orb')})"
        )
    return "\n".join(rows)


def build_fallback_story(facts: dict, mode: str) -> str:
    profile = facts.get("profile", {})
    name = profile.get("name") or "هذه الخريطة"
    parts: list[str] = [f"# قراءة {name} — {facts.get('as_of', '')}"]

    if profile.get("sign_only"):
        parts.append(
            "> هذه قراءة على مستوى الأبراج والبيوت المقدمة يدويًا. "
            "الدرجات الدقيقة والتوقيت اليومي ليسا متاحين، لذلك اقرأها كخريطة رمزية لا كتنبؤ."
        )

    parts.append("## المفتاح\n" + _opening(facts))

    if mode == "short":
        parts.append("## طاقة اليوم\n" + _current(facts))
        parts.append("## خطوة واحدة\n" + _closing(facts))
        return "\n\n".join(parts).strip() + "\n"

    parts.append("## العالم الداخلي\n" + _inner(facts))
    parts.append("## العالم الخارجي\n" + _outer(facts))
    parts.append("## الظل\n" + _shadow(facts))
    parts.append("## طاقة اليوم\n" + _current(facts))
    parts.append("## الهدية\n" + _gift(facts))

    if mode == "deep":
        parts.append(
            "## تأمل أعمق\n"
            "الخريطة لا تقول من أنت؛ إنها تصف اللغة التي تعودت أن تحكي بها عن نفسك. "
            "لاحظ أين تكرر نفس السيناريو بأسماء مختلفة: شخص يطلب منك وضوحًا، "
            "موقف يشعرك أنك غير مرئي، أو لحظة تنسحب فيها قبل أن تشرح. "
            "الوعي بهذا النمط لا يلغيه فورًا، لكنه يمنحك خيارًا صغيرًا في المرة القادمة."
        )
        aspects = _aspects_note(facts)
        if aspects:
            parts.append("## حوار الخريطة\n" + aspects)
        moon_changes = facts.get("moon_changes", [])
        if moon_changes:
            moon_lines = [
                f"- {row.get('date')} {row.get('time')} → {row.get('sign')}"
                for row in moon_changes[:6]
            ]
            parts.append("## إيقاع القمر\n" + "\n".join(moon_lines))

    parts.append("## الرسالة\n" + _closing(facts))
    return "\n\n".join(parts).strip() + "\n"


def generate_reading(
    context,
    data,
    *,
    mode: str = "standard",
    use_ai: bool = True,
    model: str | None = None,
    transport=None,
) -> str:
    facts = build_reading_facts(context, data, mode)
    if use_ai and os.environ.get(ENV_KEY, "").strip():
        try:
            return chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(facts, mode)},
                ],
                model=model,
                transport=transport,
            )
        except OpenRouterError as exc:
            print(f"warning: OpenRouter fallback: {exc}", file=sys.stderr)
    text = build_fallback_story(facts, mode)
    if use_ai:
        text += (
            "\n\n> قراءة محلية مبنية على القواعد. "
            "أضف `OPENROUTER_API_KEY` لتفعيل السرد التوليدي عبر OpenRouter."
        )
    return text
