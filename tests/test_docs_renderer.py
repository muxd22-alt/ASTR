from __future__ import annotations

import importlib.util
from pathlib import Path

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
