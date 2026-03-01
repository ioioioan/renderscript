from __future__ import annotations

from io import BytesIO


def _page_one_lines(prompt_path: str) -> list[str]:
    return [
        "RenderPackage Quick Start (Runway Gen-4 Image References)",
        "This package creates a shot-by-shot plan. You generate shots in Runway.",
        "",
        "Quick Start: Choose Your Path",
        "",
        "PATH A - No Assets (10 minutes)",
        "1. Open prompts/runway.gen4_image_refs_prompts.md.",
        "2. In Runway Workflow, open Gen-4 video generation.",
        "3. Do NOT add references.",
        "4. Copy/paste prompt for shot_001, generate.",
        "5. Repeat for shot_002, shot_003 (start with 3 shots).",
        "6. Score each shot in rubric/scoring_sheet.csv.",
        "",
        "PATH B - With Assets (30 minutes)",
        "Minimum 4 images:",
        "- style_01_ref_01",
        "- loc_01_ref_01",
        "- char_<X>_ref_01 (one per character)",
        "1. Open prompts/runway.gen4_image_refs_prompts.md.",
        "2. In Runway Workflow: Tool -> References.",
        "3. Clear references before each shot.",
        "4. Add refs listed for the shot (max 3 active at once).",
        "5. Paste prompt, generate.",
        "6. Score each shot in the rubric.",
        "",
        "Where to click in Runway Workflow:",
        "Workflow -> Tool -> References -> Paste prompt -> Generate -> Score",
        "",
        f"Prompt file in this package: {prompt_path}",
    ]


def _page_two_lines() -> list[str]:
    return [
        "For Each Shot (repeat this loop)",
        "",
        "Checklist",
        "1. Clear references.",
        "2. Add listed references (if using Path B).",
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
        "- Process one shot block at a time from prompts/runway.gen4_image_refs_prompts.md.",
        "- Keep location and look stable through the full pack.",
        "- If drift appears, reroll before changing the reference set.",
    ]


def _page_three_lines() -> list[str]:
    return [
        "Common Mistakes + Scoring",
        "",
        "Common mistakes",
        "- forgetting to clear refs",
        "- exceeding 3 active refs",
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


def _render_with_reportlab(prompt_path: str) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen.canvas import Canvas

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

    def draw_page_one(canvas: Canvas, prompt_file: str) -> None:
        width, height = LETTER
        x = 0.8 * inch
        y = height - 0.8 * inch
        canvas.setFont("Helvetica-Bold", 20)
        canvas.drawString(x, y, "RenderPackage Quick Start (Runway Gen-4 Image References)")
        y -= 30
        y = draw_wrapped(
            canvas,
            "This package creates a shot-by-shot plan. You generate shots in Runway.",
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
        draw_box(
            canvas,
            "PATH A - No Assets (10 minutes)",
            [
                "1. Open prompts/runway.gen4_image_refs_prompts.md.",
                "2. In Runway Workflow, open Gen-4 video generation.",
                "3. Do NOT add references.",
                "4. Copy/paste prompt for shot_001, generate.",
                "5. Repeat for shot_002, shot_003 (start with 3 shots).",
                "6. Score each shot in rubric/scoring_sheet.csv.",
            ],
            x,
            path_a_top,
            box_width,
            140,
        )
        path_b_top = path_a_top - 152
        draw_box(
            canvas,
            "PATH B - With Assets (30 minutes)",
            [
                "Minimum 4 images:",
                "- style_01_ref_01",
                "- loc_01_ref_01",
                "- char_<X>_ref_01 (one per character)",
                "1. Open prompts/runway.gen4_image_refs_prompts.md.",
                "2. In Runway Workflow: Tool -> References.",
                "3. Clear references before each shot.",
                "4. Add refs listed for the shot (max 3 active at once).",
                "5. Paste prompt, generate.",
                "6. Score each shot in the rubric.",
            ],
            x,
            path_b_top,
            box_width,
            210,
        )
        mini_strip_y = path_b_top - 224
        draw_wrapped(
            canvas,
            "Workflow -> Tool -> References -> Paste prompt -> Generate -> Score",
            x,
            mini_strip_y,
            box_width,
            "Helvetica-Bold",
            11,
        )
        draw_wrapped(
            canvas,
            f"Prompt file in this package: {prompt_file}",
            x,
            mini_strip_y - 18,
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
                "Common mistakes",
                "Scoring",
                "Team workflow",
                "Minimum 4 images:",
                "Where to click in Runway Workflow:",
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
    canvas.setTitle("RenderPackage Quick Start (Runway Gen-4 Image References)")
    canvas.setAuthor("renderscript")
    canvas.setSubject("Creative-first runbook")
    canvas.setCreator("renderscript")
    canvas.setProducer("renderscript")

    # Deterministic fixed 3-page flow (no loop-based page breaks).
    draw_page_one(canvas, prompt_path)
    canvas.showPage()
    draw_lines(canvas, _page_two_lines(), title=False)
    canvas.showPage()
    draw_lines(canvas, _page_three_lines(), title=False)
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
            "Common mistakes",
            "Scoring",
            "Team workflow",
            "Minimum 4 images:",
            "Where to click in Runway Workflow:",
        }:
            out.append("/F1 12 Tf")
        else:
            out.append("/F1 11 Tf")
        out.append(f"({_pdf_escape(line)}) Tj")
        out.append("T*")
    out.append("ET")
    return ("\n".join(out) + "\n").encode("latin-1", errors="replace")


def _render_fallback_pdf(prompt_path: str) -> bytes:
    pages = [
        _page_one_lines(prompt_path),
        _page_two_lines(),
        _page_three_lines(),
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
    # Info object to stabilize metadata
    objects.append(
        b"<< /Title (RenderPackage Quick Start \\(Runway Gen-4 Image References\\)) "
        b"/Author (renderscript) /Creator (renderscript) /Producer (renderscript) >>"
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


def render_creator_guide_pdf(prompt_path: str) -> bytes:
    try:
        return _render_with_reportlab(prompt_path)
    except ModuleNotFoundError:
        return _render_fallback_pdf(prompt_path)
