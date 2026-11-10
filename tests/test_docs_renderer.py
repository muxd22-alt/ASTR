from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

from astromind.cli import build_context
from astromind.profiles import load_bundle

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_docs", ROOT / "scripts" / "build_docs.py")
assert SPEC and SPEC.loader
BUILD_DOCS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD_DOCS)


def test_bold_title_and_horizontal_rule_render_as_story_heading() -> None:
    html = BUILD_DOCS.markdown_to_html(
        "**قراءة لِنفسك — 10 نوفمبر 2026**\n\n---\n\n### افتتاحية\n\nنص."
    )
    assert '<h1 class="reading-title">قراءة لِنفسك — 10 نوفمبر 2026</h1>' in html
    assert '<hr class="reading-divider">' in html
    assert "<h3>افتتاحية</h3>" in html
    assert "<p><strong>" not in html


def test_hash_title_still_renders() -> None:
    html = BUILD_DOCS.markdown_to_html("# عنوان\n\n## قسم\n\nنص.")
    assert "<h1>عنوان</h1>" in html
    assert "<h2>قسم</h2>" in html


def test_apple_bento_and_ten_books_render_in_full_page() -> None:
    bundle = load_bundle(ROOT / "profiles" / "profiles.example.json")
    context = build_context(bundle)
    page = BUILD_DOCS.build_page(
        bundle,
        context,
        date(2026, 11, 10),
        use_ai=False,
    )
    # Apple Bento & Frosted Glass visual identity
    assert "floating-pill-nav" in page
    assert "backdrop-filter: saturate(180%) blur(28px)" in page
    assert "--bento-radius: 25px" in page
    assert "#0A84FF" in page
    assert "#FF9F0A" in page
    assert "#30D158" in page
    assert "#FF453A" in page
    assert "Pro Dark Titanium" in page
    assert "Apple Daylight Silver" in page
    assert "redrawAllCharts" in page
    # 10 Foundational Books
    for book_title in (
        "Astrology and the Authentic Self",
        "Astrology of Fate",
        "The Anthology",
        "Horoscope Symbols",
        "A Tiny Universe",
        "Hellenistic Astrology",
        "The Lunation Cycle",
        "Predictive Astrology: The Eagle and the Lark",
        "The Complete Astrological Writings",
        "Ancient Astrology in Theory and Practice Vol. 1 &amp; 2",
    ):
        assert book_title in page
