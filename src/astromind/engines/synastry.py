"""Synastry: cross-chart aspects and relationship dynamics."""

from __future__ import annotations

from dataclasses import dataclass

from astromind.engines.aspects import allowed_orb, detect_aspect, is_hard, is_soft
from astromind.engines.charts import Chart
from astromind.engines.ephemeris import BODY_WEIGHT, TARGET_WEIGHT
from astromind.engines.transits import sign_aspect
from astromind.i18n import BODIES_AR, element_ar, sign_element, sign_of


@dataclass(frozen=True)
class SynastryAspect:
    a_body: str
    b_body: str
    aspect: str
    orb: float
    limit: float
    score: float
    polarity: str
    a_is_angle: bool = False
    b_is_angle: bool = False

    @property
    def key(self) -> str:
        return f"{self.a_body}|{self.b_body}|{self.aspect}"


def _polarity(a_body: str, b_body: str, aspect: str) -> str:
    if is_soft(aspect):
        if a_body in {"venus", "jupiter"} or b_body in {"venus", "jupiter"}:
            return "opportunity"
        return "support"
    if is_hard(aspect):
        return "friction"
    if a_body in {"saturn", "mars", "pluto", "uranus"} or b_body in {
        "saturn",
        "mars",
        "pluto",
        "uranus",
    }:
        return "friction"
    if a_body in {"venus", "jupiter"} or b_body in {"venus", "jupiter"}:
        return "opportunity"
    return "info"


def compute_synastry(chart_a: Chart, chart_b: Chart) -> list[SynastryAspect]:
    points_a = chart_a.points()
    points_b = chart_b.points()
    aspects: list[SynastryAspect] = []

    for a_body, a_lon in points_a.items():
        for b_body, b_lon in points_b.items():
            if a_body in {"asc", "mc", "dsc", "ic"} and b_body in {
                "asc",
                "mc",
                "dsc",
                "ic",
            }:
                if a_body == b_body:
                    continue
            if chart_a.sign_only or chart_b.sign_only:
                match = sign_aspect(sign_of(a_lon), sign_of(b_lon))
                if match is None:
                    continue
                aspect, weight = match
                polarity = _polarity(a_body, b_body, aspect)
                score = (
                    BODY_WEIGHT.get(a_body, 1.0)
                    * TARGET_WEIGHT.get(b_body, 1.0)
                    * weight
                    * 10.0
                )
                aspects.append(
                    SynastryAspect(
                        a_body=a_body,
                        b_body=b_body,
                        aspect=aspect,
                        orb=0.0,
                        limit=1.0,
                        score=round(score, 3),
                        polarity=polarity,
                        a_is_angle=a_body in {"asc", "mc", "dsc", "ic"},
                        b_is_angle=b_body in {"asc", "mc", "dsc", "ic"},
                    )
                )
                continue

            limit = allowed_orb(a_body, b_body)
            hit = detect_aspect(a_lon, b_lon, limit, include_minor=True)
            if hit is None:
                continue
            polarity = _polarity(a_body, b_body, hit.aspect)
            tightness = max(0.05, 1.0 - hit.orb / hit.limit)
            score = (
                BODY_WEIGHT.get(a_body, 1.0)
                * TARGET_WEIGHT.get(b_body, 1.0)
                * hit.weight
                * tightness
                * 10.0
            )
            aspects.append(
                SynastryAspect(
                    a_body=a_body,
                    b_body=b_body,
                    aspect=hit.aspect,
                    orb=round(hit.orb, 2),
                    limit=round(hit.limit, 2),
                    score=round(score, 3),
                    polarity=polarity,
                    a_is_angle=a_body in {"asc", "mc", "dsc", "ic"},
                    b_is_angle=b_body in {"asc", "mc", "dsc", "ic"},
                )
            )

    return sorted(aspects, key=lambda item: item.score, reverse=True)


def top_ease(aspects: list[SynastryAspect], limit: int = 5) -> list[SynastryAspect]:
    return [
        item
        for item in aspects
        if item.polarity in {"support", "opportunity"}
    ][:limit]


def top_friction(aspects: list[SynastryAspect], limit: int = 5) -> list[SynastryAspect]:
    return [item for item in aspects if item.polarity == "friction"][:limit]


def element_compatibility(chart_a: Chart, chart_b: Chart) -> str:
    moon_a = chart_a.body("moon")
    moon_b = chart_b.body("moon")
    if moon_a is None or moon_b is None:
        return "تعذّر تقييم توافق العناصر لغياب القمر."
    ea, eb = sign_element(moon_a.sign), sign_element(moon_b.sign)
    if ea == eb:
        return (
            f"كلاكما بقمر {element_ar(ea)}: تفهمان الاحتياج نفسه، "
            "لكن قد تفتقدان التنويع."
        )
    if {ea, eb} == {"fire", "air"}:
        return "نار + هواء: حركة وحوار، تحتاجان إلى تثبيت عملي حتى لا يتبدد الحماس."
    if {ea, eb} == {"fire", "earth"}:
        return "نار + تراب: حماس مقابل ثبات. اتفقا على خطوة صغيرة قابلة للتنفيذ قبل التوسع."
    if {ea, eb} == {"earth", "water"}:
        return "تراب + ماء: أمان ورعاية، تحتاجان إلى كلام صريح حتى لا يتحول الصمت إلى افتراض."
    if {ea, eb} == {"fire", "water"}:
        return "نار + ماء: دفء وحساسية، تحتاجان إلى تخفيف حدة الافتتاح."
    if {ea, eb} == {"air", "earth"}:
        return "هواء + تراب: أفكار مقابل تفاصيل، تحتاجان إلى ترجمة الكلام إلى خطوة."
    return "العناصر مختلفة: الاختلاف مصدر نمو إذا سُمّي بوضوح، ومصدر سوء فهم إذا تُرك مُبهمًا."


def describe_aspect(aspect: SynastryAspect, a_name: str, b_name: str) -> str:
    a = BODIES_AR.get(aspect.a_body, aspect.a_body)
    b = BODIES_AR.get(aspect.b_body, aspect.b_body)
    return (
        f"- **{a} عند {a_name} × {b} عند {b_name}** — {aspect.aspect} "
        f"(orb {aspect.orb}°): {aspect.polarity}"
    )
