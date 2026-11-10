"""Generate an intuitive astrology reading with a local fallback.

The deterministic chart facts are always built first. The optional provider
only rewrites those facts into prose; it cannot add or change placements.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import date

from astromind.i18n import SIGNS_AR, format_date_short
from astromind.reading.facts import build_reading_facts
from astromind.reading.openrouter import ENV_KEY, OpenRouterError, chat
from astromind.reading.prompts import SYSTEM_PROMPT, build_user_prompt

PLACEMENT_INVENTORY = re.compile(r"في\s+البيت")


def _spine(facts: dict) -> dict:
    return facts.get("profile", {}).get("story_spine", {})


def _future_transits(facts: dict) -> list[dict]:
    return [row for row in facts.get("transits", []) if row.get("date")]


def _transit_line(row: dict) -> str:
    when = format_date_short(date.fromisoformat(row["date"]))
    return f"{when}: {row.get('line', '')} — {row.get('action', '')}"


def _sanitize_signs(text: str) -> str:
    """Ensure fallback prose never recites raw zodiac sign names."""
    cleaned = text
    for sign in SIGNS_AR:
        cleaned = cleaned.replace(sign, "هذا المسار")
    cleaned = PLACEMENT_INVENTORY.sub("في هذا المحور", cleaned)
    return cleaned


def _opening(facts: dict) -> str:
    spine = _spine(facts)
    lunation_rhythm = spine.get("lunation_rhythm", "")
    extra = f" {lunation_rhythm}" if lunation_rhythm else ""
    return (
        f"{spine.get('core_tension', '')} "
        f"{spine.get('outer_style', '')}{extra} "
        "القراءة هنا تجمع بين حكمة المدرسة الكلاسيكية وعمق التحليل النفسي لتمنحك بوصلة خفيفة وعملية ليومك."
    ).strip()


def _inner(facts: dict) -> str:
    spine = _spine(facts)
    sect_wisdom = spine.get("sect_wisdom", "")
    return (
        f"احتياجك العاطفي الأساسي: {spine.get('core_need', '')} "
        f"{sect_wisdom} "
        "حين تهدأ، اسأل نفسك: هل أعبّر عن حاجتي للأمان بلغة مباشرة يفهمها من حولي، "
        "أم أنتظر أن يلتقطوا الإشارة وحدهم؟"
    ).strip()


def _outer(facts: dict) -> str:
    spine = _spine(facts)
    annual = spine.get("annual_theme", "")
    return (
        f"{spine.get('relationship_pattern', '')} "
        f"{annual} "
        "الفرق بين ما تحتاجه في داخلك وما تُظهره للخارج هو المساحة التي تحتاج منك كلمة واضحة ومبادرة هادئة."
    ).strip()


def _domains_summary(facts: dict) -> str:
    domains = facts.get("profile", {}).get("life_domains", [])
    if not domains:
        return ""
    lines: list[str] = []
    for item in domains:
        title = item.get("title_ar", "")
        badge = item.get("badge_ar", "")
        action = _sanitize_signs(str(item.get("action", "")))
        avoid = _sanitize_signs(str(item.get("avoid", "")))
        lines.append(
            f"- **{title} ({badge}):** افعل: {action} | تجنّب: {avoid}"
        )
    return "\n".join(lines)


def _shadow(facts: dict) -> str:
    spine = _spine(facts)
    return (
        "الظل هنا ليس عيبًا؛ إنه الطريقة التي تحمي بها نفسك من ألم قديم. "
        f"{spine.get('shadow', '')} "
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
    spine = _spine(facts)
    return spine.get("gift", "قدرتك على الصبر والملاحظة قبل أن تتحرك.")


def _closing(facts: dict) -> str:
    return (
        "لا تحتاج أن تحل نفسك اليوم. اختر جملة واحدة صادقة تقولها لشخص آمن، "
        "وخطوة واحدة صغيرة تثبت أنك تسمع نفسك. التغيير الحقيقي غالبًا بهذا الحجم."
    )


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
    domains_block = _domains_summary(facts)
    if domains_block:
        parts.append("## بوصلة النواحي العملية\n" + domains_block)
    parts.append("## الهدية\n" + _gift(facts))

    if mode == "deep":
        parts.append(
            "## تأمل أعمق\n"
            "الخريطة لا تقول من أنت؛ إنها تصف اللغة التي تعودت أن تحكي بها عن نفسك. "
            "لاحظ أين تكرر نفس السيناريو بأسماء مختلفة: شخص يطلب منك وضوحًا، "
            "موقف يشعرك أنك غير مرئي، أو لحظة تنسحب فيها قبل أن تشرح. "
            "الوعي بهذا النمط لا يلغيه فورًا، لكنه يمنحك خيارًا صغيرًا في المرة القادمة."
        )
        moon_changes = facts.get("moon_changes", [])
        if moon_changes:
            moon_lines = [
                f"- {row.get('date')} {row.get('time')} → {row.get('sign')}"
                for row in moon_changes[:6]
            ]
            parts.append("## إيقاع القمر\n" + "\n".join(moon_lines))

    parts.append("## الرسالة\n" + _closing(facts))
    if mode != "deep":
        return _sanitize_signs("\n\n".join(parts).strip()) + "\n"
    return "\n\n".join(parts).strip() + "\n"


def _recites_placements(text: str) -> bool:
    if PLACEMENT_INVENTORY.search(text):
        return True
    return any(sign in text for sign in SIGNS_AR)


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
            text = chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(facts, mode)},
                ],
                model=model,
                transport=transport,
            )
            if not any("\u0600" <= char <= "\u06FF" for char in text):
                raise OpenRouterError("provider returned a non-Arabic reading")
            if _recites_placements(text):
                raise OpenRouterError("provider recited placements instead of the story")
            return text
        except OpenRouterError as exc:
            print(f"warning: OpenRouter fallback: {exc}", file=sys.stderr)
    text = build_fallback_story(facts, mode)
    if use_ai:
        text += (
            "\n\n> قراءة محلية مبنية على القواعد. "
            "أضف `OPENROUTER_API_KEY` لتفعيل السرد التوليدي عبر OpenRouter."
        )
    return text
