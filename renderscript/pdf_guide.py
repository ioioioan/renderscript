from __future__ import annotations

from io import BytesIO


_GUIDE_LINES = [
    "RenderPackage Quick Start (Runway Gen-4 Image References)",
    "",
    "Two-path quickstart",
    "Path A: No Assets (prompts-only).",
    "Path B: With Assets (minimum 4 images: style, location, 1 per character).",
    "",
    "Where to click in Runway Workflow",
    "Tool -> References",
    "Paste prompt",
    "Generate",
    "Score",
    "",
    "Shot checklist",
    "Open prompts/<provider>_prompts.md and process one SHOT block at a time.",
    "Each SHOT block lists required references and prompt text.",
    "Use the reference map file at bindings/bindings.csv to match shot IDs to refs.",
    "",
    "Common mistakes",
    "Forgetting to clear references between shots.",
    "Using too many references at once (Runway supports up to 3 active references).",
    "Expecting perfect dialogue audio from image-first outputs.",
    "",
    "Scoring",
    "Use rubric/scoring_sheet.csv after each shot generation pass.",
    "Track keeper status and 1-5 consistency for character, location, and style.",
]


def _render_with_reportlab(prompt_path: str) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen.canvas import Canvas

    def wrapped(canvas: Canvas, text: str, x: float, y: float, width: float, size: int) -> float:
        words = text.split()
        line = ""
        canvas.setFont("Helvetica", size)
        for word in words:
            test = f"{line} {word}".strip()
            if canvas.stringWidth(test, "Helvetica", size) <= width:
                line = test
            else:
                canvas.drawString(x, y, line)
                y -= size + 4
                line = word
        if line:
            canvas.drawString(x, y, line)
            y -= size + 4
        return y

    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=LETTER, pageCompression=0, invariant=1)
    width, height = LETTER
    left = 0.85 * inch
    y = height - 0.85 * inch
    line_width = width - (2 * left)
    full_lines = [line.replace("<provider>", "runway.gen4_image_refs") for line in _GUIDE_LINES]
    for idx, line in enumerate(full_lines):
        size = 14 if idx == 0 else 11
        if y < 0.9 * inch:
            canvas.showPage()
            y = height - 0.85 * inch
        y = wrapped(canvas, line if line else " ", left, y, line_width, size)
    if y > 2 * inch:
        y -= 10
        y = wrapped(
            canvas,
            f"Prompt file for this package: {prompt_path}",
            left,
            y,
            line_width,
            11,
        )
    canvas.save()
    return buffer.getvalue()


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_fallback_pdf(prompt_path: str) -> bytes:
    lines = [line.replace("<provider>", "runway.gen4_image_refs") for line in _GUIDE_LINES]
    lines.append(f"Prompt file for this package: {prompt_path}")
    lines.extend(
        [
            "",
            "Notes:",
            "Use consistent refs per shot to reduce drift.",
            "Rerolls are normal. Score each take in the rubric.",
        ]
    )
    while len(lines) < 80:
        lines.extend(lines[:10])
        lines = lines[:80]

    stream_lines = ["BT", "/F1 11 Tf", "72 760 Td", "14 TL"]
    for line in lines:
        escaped = _pdf_escape(line)
        stream_lines.append(f"({escaped}) Tj")
        stream_lines.append("T*")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines) + "\n"
    stream_bytes = stream.encode("latin-1", errors="replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii") + stream_bytes + b"endstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def render_creator_guide_pdf(prompt_path: str) -> bytes:
    try:
        return _render_with_reportlab(prompt_path)
    except ModuleNotFoundError:
        return _render_fallback_pdf(prompt_path)
