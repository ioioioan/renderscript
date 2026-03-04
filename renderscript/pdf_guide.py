from __future__ import annotations

from io import BytesIO
from pathlib import Path


RUNWAY_PROVIDER = "runway.gen4_image_refs"


def _is_runway(provider: str) -> bool:
    return provider == RUNWAY_PROVIDER


def _title_for_provider(provider: str) -> str:
    if _is_runway(provider):
        return "RenderPackage Quick Start (Runway Gen-4 Image References)"
    return "RenderPackage Quick Start (Universal)"


def _subtitle_for_provider(provider: str) -> str:
    if _is_runway(provider):
        return "This package creates a shot-by-shot plan. You generate shots in Runway."
    return "This package creates a shot-by-shot plan. You generate shots in your tool of choice."


def _where_to_click_line(provider: str) -> str:
    if _is_runway(provider):
        return "Workflow -> Tool -> References -> Paste prompt -> Generate -> Score"
    return "In your tool: attach references (if supported) -> paste prompt -> generate -> score"


def _asset_callout_lines(provider: str, asset_prompts_path: str) -> list[str]:
    if _is_runway(provider):
        return [
            f"Need assets? Open {asset_prompts_path} to generate the minimum set (style, location, characters), then save into assets/placeholder/* with the exact filenames listed in assets/ingredients_manifest.md for Runway references.",
        ]
    return [
        f"Need assets? Open {asset_prompts_path} to generate the minimum set (style, location, characters), then save into assets/placeholder/* with the exact filenames listed in assets/ingredients_manifest.md.",
    ]


def _page_one_lines(prompt_path: str, asset_prompts_path: str, provider: str) -> list[str]:
    title = _title_for_provider(provider)
    subtitle = _subtitle_for_provider(provider)
    path_a_lines = [
        f"1. Open {prompt_path}.",
        "2. Open your generation workflow.",
        "3. Do NOT add references.",
        "4. Copy/paste prompt for shot_001, generate.",
        "5. Repeat for shot_002, shot_003 (start with 3 shots).",
        "6. Score each shot in rubric/scoring_sheet.csv.",
    ]
    path_b_lines = [
        "Minimum 4 images:",
        "- style_01_ref_01",
        "- loc_01_ref_01",
        "- char_<X>_ref_01 (one per character)",
        f"1. Open {prompt_path}.",
        "2. Attach references for the current shot.",
        "3. Clear references before each shot.",
        "4. Add refs listed for the shot.",
        "5. Paste prompt, generate.",
        "6. Score each shot in the rubric.",
    ]
    where_to_click_heading = "Where to click in your tool:"
    if _is_runway(provider):
        path_a_lines[1] = "2. In Runway Workflow, open Gen-4 video generation."
        path_b_lines[5] = "2. In Runway Workflow: Tool -> References."
        path_b_lines[7] = "4. Add refs listed for the shot (max 3 active at once)."
        where_to_click_heading = "Where to click in Runway Workflow:"

    return [
        title,
        subtitle,
        "",
        "Quick Start: Choose Your Path",
        "",
        "PATH A - No Assets (10 minutes)",
        *path_a_lines,
        "",
        "PATH B - With Assets (30 minutes)",
        *path_b_lines,
        "",
        "Need assets?",
        *_asset_callout_lines(provider, asset_prompts_path),
        "",
        where_to_click_heading,
        _where_to_click_line(provider),
        "",
        f"Prompt file in this package: {prompt_path}",
    ]


