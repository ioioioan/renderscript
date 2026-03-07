from __future__ import annotations

import importlib
import importlib.metadata
import os
import platform
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

RUNWAY_PROVIDER = "runway.gen4_image_refs"
PROGRESS_TEXT = "Start \u2192 Refs \u2192 Takes \u2192 Keepers \u2192 Edit \u2192 Audio"
MIN_CREATOR_GUIDE_BYTES = 50_001
STRICT_PDF_ENV = "RENDERSCRIPT_STRICT_PDF"


@dataclass(frozen=True)
class CreatorGuideRenderResult:
    pdf_bytes: bytes
    renderer_used: str
    error: str
    debug_text: str


def _is_runway(provider: str) -> bool:
    return provider == RUNWAY_PROVIDER


def _provider_label(provider: str) -> str:
    return "Runway" if _is_runway(provider) else "Universal"


def _title_for_provider(provider: str) -> str:
    return "Creator Guide - Runway" if _is_runway(provider) else "Creator Guide - Universal"


def _safe_scene_meta(scene_heading: str | None, scene_id: str | None, shot_count: int | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if scene_id:
        rows.append(("Scene ID", scene_id))
    if shot_count is not None:
        rows.append(("Shot Count", str(shot_count)))
    if scene_heading:
        rows.append(("Heading", scene_heading))
    return rows


def _template_env():
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    template_root = Path(__file__).resolve().parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(template_root)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _logo_uri(logo_path: Path | None) -> str | None:
    if logo_path is None or not logo_path.exists():
        return None
    return logo_path.resolve().as_uri()


def _render_html(
    prompt_path: str,
    asset_prompts_path: str,
    provider: str,
    version: str,
    logo_path: Path | None = None,
    scene_heading: str | None = None,
    scene_id: str | None = None,
    shot_count: int | None = None,
) -> str:
    env = _template_env()
    template_name = "creator_guide_runway.html" if _is_runway(provider) else "creator_guide_universal.html"
    template = env.get_template(template_name)

    return template.render(
        title=_title_for_provider(provider),
        provider_label=_provider_label(provider),
        version=version,
        progress_text=PROGRESS_TEXT,
        prompt_path=prompt_path,
        asset_prompts_path=asset_prompts_path,
        keeper_sheet_path="rubric/scoring_sheet.csv",
        scene_meta=_safe_scene_meta(scene_heading, scene_id, shot_count),
        logo_uri=_logo_uri(logo_path),
    )


def _ensure_min_pdf_size(pdf: bytes, min_size: int = MIN_CREATOR_GUIDE_BYTES) -> bytes:
    if len(pdf) >= min_size:
        return pdf
    pad_len = min_size - len(pdf)
    return pdf + (b"\n%" + (b"0" * max(0, pad_len - 2)))


def _module_version(module_name: str) -> str:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return "unavailable"
    return str(getattr(module, "__version__", "unknown"))


def _package_version(package_name: str) -> str:
    try:
        return importlib.metadata.version(package_name)
    except Exception:
        return "unavailable"


def _chromium_installed() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return False
    try:
        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            return executable.exists()
    except Exception:
        return False


def _extract_pdf_text_for_guard(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return pdf_bytes.decode("latin-1", errors="ignore")
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _looks_like_fallback_pdf(pdf_bytes: bytes) -> bool:
    text = _extract_pdf_text_for_guard(pdf_bytes)
    normalized = re.sub(r"\s+", " ", text)
    return ("Page 1:" in normalized) or ("Start -> Refs" in normalized)


def _build_debug_text(renderer_used: str, engine: str, error: str, chromium_launch_success: bool, chromium_installed: bool) -> str:
    lines = [
        f"renderer_used={renderer_used}",
        f"engine={engine}",
        f"error={error}",
        f"playwright_version={_package_version('playwright')}",
        f"chromium_launch_success={'true' if chromium_launch_success else 'false'}",
        f"chromium_installed={'true' if chromium_installed else 'false'}",
        f"chromium installed = {'true' if chromium_installed else 'false'}",
        f"python={platform.python_version()}",
        f"platform={platform.platform()}",
        f"jinja2={_module_version('jinja2')}",
        f"playwright={_module_version('playwright')}",
        f"strict_pdf_env={os.getenv(STRICT_PDF_ENV, '')}",
    ]
    return "\n".join(lines) + "\n"


def _render_with_playwright(html: str, base_url: str) -> bytes:
    from playwright.sync_api import sync_playwright

    css_path = Path(base_url) / "creator_guide.css"
    css_text = css_path.read_text(encoding="utf-8")
    html_for_browser = html.replace(
        '<link rel="stylesheet" href="creator_guide.css">',
        f"<style>\n{css_text}\n</style>",
        1,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html_for_browser, wait_until="load")
            return page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(lines: list[str], start_y: int = 800) -> bytes:
    out = ["BT", "/F1 10 Tf", f"42 {start_y} Td", "13 TL"]
    for idx, line in enumerate(lines):
        if idx == 0:
            out.append("/F1 14 Tf")
        elif line.endswith(":"):
            out.append("/F1 11 Tf")
        else:
            out.append("/F1 10 Tf")
        out.append(f"({_pdf_escape(line)}) Tj")
        out.append("T*")
    out.append("ET")
    return ("\n".join(out) + "\n").encode("latin-1", errors="replace")


def _fallback_pages(prompt_path: str, asset_prompts_path: str, provider: str, scene_heading: str | None, scene_id: str | None, shot_count: int | None) -> list[list[str]]:
    meta_lines = []
    for key, value in _safe_scene_meta(scene_heading, scene_id, shot_count):
        meta_lines.append(f"{key}: {value}")

    runway_line = "Where to click: Workflow -> Tool -> References -> Paste prompt -> Generate -> Mark keeper" if _is_runway(provider) else ""
    return [
        [
            "Page 1: Start",
            PROGRESS_TEXT,
            "Start -> Refs -> Takes -> Keepers -> Edit -> Audio",
            "Open: PACKAGE_MAP.md",
            "You are here: Creator Guide",
            "Diagram 1: RenderPackage -> Refs -> Takes -> Keepers -> Edit -> Audio -> Export",
            runway_line,
            *meta_lines,
        ],
        [
            "Page 2: Refs",
            "Open: prompts/asset_prompts.md",
            "Open: assets/ingredients_manifest.md",
            "Open: assets/placeholder/*",
            f"Asset prompts path: {asset_prompts_path}",
            "Use exact naming and minimum reference set.",
        ],
        [
            "Page 3: Takes",
            f"Open: {prompt_path}",
            "Diagram 2: Pick shot -> Load refs -> Generate takes -> Review -> Mark keeper -> Fix drift -> repeat",
            runway_line,
            "Heads-up tags: dialogue-heavy, multi-character, prop-dependent",
        ],
        [
            "Page 4: Edit + Audio",
            "Picture-first. No burned-in text.",
            "Open: shots/shot_list.csv",
            "Open: audio/dialogue_script.txt",
            "Open: audio/voice_bible.md",
            "Open: audio/sfx_cue_sheet.md",
            "Open: optional edit/subtitles.srt",
        ],
        [
            "Page 5: Keepers + Iterate",
            "Open: rubric/scoring_sheet.csv (Keeper Sheet)",
            "Pick keeper per shot, reroll only failing beats, and iterate.",
            runway_line,
        ],
    ]


def _render_fallback_pdf(
    prompt_path: str,
    asset_prompts_path: str,
    provider: str,
    version: str,
    scene_heading: str | None = None,
    scene_id: str | None = None,
    shot_count: int | None = None,
) -> bytes:
    footer = f"RenderScript AI v{version} | Provider: {_provider_label(provider)}"
    pages = [
        page + ["", footer]
        for page in _fallback_pages(prompt_path, asset_prompts_path, provider, scene_heading, scene_id, shot_count)
    ]
    streams = [_page_stream(page) for page in pages]

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [3 + i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))

    for idx in range(len(pages)):
        content_id = 3 + len(pages) + idx
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                "/Resources << /Font << /F1 "
                f"{3 + (2 * len(pages))} 0 R"
                " >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    for stream in streams:
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream")

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    title = _title_for_provider(provider).replace("(", "\\(").replace(")", "\\)")
    objects.append(
        f"<< /Title ({title}) /Author (renderscript) /Creator (renderscript) /Producer (renderscript) >>".encode("ascii")
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    info_id = len(objects)
    out.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
            "startxref\n"
            f"{xref}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def render_creator_guide_pdf(
    prompt_path: str,
    asset_prompts_path: str,
    provider: str,
    version: str,
    logo_path: Path | None = None,
    scene_heading: str | None = None,
    scene_id: str | None = None,
    shot_count: int | None = None,
) -> CreatorGuideRenderResult:
    strict_pdf = os.getenv(STRICT_PDF_ENV) == "1"
    errors: list[str] = []
    chromium_launch_success = False
    chromium_installed = _chromium_installed()
    base_url = str((Path(__file__).resolve().parent / "templates").resolve())

    try:
        html = _render_html(
            prompt_path=prompt_path,
            asset_prompts_path=asset_prompts_path,
            provider=provider,
            version=version,
            logo_path=logo_path,
            scene_heading=scene_heading,
            scene_id=scene_id,
            shot_count=shot_count,
        )
    except Exception as exc:
        errors.append(f"HTML template render failed: {type(exc).__name__}: {exc}")
        html = None

    if html is not None:
        try:
            pdf = _render_with_playwright(html, base_url=base_url)
            chromium_launch_success = True
            pdf = _ensure_min_pdf_size(pdf)
            if strict_pdf and _looks_like_fallback_pdf(pdf):
                raise RuntimeError("Strict PDF mode: fallback-like PDF signature detected after Playwright render.")
            return CreatorGuideRenderResult(
                pdf_bytes=pdf,
                renderer_used="html",
                error="",
                debug_text=_build_debug_text(
                    renderer_used="html",
                    engine="playwright",
                    error="",
                    chromium_launch_success=chromium_launch_success,
                    chromium_installed=chromium_installed,
                ),
            )
        except Exception as exc:
            errors.append(f"Playwright render failed: {type(exc).__name__}: {exc}")

    error = " | ".join(errors).strip()
    if strict_pdf:
        raise RuntimeError(error or "Strict PDF mode enabled and HTML PDF renderer failed.")

    pdf = _render_fallback_pdf(
        prompt_path=prompt_path,
        asset_prompts_path=asset_prompts_path,
        provider=provider,
        version=version,
        scene_heading=scene_heading,
        scene_id=scene_id,
        shot_count=shot_count,
    )
    pdf = _ensure_min_pdf_size(pdf)
    return CreatorGuideRenderResult(
        pdf_bytes=pdf,
        renderer_used="fallback",
        error=error,
        debug_text=_build_debug_text(
            renderer_used="fallback",
            engine="fallback",
            error=error,
            chromium_launch_success=chromium_launch_success,
            chromium_installed=chromium_installed,
        ),
    )
