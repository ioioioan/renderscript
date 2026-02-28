from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from .compiler import compile_fountain_text
from .pdf_guide import render_creator_guide_pdf


SUPPORTED_PROVIDER = "runway.gen4_image_refs"
PROMPTS_FILENAME = "prompts/runway.gen4_image_refs_prompts.md"
REQUIRED_FILES = [
    "rpack.json",
    "rpack.schema.json",
    "README.md",
    "CREATOR_GUIDE.pdf",
    "assets/ingredients_manifest.md",
    "assets/placeholder/characters/README.md",
    "assets/placeholder/locations/README.md",
    "assets/placeholder/styles/README.md",
    "assets/placeholder/props/README.md",
    "shots/shot_list.csv",
    "bindings/bindings.csv",
    "rubric/scoring_sheet.csv",
    PROMPTS_FILENAME,
]
ZIP_FIXED_DATETIME = (1980, 1, 1, 0, 0, 0)
MIN_SHOTS = 8
MAX_SHOTS = 12
FRAMING_CYCLE = ("wide", "medium", "close")


def _render_readme() -> str:
    return (
        "# How to run this RenderPackage in Runway Gen-4 Image References\n\n"
        "This package is prepared for `runway.gen4_image_refs` workflows.\n\n"
        "## Steps\n\n"
        "1. Open Runway and start a Gen-4 image generation workflow.\n"
        "2. Enable **References**.\n"
        "3. Add references for the current shot (maximum 3 active at a time in Runway).\n"
        "4. Read required references in `bindings/bindings.csv` for that shot.\n"
        "5. Paste the matching prompt from `prompts/runway.gen4_image_refs_prompts.md`.\n"
        "6. Set the shot duration from `shots/shot_list.csv`.\n"
        "7. Generate output, then score it in `rubric/scoring_sheet.csv`.\n"
        "8. Reroll as needed while keeping reference IDs and prompt intent unchanged.\n\n"
        "## Limits & drift warnings\n\n"
        "- Results are not deterministic, even with fixed prompts and references.\n"
        "- Reference quality and consistency still depend on source image quality.\n"
        "- Runway supports up to 3 active references per generation.\n"
        "- Identity, wardrobe, and location drift can still occur and may require rerolls.\n"
        "- Overly broad prompt edits can reduce visual continuity across shots.\n"
    )


def _render_placeholder_readme(asset_kind: str) -> str:
    return (
        f"# {asset_kind.capitalize()} Placeholder\n\n"
        "Use this folder to stage reference images before generation.\n\n"
        "## Naming examples\n\n"
        "- `char_A_ref_01`\n"
        "- `loc_01_ref_01`\n"
        "- `style_01_ref_01`\n"
        "- `prop_01_ref_01`\n\n"
        "## Capture checklist\n\n"
        "- Capture clean, front-facing references where applicable.\n"
        "- Keep lighting and color temperature consistent.\n"
        "- Avoid heavy motion blur and extreme occlusion.\n"
        "- Keep wardrobe and key props consistent across captures.\n\n"
        "## Provider limits\n\n"
        "- Exact reference limits depend on provider.\n"
        "- Runway Gen-4 Image References supports up to 3 active references.\n"
    )


def _render_rpack_schema_json() -> str:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "RenderPackage v0.1",
        "type": "object",
        "required": [
            "rpack_version",
            "target_provider",
            "target_provider_version",
            "source",
            "scene",
            "shots",
            "bindings",
            "risk_flags",
        ],
        "properties": {
            "rpack_version": {"type": "string"},
            "target_provider": {"type": "string"},
            "target_provider_version": {"type": "string"},
            "source": {
                "type": "object",
                "required": ["filename", "hash"],
                "properties": {"filename": {"type": "string"}, "hash": {"type": "string"}},
            },
            "scene": {
                "type": "object",
                "required": ["scene_id", "heading_raw", "ordinal"],
                "properties": {
                    "scene_id": {"type": "string"},
                    "heading_raw": {"type": "string"},
                    "ordinal": {"type": "integer"},
                },
            },
            "shots": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["shot_id", "duration_s", "framing", "beat", "notes", "risk_flags"],
                },
            },
            "bindings": {"type": "object"},
            "required_references": {"type": "object"},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
        },
    }
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def _normalize_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return safe or "project"