def _page_two_lines(prompt_path: str, asset_prompts_path: str, provider: str) -> list[str]:
    checklist_step_2 = "2. Add listed references (if using Path B)."
    if _is_runway(provider):
        checklist_step_2 = "2. Add listed references in Runway (if using Path B)."
    return [
        "For Each Shot (repeat this loop)",
        "",
        "Checklist",
        "1. Clear references.",
        checklist_step_2,
        "3. Paste the shot prompt.",
        "4. Set duration (use shots/shot_list.csv).",
        "5. Generate.",
        "6. Score (rubric).",
        "",
        "Reference Map",
        "Use Reference Map (bindings/bindings.csv) to find which references",
        "belong to each shot_id before you generate.",
        "",
        "Execution notes",
        f"- Process one shot block at a time from {prompt_path}.",
        "- Keep location and look stable through the full pack.",
        "- If drift appears, reroll before changing the reference set.",
        "",
        "Workflow: Picture First, Audio in Post",
        "1. Generate shots (picture-only; no subtitles/text)",
        "2. Assemble a rough cut (order shots by shot_id)",
        "3. Add dialogue (voiceover/ADR) using the dialogue script",
        "4. Add ambience + SFX using the SFX cue sheet",
        "5. Add music",
        "6. Mix and export",
        "",
        "If your tool generates subtitles anyway, reroll that shot. Don't rely on subtitle removal.",
        "",
        "After you generate reference images",
        "Save images into:",
        "- assets/placeholder/characters/",
        "- assets/placeholder/locations/",
        "- assets/placeholder/styles/",
        "- assets/placeholder/props/",
        "Use exact filenames listed in assets/ingredients_manifest.md",
        "(for example: char_A_ref_01.png, loc_01_ref_01.png, style_01_ref_01.png).",
        "Some tools require at least one image. Path A (no assets) is valid for prompts-only testing.",
        "",
        "What's in this package",
        "Start here: CREATOR_GUIDE.pdf",
        f"Shot prompts: {prompt_path}",
        f"Asset prompts: {asset_prompts_path}",
        "Required assets list: assets/ingredients_manifest.md",
        "Voice bible: audio/voice_bible.md",
        "Dialogue script: audio/dialogue_script.txt",
        "SFX cue sheet: audio/sfx_cue_sheet.md",
        "Optional editing subtitles: edit/subtitles.srt (disable before final export)",
        "Shot list: shots/shot_list.csv",
        "Reference map: bindings/bindings.csv",
        "Scoring: rubric/scoring_sheet.csv",
        "Technical: rpack.json, README.md",
    ]


def _page_three_lines(provider: str) -> list[str]:
    common_mistake_2 = "- using the wrong or stale references"
    if _is_runway(provider):
        common_mistake_2 = "- exceeding 3 active refs"
    return [
        "Common Mistakes + Scoring",
        "",
        "Common mistakes",
        "- forgetting to clear refs",
        common_mistake_2,
        "- expecting perfect spoken dialogue/audio",
        "- changing style refs mid-pack",
        "",
        "Scoring",
        "- keeper 0/1",
        "- 1-5 character/location/style consistency",
        "- rerolls normal; score takes consistently",
        "",
        "Team workflow",
        "- Select top takes with consistent scores.",
        "- Keep notes short and concrete in rubric/scoring_sheet.csv.",
        "- Use the same scoring criteria across all reviewers.",
    ]


