from __future__ import annotations

from pathlib import Path

import pytest

from renderscript import pdf_guide


def test_strict_pdf_mode_raises_when_playwright_render_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pdf_guide.STRICT_PDF_ENV, "1")
    monkeypatch.setattr(pdf_guide, "_render_html", lambda **_: "<html><body>ok</body></html>")

    def fail_renderer(*args, **kwargs):
        raise RuntimeError("renderer failed")

    monkeypatch.setattr(pdf_guide, "_render_with_playwright", fail_renderer)

    with pytest.raises(RuntimeError):
        pdf_guide.render_creator_guide_pdf(
            prompt_path="prompts/shot_prompts.md",
            asset_prompts_path="prompts/asset_prompts.md",
            provider="universal",
            version="0.1.0",
            logo_path=Path("assets/branding/renderscript_logo_mark_blue_pad5.png"),
            scene_heading="",
            scene_id="scene_001",
            shot_count=8,
        )


def test_fallback_records_playwright_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(pdf_guide.STRICT_PDF_ENV, raising=False)
    monkeypatch.setattr(pdf_guide, "_render_html", lambda **_: "<html><body>ok</body></html>")

    def no_playwright(*args, **kwargs):
        raise RuntimeError("playwright unavailable")

    monkeypatch.setattr(pdf_guide, "_render_with_playwright", no_playwright)

    result = pdf_guide.render_creator_guide_pdf(
        prompt_path="prompts/shot_prompts.md",
        asset_prompts_path="prompts/asset_prompts.md",
        provider="universal",
        version="0.1.0",
        logo_path=Path("assets/branding/renderscript_logo_mark_blue_pad5.png"),
        scene_heading="",
        scene_id="scene_001",
        shot_count=8,
    )

    assert result.renderer_used == "fallback"
    assert "Playwright render failed" in result.error
    assert "Playwright render failed" in result.debug_text
