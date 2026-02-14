from __future__ import annotations

import re
from dataclasses import dataclass


_SCENE_RE = re.compile(r"^(INT|EXT)\.?\s+", re.IGNORECASE)
_CHARACTER_RE = re.compile(r"^[A-Z0-9 .'\-()]+$")
_TRANSITION_RE = re.compile(r"^(?:[A-Z0-9 .'\-]+ TO:|FADE OUT\.|FADE IN:)$")


class FountainParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedScene:
    raw_heading: str
    int_ext: str | None
    location_name: str
    time_of_day: str | None
    tokens: list["ParsedToken"]


@dataclass(frozen=True)
class ParsedToken:
    token_type: str
    text: str
    speaker: str | None = None


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


def _is_transition(stripped: str) -> bool:
    return bool(_TRANSITION_RE.match(stripped))


def _is_character_cue(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped != stripped.upper():
        return False
    if len(stripped) > 40:
        return False
    if stripped.startswith("(") or stripped.endswith(":"):
        return False
    if _SCENE_RE.match(stripped) or _is_transition(stripped):
        return False
    if not any(ch.isalpha() for ch in stripped):
        return False
    return bool(_CHARACTER_RE.match(stripped))


def _is_parenthetical(stripped: str) -> bool:
    return stripped.startswith("(") and stripped.endswith(")") and len(stripped) >= 3


def _looks_like_dialogue_without_cue(raw_line: str) -> bool:
    stripped = raw_line.strip()
    if not stripped:
        return False
    leading = len(raw_line) - len(raw_line.lstrip(" \t"))
    return leading >= 2


def _tokenize_scene_body(lines: list[str]) -> list[ParsedToken]:
    tokens: list[ParsedToken] = []
    idx = 0

    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped:
            idx += 1
            continue

        if _is_transition(stripped):
            tokens.append(ParsedToken(token_type="transition", text=stripped))
            idx += 1
            continue

        if _is_parenthetical(stripped):
            raise FountainParseError(f"Parenthetical without character cue: {stripped}")

        if _looks_like_dialogue_without_cue(lines[idx]):
            raise FountainParseError(f"Dialogue without character cue: {stripped}")

        if _is_character_cue(stripped):
            speaker = stripped
            idx += 1
            emitted_speech = False
            while idx < len(lines):
                line = lines[idx].strip()
                if not line:
                    idx += 1
                    break
                if _SCENE_RE.match(line) or _is_transition(line) or _is_character_cue(line):
                    break
                if _is_parenthetical(line):
                    tokens.append(
                        ParsedToken(token_type="parenthetical", text=line, speaker=speaker)
                    )
                else:
                    tokens.append(ParsedToken(token_type="dialogue", text=line, speaker=speaker))
                emitted_speech = True
                idx += 1

            if not emitted_speech:
                tokens.append(ParsedToken(token_type="action", text=speaker))
            continue

        tokens.append(ParsedToken(token_type="action", text=stripped))
        idx += 1

    return tokens


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
                tokens = _tokenize_scene_body(current_body)
                if not tokens:
                    raise FountainParseError(f"Scene has zero beats: {current_heading}")
                scenes.append(
                    ParsedScene(
                        raw_heading=current_heading,
                        int_ext=int_ext,
                        location_name=location_name,
                        time_of_day=time_of_day,
                        tokens=tokens,
                    )
                )
            current_heading = stripped
            current_body = []
            continue

        if current_heading is None and stripped:
            raise FountainParseError(f"Content appears before first scene heading: {stripped}")

        if current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        int_ext, location_name, time_of_day = _parse_heading(current_heading)
        tokens = _tokenize_scene_body(current_body)
        if not tokens:
            raise FountainParseError(f"Scene has zero beats: {current_heading}")
        scenes.append(
            ParsedScene(
                raw_heading=current_heading,
                int_ext=int_ext,
                location_name=location_name,
                time_of_day=time_of_day,
                tokens=tokens,
            )
        )

    return title, scenes