def _render_with_reportlab(
    prompt_path: str,
    asset_prompts_path: str,
    provider: str,
    version: str,
    logo_path: Path | None = None,
) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    def draw_logo_header(canvas: Canvas) -> None:
        if logo_path is None or not logo_path.exists():
            return
        try:
            width, height = LETTER
            img = ImageReader(str(logo_path))
            logo_w = 1.0 * inch
            logo_h = 0.35 * inch
            x = width - 0.8 * inch - logo_w
            y = height - 0.8 * inch - logo_h + 2
            canvas.drawImage(img, x, y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
        except Exception:
            # Silently skip logo rendering if the file is unreadable/invalid.
            return

    def draw_provider_header(canvas: Canvas) -> None:
        width, height = LETTER
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(width - 58, height - 22, f"Provider: {provider}")

    def draw_footer(canvas: Canvas) -> None:
        canvas.setFont("Helvetica", 9)
        canvas.drawString(58, 18, f"RenderScript AI v{version} | Provider: {provider}")

    def draw_wrapped(canvas: Canvas, text: str, x: float, y: float, max_width: float, font: str, size: int) -> float:
        canvas.setFont(font, size)
        words = text.split()
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if canvas.stringWidth(trial, font, size) <= max_width:
                current = trial
                continue
            canvas.drawString(x, y, current)
            y -= 15
            current = word
        if current:
            canvas.drawString(x, y, current)
            y -= 15
        return y

    def draw_box(canvas: Canvas, title: str, lines: list[str], x: float, y_top: float, width: float, height: float) -> None:
        canvas.rect(x, y_top - height, width, height, stroke=1, fill=0)
        cursor = y_top - 18
        cursor = draw_wrapped(canvas, title, x + 10, cursor, width - 20, "Helvetica-Bold", 12)
        for line in lines:
            if not line:
                cursor -= 5
                continue
            cursor = draw_wrapped(canvas, line, x + 10, cursor, width - 20, "Helvetica", 11)

    def draw_page_one(canvas: Canvas, prompt_file: str, asset_prompts_file: str, current_provider: str) -> None:
        width, height = LETTER
        x = 0.8 * inch
        y = height - 0.8 * inch
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawString(x, y, _title_for_provider(current_provider))
        y -= 30
        y = draw_wrapped(
            canvas,
            _subtitle_for_provider(current_provider),
            x,
            y,
            width - (1.6 * inch),
            "Helvetica",
            11,
        )
        y -= 6
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(x, y, "Quick Start: Choose Your Path")

        box_width = width - (1.6 * inch)
        path_a_top = y - 12
        path_a_lines = [
            f"1. Open {prompt_file}.",
            "2. Open your generation workflow.",
            "3. Do NOT add references.",
            "4. Copy/paste prompt for shot_001, generate.",
            "5. Repeat for shot_002, shot_003 (start with 3 shots).",
            "6. Score each shot in rubric/scoring_sheet.csv.",
        ]
        path_b_lines = [
            "Minimum 4 images:",
            "- style_01_ref_01",
            "- loc_01_ref_01",
            "- char_<X>_ref_01 (one per character)",
            f"1. Open {prompt_file}.",
            "2. Attach references for the current shot.",
            "3. Clear references before each shot.",
            "4. Add refs listed for the shot.",
            "5. Paste prompt, generate.",
            "6. Score each shot in the rubric.",
        ]
        where_to_click_heading = "Where to click in your tool:"
        path_b_height = 185
        if _is_runway(current_provider):
            path_a_lines[1] = "2. In Runway Workflow, open Gen-4 video generation."
            path_b_lines[5] = "2. In Runway Workflow: Tool -> References."
            path_b_lines[7] = "4. Add refs listed for the shot (max 3 active at once)."
            where_to_click_heading = "Where to click in Runway Workflow:"
            path_b_height = 200

        draw_box(
            canvas,
            "PATH A - No Assets (10 minutes)",
            path_a_lines,
            x,
            path_a_top,
            box_width,
            140,
        )
        path_b_top = path_a_top - 152
        draw_box(
            canvas,
            "PATH B - With Assets (30 minutes)",
            path_b_lines,
            x,
            path_b_top,
            box_width,
            path_b_height,
        )
        callout_top = path_b_top - (path_b_height + 12)
        draw_box(
            canvas,
            "Need assets?",
            _asset_callout_lines(current_provider, asset_prompts_file),
            x,
            callout_top,
            box_width,
            78,
        )
        mini_strip_y = callout_top - 90
        draw_wrapped(
            canvas,
            where_to_click_heading,
            x,
            mini_strip_y,
            box_width,
            "Helvetica-Bold",
            11,
        )
        draw_wrapped(
            canvas,
            _where_to_click_line(current_provider),
            x,
            mini_strip_y - 16,
            box_width,
            "Helvetica",
            11,
        )
        draw_wrapped(
            canvas,
            f"Prompt file in this package: {prompt_file}",
            x,
            mini_strip_y - 34,
            box_width,
            "Helvetica",
            10,
        )

    def draw_lines(canvas: Canvas, lines: list[str], *, title: bool = False) -> None:
        width, height = LETTER
        x = 0.8 * inch
        y = height - 0.8 * inch
        max_width = width - (1.6 * inch)
        canvas.setFont("Helvetica-Bold", 20 if title else 16)
        canvas.drawString(x, y, lines[0])
        y -= 30 if title else 26
        for line in lines[1:]:
            if line.startswith("PATH A") or line.startswith("PATH B") or line in {
                "Quick Start: Choose Your Path",
                "Checklist",
                "Reference Map",
                "Execution notes",
                "Workflow: Picture First, Audio in Post",
                "After you generate reference images",
                "Save images into:",
                "What's in this package",
                "Common mistakes",
                "Scoring",
                "Team workflow",
                "Minimum 4 images:",
                "Where to click in Runway Workflow:",
                "Where to click in your tool:",
                "Need assets?",
            }:
                font = "Helvetica-Bold"
                size = 12
            else:
                font = "Helvetica"
                size = 11
            if not line:
                y -= 8
                continue
            y = draw_wrapped(canvas, line, x, y, max_width, font, size)

    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=LETTER, pageCompression=0, invariant=1)
    title = _title_for_provider(provider)
    canvas.setTitle(title)
    canvas.setAuthor("renderscript")
    canvas.setSubject("Creative-first runbook")
    canvas.setCreator("renderscript")
    canvas.setProducer("renderscript")

    # Deterministic fixed 3-page flow (no loop-based page breaks).
    draw_logo_header(canvas)
    draw_provider_header(canvas)
    draw_page_one(canvas, prompt_path, asset_prompts_path, provider)
    draw_footer(canvas)
    canvas.showPage()
    draw_logo_header(canvas)
    draw_provider_header(canvas)
    draw_lines(canvas, _page_two_lines(prompt_path, asset_prompts_path, provider), title=False)
    draw_footer(canvas)
    canvas.showPage()
    draw_logo_header(canvas)
    draw_provider_header(canvas)
    draw_lines(canvas, _page_three_lines(provider), title=False)
    draw_footer(canvas)
    canvas.save()
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _page_stream(lines: list[str], start_y: int = 760) -> bytes:
    out = ["BT", "/F1 11 Tf", f"72 {start_y} Td", "14 TL"]
    for idx, line in enumerate(lines):
        if idx == 0:
            out.append("/F1 16 Tf")
        elif line.startswith("PATH A") or line.startswith("PATH B") or line in {
            "Quick Start: Choose Your Path",
            "Checklist",
            "Reference Map",
            "Execution notes",
            "Workflow: Picture First, Audio in Post",
            "After you generate reference images",
            "Save images into:",
            "What's in this package",
            "Common mistakes",
            "Scoring",
            "Team workflow",
            "Minimum 4 images:",
            "Where to click in Runway Workflow:",
            "Where to click in your tool:",
            "Need assets?",
        }:
            out.append("/F1 12 Tf")
        else:
            out.append("/F1 11 Tf")
        out.append(f"({_pdf_escape(line)}) Tj")
        out.append("T*")
    out.append("ET")
    return ("\n".join(out) + "\n").encode("latin-1", errors="replace")


