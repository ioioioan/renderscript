from __future__ import annotations

import json
from pathlib import Path

from .fountain_parser import parse_fountain
from .ids import doc_id_from_text, location_id, scene_id, source_hash


_CREATED_AT = "1970-01-01T00:00:00Z"


def _build_document(text: str, source_name: str | None) -> dict[str, object]:
    title, parsed_scenes = parse_fountain(text)

    locations: list[dict[str, object]] = []
    location_lookup: dict[str, str] = {}
    scenes: list[dict[str, object]] = []

    for idx, scene in enumerate(parsed_scenes, start=1):
        loc_key = scene.location_name.strip().lower()
        if loc_key not in location_lookup:
            lid = location_id(scene.location_name)
            location_lookup[loc_key] = lid
            loc_obj: dict[str, object] = {
                "id": lid,
                "name": scene.location_name,
            }
            if scene.int_ext or scene.time_of_day:
                context: dict[str, str] = {}
                if scene.int_ext:
                    context["int_ext"] = scene.int_ext
                if scene.time_of_day:
                    context["time_of_day_default"] = scene.time_of_day
                loc_obj["context"] = context
            locations.append(loc_obj)

        beats = [{"type": "action", "text": line.strip()} for line in scene.body_lines]
        scenes.append(
            {
                "id": scene_id(idx, scene.raw_heading),
                "ordinal": idx,
                "heading": {
                    "raw": scene.raw_heading,
                    "location_id": location_lookup[loc_key],
                    **({"int_ext": scene.int_ext} if scene.int_ext else {}),
                    **({"time_of_day": scene.time_of_day} if scene.time_of_day else {}),
                },
                "beats": beats,
            }
        )

    return {
        "rscript_version": "0.1",
        "doc_id": doc_id_from_text(text),
        "meta": {
            "title": title,
            "source": {
                "format": "fountain",
                **({"name": source_name} if source_name else {}),
                "hash": source_hash(text),
            },
            "compiler": {
                "name": "renderscript",
                "version": "0.1.0",
            },
            "created_at": _CREATED_AT,
        },
        "entities": {
            "characters": [],
            "locations": locations,
            "props": [],
        },
        "scenes": scenes,
    }


def compile_fountain_text(text: str, source_name: str | None = None) -> dict[str, object]:
    return _build_document(text=text, source_name=source_name)


def write_rscript(doc: dict[str, object], output_path: Path) -> None:
    output_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compile_file(input_path: Path, output_path: Path) -> dict[str, object]:
    text = input_path.read_text(encoding="utf-8")
    compiled = compile_fountain_text(text, source_name=input_path.name)
    write_rscript(compiled, output_path)
    return compiled
