from __future__ import annotations

from io import BytesIO
from pathlib import Path


RUNWAY_PROVIDER = "runway.gen4_image_refs"
PROGRESS_TEXT = "Start \u2192 Refs \u2192 Shots \u2192 Edit/Audio \u2192 Score"


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

    def draw_wrapped(text: str, x: float, y: float, width: float, *, font: str = "Helvetica", size: float = 11.0, lead: float = 15.0) -> float:
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
            text_lines += max(1, len(wrap_text(line, width - 24, "Helvetica", 11)))
        box_h = 30 + (text_lines * 15)
        c.setFillColor(colors.HexColor(fill))
        c.setStrokeColor(colors.HexColor(stroke))
        c.roundRect(x, y_top - box_h, width, box_h, 8, stroke=1, fill=1)
        c.setFillColor(colors.HexColor(ink))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 11, y_top - 18, title)
        y = y_top - 36
        for line in body:
            y = draw_wrapped(line, x + 11, y, width - 22, font="Helvetica", size=11, lead=15)
        return y_top - box_h - 14

    def draw_step_card(x: float, y_top: float, width: float, title: str, bullets: list[str], done_when: str) -> float:
        bullet_lines = sum(max(1, len(wrap_text(b, width - 30, "Helvetica", 11))) for b in bullets)
        done_lines = max(1, len(wrap_text(done_when, width - 24, "Helvetica-Oblique", 11)))
        box_h = 40 + (bullet_lines * 15) + (done_lines * 15) + 18
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#D8DFE6"))
        c.roundRect(x, y_top - box_h, width, box_h, 8, stroke=1, fill=1)
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(colors.HexColor("#1F2933"))
        c.drawString(x + 11, y_top - 20, title)
        y = y_top - 40
        for bullet in bullets:
            wrapped = wrap_text(bullet, width - 30, "Helvetica", 11)
            for idx, line in enumerate(wrapped):
                c.setFont("Helvetica", 11)
                prefix = "- " if idx == 0 else "  "
                c.drawString(x + 12, y, prefix + line)
                y -= 15
        y -= 3
        c.setFont("Helvetica-Oblique", 11)
        c.setFillColor(colors.HexColor("#384553"))
        y = draw_wrapped(f"Done when: {done_when}", x + 11, y, width - 22, font="Helvetica-Oblique", size=11, lead=15)
        return y_top - box_h - 14

    def draw_file_tiles(x: float, y_top: float, width: float, files: list[str]) -> float:
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(colors.HexColor("#243443"))
        c.drawString(x, y_top, "Open These Files")
        y = y_top - 18
        tile_h = 20
        for file_name in files:
            c.setFillColor(colors.HexColor("#F7F9FB"))
            c.setStrokeColor(colors.HexColor("#D6DCE3"))
            c.roundRect(x, y - tile_h + 3, width, tile_h, 5, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#304255"))
            c.setFont("Helvetica", 10)
            c.drawString(x + 8, y - 9, file_name)
            y -= 24
        return y - 8

    def draw_mini_table(x: float, y_top: float, width: float, title: str, rows: list[tuple[str, str]]) -> float:
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#D8DFE6"))
        box_h = 30 + (len(rows) * 18)
        c.roundRect(x, y_top - box_h, width, box_h, 8, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#1E2D3B"))
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 11, y_top - 18, title)
        y = y_top - 36
        c.setFont("Helvetica", 11)
        for left, right in rows:
            c.setFillColor(colors.HexColor("#4A5A6A"))
            c.drawString(x + 11, y, left)
            c.setFillColor(colors.HexColor("#233240"))
            c.drawRightString(x + width - 11, y, right)
            y -= 18
        return y_top - box_h - 14

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
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(colors.HexColor("#203042"))
        c.drawString(x, y_top, "Diagram 1: Scene to finished cut")
        box_w = (width - 24) / 4
        box_h = 38
        top_y = y_top - 24
        bot_y = top_y - 62
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
            c.setFont("Helvetica", 10)
            tx = bx + 5
            ty = by - 14
            for line in wrap_text(labels[idx], box_w - 10, "Helvetica", 10):
                c.drawString(tx, ty, line)
                ty -= 12

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
        c.setFont("Helvetica-Oblique", 10)
        c.setFillColor(colors.HexColor("#6A7785"))
        c.drawString(note_x, note_y, "Expect drift...")
        return bot_y - box_h - 24

    def draw_diagram_take_loop(x: float, y_top: float, width: float) -> float:
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(colors.HexColor("#203042"))
        c.drawString(x, y_top, "Diagram 2: The take loop")

        bx_w = 138
        bx_h = 30
        cx = x + (width / 2)
        cy = y_top - 80
        nodes = {
            "Pick shot": (cx - (bx_w / 2), cy + 44),
            "Load refs": (cx + 94, cy + 14),
            "Generate 3-6 takes": (cx + 94, cy - 34),
            "Review fast": (cx - (bx_w / 2), cy - 68),
            "Mark keeper": (cx - 232, cy - 34),
            "If drift: tighten refs / simplify prompt / split shot": (cx - 254, cy + 14),
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
            local_h = 42 if text.startswith("If drift") else bx_h
            c.roundRect(bx, by - local_h, bx_w + (50 if text.startswith("If drift") else 0), local_h, 5, stroke=1, fill=1)
            c.setFillColor(colors.HexColor("#2C3D50"))
            c.setFont("Helvetica", 10)
            tw = bx_w + (32 if text.startswith("If drift") else 0)
            ty = by - 13
            for line in wrap_text(text, tw - 10, "Helvetica", 10):
                c.drawString(bx + 5, ty, line)
                ty -= 12

        for i in range(len(order) - 1):
            sx, sy = nodes[order[i]]
            tx, ty = nodes[order[i + 1]]
            sx += bx_w / 2
            tx += bx_w / 2
            draw_arrow(sx, sy - 12, tx, ty - 12)

        return cy - 96

    def draw_page_title(title: str, subtitle: str) -> float:
        c.setFillColor(colors.HexColor("#162534"))
        c.setFont("Helvetica-Bold", 23)
        c.drawString(main_x, content_top, title)
        y = content_top - 28
        c.setFont("Helvetica", 11)
        c.setFillColor(colors.HexColor("#4B5B6A"))
        return draw_wrapped(subtitle, main_x, y, main_w - 4, font="Helvetica", size=11, lead=15)

    def draw_page_1() -> None:
        y = draw_page_title(
            "Start here: turn a scene into editable shots (without losing your look)",
            "This guide is built for makers moving fast: get clean visuals first, then do sound in post where it belongs.",
        )
        y = draw_callout(
            main_x,
            y,
            main_w,
            "Golden rule",
            [
                "Picture-first. No burned-in subtitles, captions, on-screen text, watermarks, or logos.",
                "If text appears in-frame, reroll the shot and keep moving.",
                "Dialogue and audio are added in post.",
            ],
            "golden",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Path A - Universal (works with most tools)",
            [
                f"Open {prompt_path} and generate the first 3 shots as picture-only takes.",
                "Use this when you need speed, rough pacing checks, and fast visual exploration.",
                "Keep prompts focused and avoid editing too many variables at once.",
            ],
            "You can quickly choose a keeper direction for each opening shot.",
        )
        if _is_runway(provider):
            y = draw_step_card(
                main_x,
                y,
                main_w,
                "Path B - Runway (image reference workflow)",
                [
                    "Workflow -> Tool -> References -> Paste prompt -> Generate -> Score",
                    f"Create refs using {asset_prompts_path} and map them with bindings/bindings.csv.",
                    "Use this path when continuity matters more than speed.",
                ],
                "Your character/location/style continuity is stable across shots.",
            )
        y = draw_file_tiles(
            main_x,
            y,
            main_w,
            [
                "What's inside this package:",
                f"Shot prompts: {prompt_path}",
                "Shot list: shots/shot_list.csv",
                "Reference map: bindings/bindings.csv",
                "Reference checklist: assets/ingredients_manifest.md",
                "Scoring: rubric/scoring_sheet.csv",
            ],
        )
        draw_diagram_scene_to_finished(main_x, y - 2, main_w)

        sy = content_top
        rows = _safe_scene_meta(scene_heading, scene_id, shot_count)
        if rows:
            sy = draw_mini_table(side_x, sy, side_w, "Scene snapshot", rows)
        draw_callout(
            side_x,
            sy,
            side_w,
            "Tip",
            [
                "Generate three to six takes before judging.",
                "Fast loops beat perfect first attempts.",
            ],
            "tip",
        )

    def draw_page_2() -> None:
        y = draw_page_title(
            "Make your reference images (this is where consistency comes from)",
            "Do this once, do it cleanly, and every downstream step gets easier.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Generate the minimum set",
            [
                "Style: style_01_ref_01 to lock visual language.",
                "Location: loc_01_ref_01 to keep geography coherent.",
                "Characters: char_<X>_ref_01 for each speaking/on-camera role.",
                "Props: prop_XX_ref_01 for recurring hero objects.",
            ],
            "Every required id in assets/ingredients_manifest.md has a real file.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Naming and organization",
            [
                "Save into assets/placeholder/* folders.",
                "Keep exact naming to avoid mismatched refs during shot generation.",
                "Keep references clean: no logos, no text overlays, no heavy filters.",
            ],
            "You can load references without guesswork during take generation.",
        )
        draw_mini_table(
            main_x,
            y,
            main_w,
            "Capture checklist",
            [
                ("Input prompts", "prompts/asset_prompts.md"),
                ("Required IDs", "assets/ingredients_manifest.md"),
                ("Storage", "assets/placeholder/*"),
            ],
        )

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Tip",
            ["Start neutral. Stylization can be layered in later without breaking continuity."],
            "tip",
        )
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up",
            ["Inconsistent lighting in refs causes fast identity drift."],
            "headsup",
        )
        draw_callout(
            side_x,
            sy,
            side_w,
            "Glossary",
            [
                "Ref ID: stable filename used by bindings.",
                "Keeper: best take selected for edit.",
                "Drift: mismatch in identity/style/location over takes.",
            ],
            "tip",
        )

    def draw_page_3() -> None:
        y = draw_page_title(
            "Generate shots (repeat the take loop)",
            "Run one shot at a time, stay focused, and make keeper decisions early.",
        )
        if _is_runway(provider):
            y = draw_callout(
                main_x,
                y,
                main_w,
                "Runway click path",
                ["Workflow -> Tool -> References -> Paste prompt -> Generate -> Score"],
                "tip",
            )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Take loop instructions",
            [
                "Pick shot_id from shots/shot_list.csv and load refs from bindings/bindings.csv.",
                "Generate 3-6 takes before rewriting prompts.",
                "Review fast, mark one keeper, and move to the next shot.",
            ],
            "One keeper is selected for each target shot.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Fix drift without derailing momentum",
            [
                "If drift appears: tighten refs first.",
                "Then simplify prompt intent or split the shot into smaller beats.",
                "Avoid large style changes mid-pack.",
            ],
            "The next take wave improves without resetting your whole workflow.",
        )
        draw_diagram_take_loop(main_x, y - 2, main_w)

        sy = content_top
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up: dialogue-heavy",
            ["Dialogue-heavy shots need extra takes for timing and expression sync."],
            "headsup",
        )
        sy = draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up: multi-character",
            ["For multi-character frames, lock composition first, then performance details."],
            "headsup",
        )
        draw_callout(
            side_x,
            sy,
            side_w,
            "Heads-up: prop-dependent",
            [
                "If a hero prop drifts, add dedicated prop refs before changing everything else."
            ],
            "headsup",
        )

    def draw_page_4() -> None:
        y = draw_page_title(
            "Edit first, then audio in post",
            "Treat picture lock as the base layer; then build voice, ambience, SFX, and music on top.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Rough cut workflow",
            [
                "Assemble shots in shot_id order first.",
                "Trim for timing and continuity before touching audio polish.",
                "Keep alternate takes nearby for quick replacement.",
            ],
            "Picture timing feels right before audio layering starts.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Audio in post",
            [
                "Add ADR/VO using audio/dialogue_script.txt and voice notes from audio/voice_bible.md.",
                "Layer ambience and SFX from audio/sfx_cue_sheet.md.",
                "Add music, balance levels, and print a final mix.",
            ],
            "Your cut plays cleanly with intelligible dialogue and controlled dynamics.",
        )
        y = draw_callout(
            main_x,
            y,
            main_w,
            "Subtitle policy",
            [
                "No burned-in text. If subtitles/captions appear in-frame, reroll the shot.",
                "Do not rely on subtitle removal.",
                "edit/subtitles.srt is optional editing guidance and should be disabled before final export.",
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
                "Keep dialogue and subtitle decisions in post so visual rerolls stay clean.",
                "Version audio mixes per cut iteration.",
            ],
            "tip",
        )

    def draw_page_5() -> None:
        y = draw_page_title(
            "Score + iterate",
            "A simple score pass keeps creative decisions consistent when you move from draft to final.",
        )
        y = draw_step_card(
            main_x,
            y,
            main_w,
            "Score pass (keeper map)",
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
                "Reroll only failing beats first.",
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
            "Start here: turn a scene into editable shots (without losing your look)",
            "Picture-first. No burned-in subtitles/captions/on-screen text. Audio in post.",
            "Path A - Universal (works with most tools)",
            "Path B - Runway (image reference workflow)" if _is_runway(provider) else "",
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
            "Make your reference images (this is where consistency comes from)",
            "Minimum set: style, location, characters, props",
            f"Asset prompts: {asset_prompts_path}",
            "Naming from assets/ingredients_manifest.md",
            "Checklist: no logos, no text overlays, consistent wardrobe.",
        ],
        [
            "Generate shots (repeat the take loop)",
            f"Shot prompts: {prompt_path}",
            "Diagram 2: The take loop",
            "Pick shot -> Load refs -> Generate 3-6 takes -> Review fast -> Mark keeper -> If drift: tighten refs / simplify prompt / split shot -> Generate",
            runway_line,
        ],
        [
            "Edit first, then audio in post",
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
            "Score + iterate",
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