def _resolve_output_path(
    output_path: Path,
    project: str,
    selected_scene: dict[str, object],
    provider: str,
) -> Path:
    is_dir_output = output_path.exists() and output_path.is_dir()
    if not is_dir_output and not output_path.suffix:
        is_dir_output = True
    if not is_dir_output:
        return output_path
    ordinal = int(selected_scene.get("ordinal", 0))
    scene_tag = f"scene_{ordinal:03d}"
    file_name = f"{_normalize_name(project)}_{scene_tag}_{provider.replace('.', '_')}_renderpackage_v1.zip"
    return output_path / file_name


def _render_scoring_sheet(shots: list[dict[str, object]]) -> str:
    rows = [
        [str(shot["shot_id"]), "", "", "", "", ""]
        for shot in shots
    ]
    return _to_csv(
        headers=[
            "shot_id",
            "keeper",
            "character_consistency_1_5",
            "location_consistency_1_5",
            "style_consistency_1_5",
            "notes",
        ],
        rows=rows,
    )


def _render_ingredients_manifest(required_refs: dict[str, list[str]]) -> str:
    all_refs = (
        required_refs["style_ref_ids"]
        + required_refs["location_ref_ids"]
        + required_refs["character_ref_ids"]
        + required_refs["prop_ref_ids"]
    )
    refs_list = "\n".join(f"- `{ref_id}`" for ref_id in all_refs) if all_refs else "- none"
    return (
        "# Ingredients Manifest\n\n"
        "## Required reference IDs\n\n"
        f"{refs_list}\n\n"
        "## Required asset categories\n\n"
        "- Characters\n"
        "- Locations\n"
        "- Style references\n"
        "- Props\n\n"
        "## Capture checklist\n\n"
        "- Keep framing and lighting consistent with intended shot style.\n"
        "- Capture neutral, clean references with minimal motion blur.\n"
        "- Capture at least one fallback reference per critical entity.\n"
        "- Verify reference files are named consistently before packaging.\n\n"
        "## Naming rules\n\n"
        "- `char_A_ref_01`\n"
        "- `char_A_02_ref_01` (for initial collisions)\n"
        "- `loc_01_ref_01`\n"
        "- `style_01_ref_01`\n"
        "- `prop_01_ref_01`\n"
    )


