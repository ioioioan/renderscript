from __future__ import annotations

import re
from dataclasses import dataclass


_SCENE_RE = re.compile(r"^(INT|EXT)\.?\s+", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedScene:
    raw_heading: str
    int_ext: str | None
    location_name: str
    time_of_day: str | None
    body_lines: list[str]


def _parse_heading(heading: str) -> tuple[str | None, str, str | None]:
    clean = heading.strip()
    upper = clean.upper()
    int_ext = None
    if upper.startswith("INT"):
        int_ext = "INT"
    elif upper.startswith("EXT"):
        int_ext = "EXT"

    remainder = clean
    if "." in clean:
        remainder = clean.split(".", 1)[1].strip()

    if " - " in remainder:
        location_part, tod = remainder.rsplit(" - ", 1)
        location_name = location_part.strip() or "UNKNOWN"
        time_of_day = tod.strip() or None
    else:
        location_name = remainder.strip() or "UNKNOWN"
        time_of_day = None

    return int_ext, location_name, time_of_day


def parse_fountain(text: str) -> tuple[str, list[ParsedScene]]:
    title = "Untitled"
    scenes: list[ParsedScene] = []

    current_heading: str | None = None
    current_body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped.lower().startswith("title:") and title == "Untitled":
            candidate = stripped.split(":", 1)[1].strip()
            if candidate:
                title = candidate
            continue

        if _SCENE_RE.match(stripped):
            if current_heading is not None:
                int_ext, location_name, time_of_day = _parse_heading(current_heading)
                scenes.append(
                    ParsedScene(
                        raw_heading=current_heading,
                        int_ext=int_ext,
                        location_name=location_name,
                        time_of_day=time_of_day,
                        body_lines=[x for x in current_body if x.strip()],
                    )
                )
            current_heading = stripped
            current_body = []
            continue

        if current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        int_ext, location_name, time_of_day = _parse_heading(current_heading)
        scenes.append(
            ParsedScene(
                raw_heading=current_heading,
                int_ext=int_ext,
                location_name=location_name,
                time_of_day=time_of_day,
                body_lines=[x for x in current_body if x.strip()],
            )
        )

    return title, scenes
