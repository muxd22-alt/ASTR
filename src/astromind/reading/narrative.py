"""Derive the central story spine without exposing a placement inventory.

The reader already knows their chart. The narrative layer uses the chart as
hidden scaffolding, so the prompt receives a story-facing brief rather than a
list of placements to recite.
"""

from __future__ import annotations

from astromind.generators.interpretations import MARS_ANGER, VENUS_LOVE

PAIR_TENSION = {
    ("water", "fire"): (
        "تحتاج أن تشعر بالانتماء والدفء، لكن غريزة أخرى ترفض الانتظار "
        "وتريد أن تتحرك الآن."
    ),
    ("water", "earth"): (
        "تبحث عن قرب عاطفي، لكنك تثق فقط بما يُبنى ويُثبت بالأفعال."
    ),
    ("water", "air"): (
        "تبحث عن دفء قريب، لكنك تعالجه بالكلام والمسافة قبل أن تسمح به."
    ),
    ("water", "water"): (
        "تعيش المشاعر بعمق، وقد يغرقك ما لا تقوله قبل أن تجد له كلمات."
    ),
    ("fire", "water"): (
        "تندفع نحو الحياة، لكن قلبك يحتاج طمأنينة قبل أن يستمر."
    ),
    ("fire", "earth"): (
        "تريد الحركة والتجربة، لكن جزءًا منك يطلب نتيجة ملموسة قبل أن يثق."
    ),
    ("fire", "air"): (
        "تشعل الفكرة بسرعة، ثم تحتاج حوارًا ومساحة لتستمر."
    ),
    ("fire", "fire"): (
        "طاقتك عالية، لكنك قد تستهلك نفسك في اندفاع لا يعرف التوقف."
    ),
    ("earth", "water"): (
        "تبني الأمان بالخطوات، لكنك تشعر أكثر مما تعترف."
    ),
    ("earth", "fire"): (
        "تريد الثبات، لكن حماسك يدفعك لتغيير الخطة قبل أن تكتمل."
    ),
    ("earth", "air"): (
        "تثق بالأفعال، لكن عقلك يريد أن يفهم لماذا قبل أن يلتزم."
    ),
    ("earth", "earth"): (
        "تصبر وتتحمل، لكنك قد تبقى في مكان لم يعد يناسبك خوفًا من الفوضى."
    ),
    ("air", "water"): (
        "تعالج كل شيء بالكلام، لكن قلبك يحتاج حضورًا لا تفسيرًا."
    ),
    ("air", "fire"): (
        "تريد الحرية والنقاش، لكنك تنفد صبرًا حين يتأخر القرار."
    ),
    ("air", "earth"): (
        "تفكر بسرعة، لكنك تحتاج نتيجة ملموسة لتطمئن."
    ),
    ("air", "air"): (
        "تتنقل بين الأفكار بسهولة، لكنك قد تهرب من العمق بالانشغال."
    ),
}

MOON_NEED_SELF = {
    "fire": "أن يُرى ويُشجّع، وأن يجد مساحة للحركة قبل أن يُطلب منه الهدوء.",
    "earth": "وعدًا صغيرًا يُنفَّذ، وروتينًا يثبت أنك لست مضطرًا للدفاع عن نفسك.",
    "air": "كلامًا صريحًا ومساحة للتنفس، لا تخمينًا ولا مطاردة.",
    "water": "حضورًا هادئًا قبل الحل، واحتواءً قبل النصيحة.",
}

ASC_STYLE = {
    "fire": "تدخل المشهد مباشرة وتجعل الآخرين يرون المبادرة قبل أن يروا التردد.",
    "earth": "تظهر هادئًا وعمليًا، وتثق بما يُبنى لا بما يُقال.",
    "air": "تظهر خفيفًا واجتماعيًا، وتفتح الأبواب بالكلام.",
    "water": "تظهر متحفظًا ثم تكشف عمقك لمن يربح ثقتك.",
}

SHADOW_SELF = {
    "fire": "قد تخشى أن يطفئ الالتزام حماسك، فتهرب من القرار قبل أن يبدأ.",
    "earth": "قد تخشى الفوضى، فتحاول السيطرة على ما لا يحتاج سيطرة.",
    "air": "قد تخشى أن تُفهم خطأً، فتشرح أكثر من حاجتك أو تنسحب إلى الكلام.",
    "water": "قد تخشى الهجر أو الجفاف العاطفي، فتختبر الحضور بالصمت.",
}

GIFT_SELF = {
    "fire": "قدرتك على البدء وإشعال حركة في مكان ساكن.",
    "earth": "قدرتك على تحويل النية إلى واقع صغير ملموس.",
    "air": "قدرتك على ربط ما لا يراه الآخرون وصياغته بكلمات.",
    "water": "قدرتك على احتواء ما لا يُقال ومنح الآخر إحساسًا بأنه مرئي.",
}


def _element(placements: dict, body: str) -> str:
    return str(placements.get(body, {}).get("element_key") or "water")


def build_story_spine(profile_facts: dict) -> dict[str, str]:
    placements = profile_facts.get("placements", {})
    sun = _element(placements, "sun")
    moon = _element(placements, "moon")
    asc = _element(placements, "asc")
    venus = _element(placements, "venus")
    mars = _element(placements, "mars")
    saturn = _element(placements, "saturn")

    return {
        "core_tension": PAIR_TENSION.get(
            (sun, moon),
            "هناك حاجتان مختلفتان تتحركان فيك في الوقت نفسه، وكل واحدة تريد أن تُسمع.",
        ),
        "core_need": MOON_NEED_SELF[moon],
        "outer_style": ASC_STYLE[asc],
        "relationship_pattern": (
            f"{VENUS_LOVE[venus]} وعند الاحتكاك: {MARS_ANGER[mars]}"
        ),
        "shadow": SHADOW_SELF[saturn],
        "gift": GIFT_SELF[sun],
        "instruction": (
            "هذه هي السالفة الأساسية. اكتب عنها دون سرد المواضع أو الأبراج أو البيوت. "
            "القارئ يعرف خريطته؛ لا تكررها عليه."
        ),
    }
