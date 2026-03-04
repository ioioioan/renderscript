from __future__ import annotations

from io import BytesIO
from pathlib import Path


RUNWAY_PROVIDER = "runway.gen4_image_refs"
PROGRESS_TEXT = "Start -> Refs -> Shots -> Edit/Audio -> Score"


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


def _render_with_reportlab(
    prompt_path: str,
    asset_prompts_path: str,
    provider: str,
    version: str,
    logo_path: Path | None = None,
    scene_heading: str | None = None,
    scene_id: str | None = None,
    shot_count: int | None = None,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    page_w, page_h = A4
    margin_x = 36.0
    margin_bottom = 34.0
    header_h = 38.0
    top_gap = 12.0
    gutter = 12.0
    content_w = page_w - (2 * margin_x)
    main_w = content_w * 0.69
    side_w = content_w - main_w - gutter
    main_x = margin_x
    side_x = main_x + main_w + gutter
    content_top = page_h - header_h - top_gap - 20

    def wrap_text(text: str, width: float, font: str, size: float) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if c.stringWidth(trial, font, size) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def draw_wrapped(text: str, x: float, y: float, width: float, *, font: str = "Helvetica", size: float = 10.5, lead: float = 13.0) -> float:
        c.setFont(font, size)
        for line in wrap_text(text, width, font, size):
            c.drawString(x, y, line)
            y -= lead
        return y

    def draw_header(page_index: int) -> None:
        y0 = page_h - header_h
        c.setFillColor(colors.HexColor("#F3F5F7"))
        c.rect(0, y0, page_w, header_h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#D6DCE3"))
        c.line(0, y0, page_w, y0)

        if logo_path is not None and logo_path.exists():
            try:
                img = ImageReader(str(logo_path))
                c.drawImage(img, margin_x, y0 + 8, width=68, height=22, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass

        pill_w = 252
        pill_h = 18
        pill_x = (page_w - pill_w) / 2
        pill_y = y0 + 10
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#C2CBD6"))
        c.roundRect(pill_x, pill_y, pill_w, pill_h, 9, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#27323D"))
        c.setFont("Helvetica", 9)
        c.drawCentredString(pill_x + (pill_w / 2), pill_y + 5, PROGRESS_TEXT)

        badge_text = _provider_label(provider)
        badge_w = 74
        badge_h = 20
        badge_x = page_w - margin_x - badge_w
        badge_y = y0 + 9
        c.setFillColor(colors.HexColor("#E8F2FF") if _is_runway(provider) else colors.HexColor("#EDF7EE"))
        c.setStrokeColor(colors.HexColor("#9AB4D1") if _is_runway(provider) else colors.HexColor("#9FC5A2"))
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 10, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#203041"))
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(badge_x + (badge_w / 2), badge_y + 6, badge_text)

        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#5B6570"))
        c.drawString(margin_x, 18, f"RenderScript AI v{version}")
        c.drawRightString(page_w - margin_x, 18, f"Page {page_index}/5")

    def draw_callout(x: float, y_top: float, width: float, title: str, body: list[str], kind: str) -> float:
        style = {
            "golden": ("#FFF7DA", "#D4AE3F", "#5B4711"),
            "headsup": ("#FFF0ED", "#E09988", "#5A2E24"),
            "tip": ("#EEF7FF", "#90B7DB", "#1F3E59"),
        }[kind]
        fill, stroke, ink = style
        text_lines = 0
        for line in body:
            text_lines += max(1, len(wrap_text(line, width - 18, "Helvetica", 9.5)))
        box_h = 24 + (text_lines * 12)
        c.setFillColor(colors.HexColor(fill))
        c.setStrokeColor(colors.HexColor(stroke))
        c.roundRect(x, y_top - box_h, width, box_h, 6, stroke=1, fill=1)
        c.setFillColor(colors.HexColor(ink))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 8, y_top - 14, title)
        y = y_top - 28
        for line in body:
            y = draw_wrapped(line, x + 8, y, width - 16, font="Helvetica", size=9.5, lead=12)
        return y_top - box_h - 8

    def draw_step_card(x: float, y_top: float, width: float, title: str, bullets: list[str], done_when: str) -> float:
        bullet_lines = sum(max(1, len(wrap_text(b, width - 26, "Helvetica", 10))) for b in bullets)
        done_lines = max(1, len(wrap_text(done_when, width - 18, "Helvetica-Oblique", 9.5)))
        box_h = 30 + (bullet_lines * 12) + (done_lines * 12) + 14
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#D8DFE6"))
        c.roundRect(x, y_top - box_h, width, box_h, 7, stroke=1, fill=1)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor("#1F2933"))
        c.drawString(x + 8, y_top - 16, title)
        y = y_top - 30
        for bullet in bullets:
            wrapped = wrap_text(bullet, width - 26, "Helvetica", 10)
            for idx, line in enumerate(wrapped):
                c.setFont("Helvetica", 10)
                prefix = "- " if idx == 0 else "  "
                c.drawString(x + 10, y, prefix + line)
                y -= 12
        y -= 2
        c.setFont("Helvetica-Oblique", 9.5)
        c.setFillColor(colors.HexColor("#384553"))
        y = draw_wrapped(f"Done when: {done_when}", x + 8, y, width - 16, font="Helvetica-Oblique", size=9.5, lead=12)
        return y_top - box_h - 8

    def draw_file_tiles(x: float, y_top: float, width: float, files: list[str]) -> float:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#243443"))
        c.drawString(x, y_top, "Open These Files")
        y = y_top - 14
        tile_h = 16
        for file_name in files:
            c.setFillColor(colors.HexColor("#F7F9FB"))
            c.setStrokeColor(colors.HexColor("#D6DCE3"))
            c.roundRect(x, y - tile_h + 3, width, tile_h, 4, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#304255"))
            c.setFont("Helvetica", 8.8)
            c.drawString(x + 6, y - 7, file_name)
            y -= 19
        return y - 4

    def draw_mini_table(x: float, y_top: float, width: float, title: str, rows: list[tuple[str, str]]) -> float:
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#D8DFE6"))
        box_h = 24 + (len(rows) * 15)
        c.roundRect(x, y_top - box_h, width, box_h, 6, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#1E2D3B"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 8, y_top - 14, title)
        y = y_top - 28
        c.setFont("Helvetica", 9.2)
        for left, right in rows:
            c.setFillColor(colors.HexColor("#4A5A6A"))
            c.drawString(x + 8, y, left)
            c.setFillColor(colors.HexColor("#233240"))
            c.drawRightString(x + width - 8, y, right)
            y -= 15
        return y_top - box_h - 8

    def draw_arrow(x1: float, y1: float, x2: float, y2: float) -> None:
        c.setStrokeColor(colors.HexColor("#8191A3"))
        c.line(x1, y1, x2, y2)
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return
        mag = (dx * dx + dy * dy) ** 0.5
        ux = dx / mag
        uy = dy / mag
        px = -uy
        py = ux
        size = 4
        tip_x = x2
        tip_y = y2
        left_x = tip_x - (ux * size) + (px * size * 0.6)
        left_y = tip_y - (uy * size) + (py * size * 0.6)
        right_x = tip_x - (ux * size) - (px * size * 0.6)
        right_y = tip_y - (uy * size) - (py * size * 0.6)
        p = c.beginPath()
        p.moveTo(tip_x, tip_y)
        p.lineTo(left_x, left_y)
        p.lineTo(right_x, right_y)
        p.close()
        c.setFillColor(colors.HexColor("#8191A3"))
        c.drawPath(p, stroke=0, fill=1)

    def draw_diagram_scene_to_finished(x: float, y_top: float, width: float) -> float:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#203042"))
        c.drawString(x, y_top, "Diagram 1: Scene to finished cut")
        box_w = (width - 24) / 4
        box_h = 28
        top_y = y_top - 18
        bot_y = top_y - 46
        labels = [
            "RenderPackage",
            "Reference images",
            "Generate visual takes",
            "Select keepers",
            "Rough cut",
            "Audio in post",
            "Score pass",
            "Final export",
        ]
        positions: list[tuple[float, float]] = []
        for i in range(4):
            positions.append((x + (i * (box_w + 8)), top_y))
        for i in range(4):
            positions.append((x + (i * (box_w + 8)), bot_y))

        for idx, (bx, by) in enumerate(positions):
            c.setFillColor(colors.HexColor("#F9FBFD"))
            c.setStrokeColor(colors.HexColor("#CBD6E1"))
            c.roundRect(bx, by - box_h, box_w, box_h, 4, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#2A3B4D"))
            c.setFont("Helvetica", 8.6)
            tx = bx + 5
            ty = by - 12
            for line in wrap_text(labels[idx], box_w - 10, "Helvetica", 8.6):
                c.drawString(tx, ty, line)
                ty -= 10

        for i in range(3):
            x1 = positions[i][0] + box_w
            y1 = positions[i][1] - (box_h / 2)
            x2 = positions[i + 1][0]
            y2 = positions[i + 1][1] - (box_h / 2)
            draw_arrow(x1, y1, x2 - 2, y2)
        draw_arrow(positions[3][0] + (box_w / 2), positions[3][1] - box_h, positions[7][0] + (box_w / 2), positions[7][1] + 1)
        for i in range(7, 4, -1):
            x1 = positions[i][0]
            y1 = positions[i][1] - (box_h / 2)
            x2 = positions[i - 1][0] + box_w
            y2 = positions[i - 1][1] - (box_h / 2)
            draw_arrow(x1 + 2, y1, x2, y2)

        note_x = positions[2][0]
        note_y = positions[2][1] - box_h - 11
        c.setFont("Helvetica-Oblique", 8.2)
        c.setFillColor(colors.HexColor("#6A7785"))
        c.drawString(note_x, note_y, "Expect drift...")
        return bot_y - box_h - 16

    def draw_diagram_take_loop(x: float, y_top: float, width: float) -> float:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#203042"))
        c.drawString(x, y_top, "Diagram 2: The take loop")

        bx_w = 118
        bx_h = 24
        cx = x + (width / 2)
        cy = y_top - 64
        nodes = {
            "Pick shot": (cx - (bx_w / 2), cy + 44),
            "Load refs": (cx + 74, cy + 14),
            "Generate 3-6 takes": (cx + 74, cy - 26),
            "Review fast": (cx - (bx_w / 2), cy - 56),
            "Mark keeper": (cx - 192, cy - 26),
            "If drift: tighten refs / simplify prompt / split shot": (cx - 224, cy + 14),
        }

        order = [
            "Pick shot",
            "Load refs",
            "Generate 3-6 takes",
            "Review fast",
            "Mark keeper",
            "If drift: tighten refs / simplify prompt / split shot",
            "Generate 3-6 takes",
        ]

        for text, (bx, by) in nodes.items():
            c.setFillColor(colors.HexColor("#F8FBFF"))
            c.setStrokeColor(colors.HexColor("#C9D7E6"))
            local_h = 34 if text.startswith("If drift") else bx_h
            c.roundRect(bx, by - local_h, bx_w + (34 if text.startswith("If drift") else 0), local_h, 4, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#2C3D50"))
            c.setFont("Helvetica", 8.3)
            tw = bx_w + (22 if text.startswith("If drift") else 0)
            ty = by - 11
            for line in wrap_text(text, tw - 10, "Helvetica", 8.3):
                c.drawString(bx + 5, ty, line)
                ty -= 9

        for i in range(len(order) - 1):
            sx, sy = nodes[order[i]]
            tx, ty = nodes[order[i + 1]]
            sx += bx_w / 2
            tx += bx_w / 2
            draw_arrow(sx, sy - 12, tx, ty - 12)

        return cy - 78

    def draw_page_title(title: str, subtitle: str) -> float:
        c.setFillColor(colors.HexColor("#162534"))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(main_x, content_top, title)
        y = content_top - 18
        c.setFont("Helvetica", 10.5)
        c.setFillColor(colors.HexColor("#4B5B6A"))
        return draw_wrapped(subtitle, main_x, y, main_w - 4, font="Helvetica", size=10.5, lead=13)

    def draw_page_1() -> None:
        y = draw_page_title(
            "Page 1: Start here",
            "Choose a fast path, know where files live, and keep the pipeline picture-first.",
        )
        if _is_runway(provider):
            y = draw_callout(
                main_x,
                y - 2,
                main_w,
                "Runway click path",
                ["Workflow -> Tool -> References -> Paste prompt -> Generate -> Score"],
                "tip",
            )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Path A: Start without refs",
            [
                f"Open {prompt_path} and run shot_001 to shot_003 as picture-only.",
                "Do not burn subtitles, text, logos, or watermarks into the frame.",
                "Use this path to validate pacing and framing quickly.",
            ],
            "You have three visual takes and can pick one keeper per shot.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Path B: Add refs for continuity",
            [
                f"Generate refs from {asset_prompts_path}.",
                "Save assets using exact names from assets/ingredients_manifest.md.",
                "Attach refs shot by shot from bindings/bindings.csv.",
            ],
            "Identity, location, and style drift are visibly reduced.",
        )
        y = draw_file_tiles(
            main_x,
            y,
            main_w,
            [
                f"Shot prompts: {prompt_path}",
                "Reference checklist: assets/ingredients_manifest.md",
                "Reference map: bindings/bindings.csv",
                "Shot list: shots/shot_list.csv",
                "Scoring: rubric/scoring_sheet.csv",
            ],
        )
        draw_diagram_scene_to_finished(main_x, y - 2, main_w)

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Golden rule",
            [
                "Generate clean visuals only.",
                "Audio and dialogue are handled in post.",
                "If text appears on screen, reroll the take.",
            ],
            "golden",
        )
        rows = _safe_scene_meta(scene_heading, scene_id, shot_count)
        if rows:
            sy = draw_mini_table(side_x, sy, side_w, "Scene snapshot", rows)
        draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up",
            ["Expect drift between takes. Keep prompts tight and refs stable."],
            "headsup",
        )

    def draw_page_2() -> None:
        y = draw_page_title(
            "Page 2: Make reference images",
            "Build the minimum style/location/character set before long generation runs.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Generate the minimum set",
            [
                "style_01_ref_01 for look and tone.",
                "loc_01_ref_01 for environment continuity.",
                "char_<X>_ref_01 per character appearing in scene.",
            ],
            "Every required id in assets/ingredients_manifest.md has a matching file.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Name and stage assets",
            [
                "Save into assets/placeholder/* folders.",
                "Keep exact naming to avoid mismatched refs during shot generation.",
                "Avoid stylized text in refs to reduce accidental on-screen text.",
            ],
            "Refs are clean, consistent, and easy to map into bindings/bindings.csv.",
        )
        draw_mini_table(
            main_x,
            y,
            main_w,
            "Inputs / Outputs",
            [
                ("Input", "prompts/asset_prompts.md"),
                ("Checklist", "assets/ingredients_manifest.md"),
                ("Output", "assets/placeholder/*"),
            ],
        )

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Tip",
            ["Capture neutral, readable refs first; style variants can come later."],
            "tip",
        )
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Quick checklist",
            ["No logos in refs", "No text overlays", "Consistent wardrobe and lighting"],
            "golden",
        )
        draw_callout(
            side_x,
            sy,
            side_w,
            "Glossary",
            ["Ref ID: file handle used in bindings.", "Keeper: chosen take for edit."],
            "tip",
        )

    def draw_page_3() -> None:
        y = draw_page_title(
            "Page 3: Generate shots",
            "Run one shot at a time and use a quick loop to keep momentum while controlling drift.",
        )
        if _is_runway(provider):
            y = draw_callout(
                main_x,
                y - 2,
                main_w,
                "Runway click path",
                ["Workflow -> Tool -> References -> Paste prompt -> Generate -> Score"],
                "tip",
            )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Take loop per shot",
            [
                "Pick shot_id from shots/shot_list.csv and load refs from bindings/bindings.csv.",
                "Generate 3-6 visual takes before editing prompts.",
                "Reject takes with on-screen text, subtitles, logos, or heavy drift.",
            ],
            "One keeper is selected for each target shot.",
        )
        draw_diagram_take_loop(main_x, y - 2, main_w)

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up",
            ["If drift rises, tighten refs first. Prompt rewrites come second."],
            "headsup",
        )
        draw_file_tiles(
            side_x,
            sy,
            side_w,
            [
                f"Shot prompts: {prompt_path}",
                "Reference map: bindings/bindings.csv",
                "Shot list: shots/shot_list.csv",
            ],
        )

    def draw_page_4() -> None:
        y = draw_page_title(
            "Page 4: Edit + Audio in post",
            "Lock picture first, then build dialogue, ambience, SFX, and music as separate layers.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Workflow: Picture First, Audio in Post",
            [
                "1. Generate shots (picture-only; no subtitles/text).",
                "2. Assemble rough cut in shot_id order.",
                "3. Add dialogue from audio/dialogue_script.txt.",
                "4. Add ambience and SFX from audio/sfx_cue_sheet.md.",
                "5. Add music and do a final mix.",
            ],
            "Exported timeline has clean visuals and fully post-produced audio.",
        )
        y = draw_callout(
            main_x,
            y,
            main_w,
            "Subtitle policy",
            [
                "If your tool generates subtitles anyway, reroll that shot.",
                "Do not rely on subtitle removal.",
                "edit/subtitles.srt is optional editing guidance; disable before final export.",
            ],
            "golden",
        )
        draw_file_tiles(
            main_x,
            y,
            main_w,
            [
                "Dialogue script: audio/dialogue_script.txt",
                "Voice bible: audio/voice_bible.md",
                "SFX cues: audio/sfx_cue_sheet.md",
                "Optional guide: edit/subtitles.srt",
            ],
        )

        sy = content_top
        draw_callout(
            side_x,
            sy,
            side_w,
            "Tip",
            [
                "Keep dialogue edits in post so visual rerolls do not force subtitle clean-up.",
                "Version audio mixes per cut iteration.",
            ],
            "tip",
        )

    def draw_page_5() -> None:
        y = draw_page_title(
            "Page 5: Score + iterate",
            "Use consistent scoring to choose keepers and decide if you reroll, split, or move forward.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Score pass",
            [
                "Mark keeper per shot in rubric/scoring_sheet.csv.",
                "Rate character, location, and style continuity.",
                "Note drift cause briefly: refs, framing, prompt scope, or timing.",
            ],
            "You have a keeper map and clear reroll priorities.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Iteration strategy",
            [
                "If only one beat fails, reroll that shot first.",
                "If continuity keeps failing, split the shot into simpler actions.",
                "When score is stable, export final master.",
            ],
            "Score trend is stable and final export is approved.",
        )
        draw_mini_table(
            main_x,
            y,
            main_w,
            "Inputs / Outputs",
            [
                ("Input", "rubric/scoring_sheet.csv"),
                ("Output", "keeper decisions"),
                ("Final", "exported cut"),
            ],
        )

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up",
            ["Do not change scoring criteria mid-pack."],
            "headsup",
        )
        draw_callout(
            side_x,
            sy,
            side_w,
            "Golden rule",
            ["Consistency beats novelty when selecting a keeper set."],
            "golden",
        )

    buffer = BytesIO()
    c = Canvas(buffer, pagesize=A4, pageCompression=0, invariant=1)
    c.setTitle(_title_for_provider(provider))
    c.setAuthor("renderscript")
    c.setSubject("Creator guide")
    c.setCreator("renderscript")
    c.setProducer("renderscript")

    for page_number, draw_page in enumerate([draw_page_1, draw_page_2, draw_page_3, draw_page_4, draw_page_5], start=1):
        draw_header(page_number)
        draw_page()
        if page_number < 5:
            c.showPage()
    c.save()
    return buffer.getvalue()


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
    for k, v in _safe_scene_meta(scene_heading, scene_id, shot_count):
        meta_lines.append(f"{k}: {v}")
    runway_line = "Workflow -> Tool -> References -> Paste prompt -> Generate -> Score" if _is_runway(provider) else ""
    return [
        [
            "Page 1: Start here",
            "Path A and Path B",
            f"Shot prompts: {prompt_path}",
            "Reference checklist: assets/ingredients_manifest.md",
            "Reference map: bindings/bindings.csv",
            "Shot list: shots/shot_list.csv",
            "Scoring: rubric/scoring_sheet.csv",
            "Diagram 1: Scene to finished cut",
            "RenderPackage -> Reference images -> Generate visual takes -> Select keepers -> Rough cut -> Audio in post -> Score pass -> Final export",
            "Expect drift...",
            runway_line,
            *meta_lines,
        ],
        [
            "Page 2: Make reference images",
            f"Asset prompts: {asset_prompts_path}",
            "Naming from assets/ingredients_manifest.md",
            "Checklist: no logos, no text overlays, consistent wardrobe.",
        ],
        [
            "Page 3: Generate shots",
            f"Shot prompts: {prompt_path}",
            "Diagram 2: The take loop",
            "Pick shot -> Load refs -> Generate 3-6 takes -> Review fast -> Mark keeper -> If drift: tighten refs / simplify prompt / split shot -> Generate",
            runway_line,
        ],
        [
            "Page 4: Edit + Audio in post",
            "Workflow: Picture First, Audio in Post",
            "1. Generate shots (picture-only; no subtitles/text)",
            "2. Assemble a rough cut (order shots by shot_id)",
            "3. Add dialogue (voiceover/ADR) using the dialogue script",
            "4. Add ambience + SFX using the SFX cue sheet",
            "5. Add music",
            "6. Mix and export",
            "If your tool generates subtitles anyway, reroll that shot. Don't rely on subtitle removal.",
            "Optional editing guide: edit/subtitles.srt (disable before final export)",
        ],
        [
            "Page 5: Score + iterate",
            "Scoring file: rubric/scoring_sheet.csv",
            "Keep criteria stable across reviewers.",
            "Reroll only failing beats, then export final.",
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
    pages = [page + ["", footer] for page in _fallback_pages(prompt_path, asset_prompts_path, provider, scene_heading, scene_id, shot_count)]
    streams = [_page_stream(page) for page in pages]

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [3 + i for i in range(len(pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))

    for i in range(len(pages)):
        content_id = 3 + len(pages) + i
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
    padding = " ".join(f"creator_guide_padding_{idx:04d}" for idx in range(2200))
    objects.append(f"<< /GuidePadding ({padding}) >>".encode("ascii"))
    title = _title_for_provider(provider).replace("(", "\\(").replace(")", "\\)")
    objects.append(
        f"<< /Title ({title}) /Author (renderscript) /Creator (renderscript) /Producer (renderscript) >>".encode("ascii")
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
    scene_heading: str | None = None,
    scene_id: str | None = None,
    shot_count: int | None = None,
) -> bytes:
    try:
        return _render_with_reportlab(
            prompt_path,
            asset_prompts_path,
            provider=provider,
            version=version,
            logo_path=logo_path,
            scene_heading=scene_heading,
            scene_id=scene_id,
            shot_count=shot_count,
        )
    except ModuleNotFoundError:
        return _render_fallback_pdf(
            prompt_path,
            asset_prompts_path,
            provider=provider,
            version=version,
            scene_heading=scene_heading,
            scene_id=scene_id,
            shot_count=shot_count,
        )