def _to_csv(headers: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue()


def _extract_scene(doc: dict[str, object], scene_ordinal: int | None) -> dict[str, object]:
    scenes_raw = doc.get("scenes", [])
    if not isinstance(scenes_raw, list):
        raise ValueError("Invalid compiled script: scenes must be a list")
    scenes = [scene for scene in scenes_raw if isinstance(scene, dict)]
    scenes.sort(key=lambda s: int(s.get("ordinal", 0)))
    if not scenes:
        raise ValueError("No scenes found in input")

    if len(scenes) > 1 and scene_ordinal is None:
        raise ValueError("v1 supports one scene; pass --scene to select")

    if scene_ordinal is None:
        return scenes[0]

    for scene in scenes:
        if int(scene.get("ordinal", 0)) == scene_ordinal:
            return scene
    raise ValueError(f"Scene ordinal not found: {scene_ordinal}")


def _speaker_lookup(doc: dict[str, object]) -> dict[str, str]:
    entities = doc.get("entities", {})
    if not isinstance(entities, dict):
        return {}
    characters_raw = entities.get("characters", [])
    if not isinstance(characters_raw, list):
        return {}
    out: dict[str, str] = {}
    for item in characters_raw:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        if cid and name:
            out[cid] = name
    return out


def _split_into_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    out = [part.strip() for part in parts if part.strip()]
    return out or [text.strip()]


def _extract_caps_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for token in re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", text):
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def _build_units(scene: dict[str, object], speaker_by_id: dict[str, str]) -> tuple[list[dict[str, object]], list[str]]:
    beats_raw = scene.get("beats", [])
    if not isinstance(beats_raw, list):
        return [], []

    transition_flags: list[str] = []
    units: list[dict[str, object]] = []
    attached_to: dict[int, str] = {}

    for idx, beat in enumerate(beats_raw):
        if not isinstance(beat, dict):
            continue
        beat_type = str(beat.get("type", ""))
        if beat_type == "transition":
            transition_flags.append("scene_transition_present")
            continue
        if beat_type == "parenthetical":
            speaker_id = str(beat.get("speaker_id", ""))
            next_beat = beats_raw[idx + 1] if idx + 1 < len(beats_raw) and isinstance(beats_raw[idx + 1], dict) else {}
            if (
                isinstance(next_beat, dict)
                and str(next_beat.get("type", "")) == "dialogue"
                and str(next_beat.get("speaker_id", "")) == speaker_id
            ):
                attached_to[idx + 1] = str(beat.get("text", "")).strip()
                continue
            speaker_name = speaker_by_id.get(speaker_id, speaker_id)
            text = str(beat.get("text", "")).strip()
            units.append(
                {
                    "type": "parenthetical",
                    "text": f"{speaker_name} {text}".strip(),
                    "speaker_ids": [speaker_id] if speaker_id else [],
                    "props": [],
                    "salience": 1,
                }
            )
            continue
        if beat_type == "dialogue":
            speaker_id = str(beat.get("speaker_id", ""))
            speaker_name = speaker_by_id.get(speaker_id, speaker_id)
            line = str(beat.get("text", "")).strip()
            parenthetical = attached_to.get(idx, "")
            text = f"{speaker_name} {parenthetical}: {line}".strip() if parenthetical else f"{speaker_name}: {line}"
            units.append(
                {
                    "type": "dialogue",
                    "text": text,
                    "speaker_ids": [speaker_id] if speaker_id else [],
                    "props": [],
                    "salience": 3,
                }
            )
            continue
        action_text = str(beat.get("text", "")).strip()
        units.append(
            {
                "type": "action",
                "text": action_text,
                "speaker_ids": [],
                "props": _extract_caps_tokens(action_text),
                "salience": 2,
            }
        )
    return units, sorted(set(transition_flags))


def _expand_units_to_min(units: list[dict[str, object]], min_shots: int) -> list[dict[str, object]]:
    out = [dict(unit) for unit in units]
    while len(out) < min_shots:
        split_idx = -1
        split_sentences: list[str] = []
        for idx, unit in enumerate(out):
            if unit.get("type") != "action":
                continue
            sentences = _split_into_sentences(str(unit.get("text", "")))
            if len(sentences) > 1:
                split_idx = idx
                split_sentences = sentences
                break
        if split_idx == -1:
            break
        base = dict(out[split_idx])
        replacements: list[dict[str, object]] = []
        for sentence in split_sentences:
            next_unit = dict(base)
            next_unit["text"] = sentence
            replacements.append(next_unit)
        out = out[:split_idx] + replacements + out[split_idx + 1 :]
    while len(out) < min_shots and out:
        clone = dict(out[(len(out) - 1) % len(out)])
        clone["notes"] = "Pacing hold"
        out.append(clone)
    return out


def _merge_units_to_max(units: list[dict[str, object]], max_shots: int) -> list[dict[str, object]]:
    out = [dict(unit) for unit in units]
    while len(out) > max_shots and len(out) > 1:
        merge_idx = 0
        best_score = 10**9
        for idx in range(len(out) - 1):
            left = out[idx]
            right = out[idx + 1]
            score = int(left.get("salience", 2)) + int(right.get("salience", 2))
            if score < best_score:
                best_score = score
                merge_idx = idx
        left = out[merge_idx]
        right = out[merge_idx + 1]
        merged = {
            "type": "merged",
            "text": f"{left.get('text', '')} {right.get('text', '')}".strip(),
            "speaker_ids": sorted(set(list(left.get("speaker_ids", [])) + list(right.get("speaker_ids", [])))),
            "props": sorted(set(list(left.get("props", [])) + list(right.get("props", [])))),
            "salience": max(int(left.get("salience", 2)), int(right.get("salience", 2))),
        }
        out = out[:merge_idx] + [merged] + out[merge_idx + 2 :]
    return out


def _normalize_units_for_shots(units: list[dict[str, object]]) -> list[dict[str, object]]:
    expanded = _expand_units_to_min(units, MIN_SHOTS)
    merged = _merge_units_to_max(expanded, MAX_SHOTS)
    return merged[:MAX_SHOTS]


def _build_shots(
    scene: dict[str, object],
    doc: dict[str, object],
    duration_s: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[str]]:
    speaker_by_id = _speaker_lookup(doc)
    units, transition_flags = _build_units(scene, speaker_by_id)
    if not units:
        heading = scene.get("heading", {})
        heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
        units = [{"type": "action", "text": heading_raw, "speaker_ids": [], "props": [], "salience": 2}]
    normalized_units = _normalize_units_for_shots(units)
    shots: list[dict[str, object]] = []
    for idx, unit in enumerate(normalized_units, start=1):
        risk_flags = list(transition_flags)
        shot = {
            "shot_id": f"shot_{idx:03d}",
            "duration_s": duration_s,
            "framing": FRAMING_CYCLE[(idx - 1) % len(FRAMING_CYCLE)],
            "beat": str(unit.get("text", "")).strip(),
            "notes": str(unit.get("notes", "")).strip(),
            "risk_flags": risk_flags,
        }
        shots.append(shot)
    return shots, normalized_units, transition_flags


def _character_ref_lookup(speaker_by_id: dict[str, str]) -> dict[str, str]:
    counts: dict[str, int] = {}
    out: dict[str, str] = {}
    for speaker_id in sorted(speaker_by_id.keys()):
        name = speaker_by_id[speaker_id]
        initial_match = re.search(r"[A-Za-z]", name)
        initial = initial_match.group(0).upper() if initial_match else "X"
        counts[initial] = counts.get(initial, 0) + 1
        suffix = f"_{counts[initial]:02d}" if counts[initial] > 1 else ""
        out[speaker_id] = f"char_{initial}{suffix}_ref_01"
    return out


def _speakers_from_action(text: str, speaker_by_id: dict[str, str]) -> list[str]:
    matches: list[str] = []
    for speaker_id, name in sorted(speaker_by_id.items()):
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            matches.append(speaker_id)
    return matches


def _build_bindings(
    shots: list[dict[str, object]],
    units: list[dict[str, object]],
    doc: dict[str, object],
) -> tuple[dict[str, dict[str, list[str]]], dict[str, list[str]]]:
    speaker_by_id = _speaker_lookup(doc)
    character_ref_by_speaker = _character_ref_lookup(speaker_by_id)

    prop_order: list[str] = []
    prop_lookup: dict[str, str] = {}
    for unit in units:
        for token in unit.get("props", []):
            prop = str(token)
            if prop not in prop_lookup:
                prop_order.append(prop)
                prop_lookup[prop] = f"prop_{len(prop_order):02d}_ref_01"

    out: dict[str, dict[str, list[str]]] = {}
    used_character_refs: set[str] = set()
    used_prop_refs: set[str] = set()
    for index, shot in enumerate(shots):
        shot_id = str(shot["shot_id"])
        unit = units[index]
        direct_speakers = [str(s) for s in unit.get("speaker_ids", []) if str(s)]
        inferred_speakers = _speakers_from_action(str(unit.get("text", "")), speaker_by_id)
        speaker_ids = sorted(set(direct_speakers + inferred_speakers))
        character_ref_ids = [character_ref_by_speaker[sid] for sid in speaker_ids if sid in character_ref_by_speaker]
        prop_ref_ids = [prop_lookup[str(token)] for token in unit.get("props", []) if str(token) in prop_lookup]
        used_character_refs.update(character_ref_ids)
        used_prop_refs.update(prop_ref_ids)
        out[shot_id] = {
            "character_ref_ids": character_ref_ids,
            "location_ref_ids": ["loc_01_ref_01"],
            "style_ref_ids": ["style_01_ref_01"],
            "prop_ref_ids": prop_ref_ids,
        }
    required_refs = {
        "style_ref_ids": ["style_01_ref_01"],
        "location_ref_ids": ["loc_01_ref_01"],
        "character_ref_ids": sorted(used_character_refs),
        "prop_ref_ids": sorted(used_prop_refs),
    }
    return out, required_refs


def _render_prompts(shots: list[dict[str, object]], bindings: dict[str, dict[str, list[str]]]) -> str:
    lines = [
        "# Runway Gen-4 Image References Prompts",
        "",
        "> Drift warning: outputs can still vary; review each shot for continuity.",
        "",
    ]
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        lines.append(f"## {shot_id} ({shot['duration_s']}s)")
        lines.append("")
        lines.append(
            "Apply references: "
            f"character={', '.join(shot_bindings['character_ref_ids']) or 'none'}, "
            f"location={', '.join(shot_bindings['location_ref_ids'])}, "
            f"style={', '.join(shot_bindings['style_ref_ids'])}"
        )
        if shot_bindings["prop_ref_ids"]:
            lines.append(f"Props references: {', '.join(shot_bindings['prop_ref_ids'])}")
        lines.append(
            "Prompt: "
            f"{shot['beat']}. Framing {shot['framing']}. "
            "Stay in this location. Do not invent new characters or props. Keep consistent look."
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_rpack_json(
    source_name: str,
    source_hash: str,
    target_provider: str,
    target_provider_version: str,
    scene: dict[str, object],
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    required_refs: dict[str, list[str]],
) -> str:
    heading = scene.get("heading", {})
    heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
    payload = {
        "rpack_version": "0.1",
        "target_provider": target_provider,
        "target_provider_version": target_provider_version,
        "source": {"filename": source_name, "hash": source_hash},
        "scene": {
            "scene_id": str(scene.get("id", "")),
            "heading_raw": str(heading_raw),
            "ordinal": int(scene.get("ordinal", 0)),
        },
        "shots": shots,
        "bindings": bindings,
        "required_references": required_refs,
        "risk_flags": [],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_deterministic_zip(output_path: Path, files: dict[str, str | bytes]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_STORED) as zf:
        for path in REQUIRED_FILES:
            info = ZipInfo(path)
            info.date_time = ZIP_FIXED_DATETIME
            info.compress_type = ZIP_STORED
            info.external_attr = 0o100644 << 16
            content = files[path]
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content
            zf.writestr(info, content_bytes)


def package_fountain_file(
    input_path: Path,
    output_path: Path,
    provider: str,
    provider_version: str = "",
    scene_ordinal: int | None = None,
    duration_s: int = 3,
    project: str = "project",
) -> None:
    if provider != SUPPORTED_PROVIDER:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: {SUPPORTED_PROVIDER}")

    text = input_path.read_text(encoding="utf-8")
    doc = compile_fountain_text(text, source_name=input_path.name)
    source = doc.get("meta", {}).get("source", {}) if isinstance(doc.get("meta", {}), dict) else {}
    source_hash = source.get("hash", "") if isinstance(source, dict) else ""
    selected_scene = _extract_scene(doc, scene_ordinal)
    resolved_output_path = _resolve_output_path(
        output_path=output_path,
        project=project,
        selected_scene=selected_scene,
        provider=provider,
    )
    shots, shot_units, _ = _build_shots(selected_scene, doc=doc, duration_s=duration_s)
    bindings, required_refs = _build_bindings(shots, units=shot_units, doc=doc)

    shot_rows = [
        [
            str(shot["shot_id"]),
            str(shot["duration_s"]),
            str(shot["framing"]),
            str(shot["beat"]),
            str(shot["notes"]),
            "|".join(str(flag) for flag in shot["risk_flags"]),
        ]
        for shot in shots
    ]
    bindings_rows = []
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        bindings_rows.append(
            [
                shot_id,
                "|".join(shot_bindings["character_ref_ids"]),
                "|".join(shot_bindings["location_ref_ids"]),
                "|".join(shot_bindings["style_ref_ids"]),
                "|".join(shot_bindings["prop_ref_ids"]),
            ]
        )

    files: dict[str, str | bytes] = {
        "rpack.json": _render_rpack_json(
            source_name=input_path.name,
            source_hash=str(source_hash),
            target_provider=provider,
            target_provider_version=provider_version,
            scene=selected_scene,
            shots=shots,
            bindings=bindings,
            required_refs=required_refs,
        ),
        "rpack.schema.json": _render_rpack_schema_json(),
        "README.md": _render_readme(),
        "CREATOR_GUIDE.pdf": render_creator_guide_pdf(PROMPTS_FILENAME),
        "assets/ingredients_manifest.md": _render_ingredients_manifest(required_refs),
        "assets/placeholder/characters/README.md": _render_placeholder_readme("characters"),
        "assets/placeholder/locations/README.md": _render_placeholder_readme("locations"),
        "assets/placeholder/styles/README.md": _render_placeholder_readme("styles"),
        "assets/placeholder/props/README.md": _render_placeholder_readme("props"),
        "shots/shot_list.csv": _to_csv(
            headers=["shot_id", "duration_s", "framing", "beat", "notes", "risk_flags"], rows=shot_rows
        ),
        "bindings/bindings.csv": _to_csv(
            headers=[
                "shot_id",
                "character_ref_ids",
                "location_ref_ids",
                "style_ref_ids",
                "prop_ref_ids",
            ],
            rows=bindings_rows,
        ),
        "rubric/scoring_sheet.csv": _render_scoring_sheet(shots),
        PROMPTS_FILENAME: _render_prompts(shots, bindings),
    }
    _write_deterministic_zip(resolved_output_path, files)