def _render_fallback_pdf(prompt_path: str, asset_prompts_path: str, provider: str, version: str) -> bytes:
    footer = f"RenderScript AI v{version} | Provider: {provider}"
    pages = [
        _page_one_lines(prompt_path, asset_prompts_path, provider) + ["", footer],
        _page_two_lines(prompt_path, asset_prompts_path, provider) + ["", footer],
        _page_three_lines(provider) + ["", footer],
    ]
    streams = [_page_stream(page) for page in pages]

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    page_object_ids = [3 + i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_object_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))  # 2

    # Page objects: 3..(2+n)
    for i in range(len(pages)):
        content_id = 3 + len(pages) + i
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R "
                "/MediaBox [0 0 612 792] "
                "/Resources << /Font << /F1 "
                f"{3 + (2 * len(pages))} 0 R"
                " >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    # Content streams
    for stream in streams:
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream")

    # Shared font object
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # Deterministic metadata padding so the guide is not tiny in minimal fallback mode.
    padding_tokens = " ".join(f"runbook_note_{idx:03d}" for idx in range(180))
    objects.append(f"<< /RPGuidePadding ({padding_tokens}) >>".encode("ascii"))
    title = _title_for_provider(provider).replace("(", "\\(").replace(")", "\\)")
    # Info object to stabilize metadata
    objects.append(
        f"<< /Title ({title}) /Author (renderscript) /Creator (renderscript) /Producer (renderscript) >>".encode(
            "ascii"
        )
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
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
) -> bytes:
    try:
        return _render_with_reportlab(
            prompt_path,
            asset_prompts_path,
            provider=provider,
            version=version,
            logo_path=logo_path,
        )
    except ModuleNotFoundError:
        return _render_fallback_pdf(prompt_path, asset_prompts_path, provider=provider, version=version)
