from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from . import __version__
from .compiler import compile_fountain_text
from .pdf_guide import render_creator_guide_pdf


DEFAULT_PROVIDER = "universal"
RUNWAY_PROVIDER = "runway.gen4_image_refs"
SUPPORTED_PROVIDERS = (DEFAULT_PROVIDER, RUNWAY_PROVIDER)
ASSET_PROMPTS_FILENAME = "prompts/asset_prompts.md"
UNIVERSAL_PROMPTS_FILENAME = "prompts/shot_prompts.md"
RUNWAY_PROMPTS_FILENAME = f"prompts/{RUNWAY_PROVIDER}_prompts.md"
VOICE_BIBLE_FILENAME = "audio/voice_bible.md"
DIALOGUE_SCRIPT_FILENAME = "audio/dialogue_script.txt"
SFX_CUE_SHEET_FILENAME = "audio/sfx_cue_sheet.md"
SUBTITLES_FILENAME = "edit_guide/subtitles.srt"
BINDINGS_FILENAME = "shots/bindings.csv"
KEEPER_SHEET_FILENAME = "keepers/scoring_sheet.csv"
RPACK_FILENAME = "dev/rpack.json"
PROVENANCE_FILENAME = "dev/provenance.json"
CREATOR_GUIDE_FILENAME = "CREATOR_GUIDE.pdf"
BASE_REQUIRED_FILES = [
    "START_HERE.txt",
    CREATOR_GUIDE_FILENAME,
    "PACKAGE_MAP.md",
    "shots/shot_list.csv",
    BINDINGS_FILENAME,
    UNIVERSAL_PROMPTS_FILENAME,
    ASSET_PROMPTS_FILENAME,
    "assets/ingredients_manifest.md",
    "assets/refs/styles/",
    "assets/refs/characters/",
    "assets/refs/locations/",
    "assets/refs/props/",
    KEEPER_SHEET_FILENAME,
    VOICE_BIBLE_FILENAME,
    DIALOGUE_SCRIPT_FILENAME,
    SFX_CUE_SHEET_FILENAME,
    SUBTITLES_FILENAME,
    RPACK_FILENAME,
    PROVENANCE_FILENAME,
]
ZIP_FIXED_DATETIME = (1980, 1, 1, 0, 0, 0)
MIN_SHOTS = 8
MAX_SHOTS = 12
FRAMING_CYCLE = ("wide", "medium", "close")


def _prompt_filename_for_provider(provider: str) -> str:
    if provider == RUNWAY_PROVIDER:
        return RUNWAY_PROMPTS_FILENAME
    return UNIVERSAL_PROMPTS_FILENAME


def _required_files(prompt_files: list[str]) -> list[str]:
    out = list(BASE_REQUIRED_FILES)
    prompt_insert_idx = out.index(ASSET_PROMPTS_FILENAME)
    for prompt_file in prompt_files:
        if prompt_file not in out:
            out.insert(prompt_insert_idx, prompt_file)
            prompt_insert_idx += 1
    return out


def _prompt_files_for_package(provider: str, include_provider_prompts: list[str] | None = None) -> list[str]:
    prompt_files = [UNIVERSAL_PROMPTS_FILENAME]
    providers_to_include: list[str] = []

    if provider != DEFAULT_PROVIDER:
        providers_to_include.append(provider)
    for extra in include_provider_prompts or []:
        if extra not in providers_to_include:
            providers_to_include.append(extra)

    for provider_name in providers_to_include:
        if provider_name not in SUPPORTED_PROVIDERS:
            supported_str = ", ".join(SUPPORTED_PROVIDERS)
            raise ValueError(f"Unsupported provider: {provider_name}. Supported providers: {supported_str}")
        if provider_name == DEFAULT_PROVIDER:
            continue
        prompt_file = _prompt_filename_for_provider(provider_name)
        if prompt_file not in prompt_files:
            prompt_files.append(prompt_file)
    return prompt_files


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    rows = [[str(shot["shot_id"]), "", "", "", "", ""] for shot in shots]
    return _to_csv(
        headers=[
            "shot_id",
            "keeper",
            "character_consistency",
            "location_consistency",
            "style_consistency",
            "note",
        ],
        rows=rows,
    )


def _render_package_map(provider: str, prompt_path: str) -> str:
    workflow_line = "This package uses the Universal workflow."
    if provider == RUNWAY_PROVIDER:
        workflow_line = "This package uses the Runway Gen-4 References workflow."
    return (
        "# RenderPackage Map\n\n"
        "## 1) What to open first\n\n"
        f"- Start with `{CREATOR_GUIDE_FILENAME}`.\n"
        "- Then follow `START_HERE.txt` for the quick flow.\n\n"
        "## 2) Where references go\n\n"
        "- Place all reference images inside `assets/refs/`.\n"
        "- Use `assets/ingredients_manifest.md` for required IDs and naming.\n\n"
        "## 3) Where prompts live\n\n"
        f"- Universal shot prompts: `{UNIVERSAL_PROMPTS_FILENAME}`.\n"
        "- Provider-specific prompts: `prompts/<provider>_prompts.md`.\n"
        f"- {workflow_line}\n"
        f"- Use `{prompt_path}` to generate shots.\n"
        f"- Reference image prompt helper: `{ASSET_PROMPTS_FILENAME}`.\n\n"
        "## 4) Where to track keepers\n\n"
        "- Directing sheet: `shots/shot_list.csv`.\n"
        f"- Reference map: `{BINDINGS_FILENAME}`.\n"
        f"- Keeper tracking sheet: `{KEEPER_SHEET_FILENAME}`.\n\n"
        "## 5) Where audio files live\n\n"
        f"- Dialogue script: `{DIALOGUE_SCRIPT_FILENAME}`.\n"
        f"- Voice guide: `{VOICE_BIBLE_FILENAME}`.\n"
        f"- SFX cues: `{SFX_CUE_SHEET_FILENAME}`.\n"
        f"- Optional subtitle guide: `{SUBTITLES_FILENAME}`.\n\n"
        "## 6) Developer files\n\n"
        f"- Machine-readable source of truth: `{RPACK_FILENAME}`.\n"
        f"- Build/provenance metadata: `{PROVENANCE_FILENAME}`.\n"
    )


def _render_start_here() -> str:
    return (
        "1. Read CREATOR_GUIDE.pdf\n"
        "2. Put reference images in assets/refs\n"
        "3. Generate takes using prompts\n"
        "4. Mark keepers in keepers/scoring_sheet.csv\n"
    )


def _render_asset_prompts(
    scene: dict[str, object],
    shots: list[dict[str, object]],
    character_refs: list[tuple[str, str]],
) -> str:
    heading = scene.get("heading", {})
    heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
    beat_samples = [str(shot.get("beat", "")).strip() for shot in shots[:3]]
    beat_context = " | ".join(sample for sample in beat_samples if sample)

    lines = [
        "# Asset Prompts",
        "",
        "Use in any image generator.",
        "Generate square or portrait images, consistent lighting, neutral background for characters.",
        "",
        f"Scene context: {heading_raw}",
        f"Shot context: {beat_context}",
        "",
        "## Style Reference — style_01_ref_01",
        (
            "Create a single style board image for this scene context. Keep visual tone, color palette, and texture "
            "consistent across shots. Avoid text overlays and logos."
        ),
        "",
        "## Location Reference — loc_01_ref_01",
        (
            "Create one clean environment image for the scene location. Keep architectural cues and lighting consistent "
            "with the scene context. No people in frame."
        ),
        "",
    ]
    for ref_id, character_name in character_refs:
        lines.extend(
            [
                f"## Character Reference — {ref_id}",
                (
                    f"Create a neutral portrait reference of {character_name} for this scene context. Keep expression "
                    "natural, wardrobe consistent, and background plain. No celebrity or real-person likeness."
                ),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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
        "## Asset prompts\n\n"
        f"- Use `{ASSET_PROMPTS_FILENAME}` to generate reference images.\n\n"
        "## Naming rules\n\n"
        "- `char_A_ref_01`\n"
        "- `char_A_02_ref_01` (for initial collisions)\n"
        "- `loc_01_ref_01`\n"
        "- `style_01_ref_01`\n"
        "- `prop_01_ref_01`\n"
    )


def _parse_debug_text(debug_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in debug_text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _render_provenance_json(
    source_name: str,
    source_hash: str,
    provider: str,
    prompt_filename: str,
    generated_at: str,
    guide_debug_text: str,
) -> str:
    debug = _parse_debug_text(guide_debug_text)
    payload = {
        "generator": {"name": "RenderScript AI", "version": __version__},
        "generated_at": generated_at,
        "source": {"filename": source_name, "hash": source_hash},
        "provider": provider,
        "prompt_profile": prompt_filename,
        "creator_guide": {
            "renderer_used": debug.get("renderer_used", ""),
            "engine": debug.get("engine", ""),
            "error": debug.get("error", ""),
        },
        "runtime": {
            "python": debug.get("python", ""),
            "platform": debug.get("platform", ""),
            "playwright_version": debug.get("playwright_version", ""),
            "chromium_launch_success": debug.get("chromium_launch_success", ""),
            "chromium_installed": debug.get("chromium_installed", ""),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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


def _clean_prompt_sentence(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = cleaned.replace("?.", "?").replace("!.", "!")
    return cleaned.strip()


def _format_prompt_line(beat: str, framing: str) -> str:
    cleaned_beat = _clean_prompt_sentence(beat)
    if cleaned_beat and cleaned_beat[-1] not in ".!?":
        cleaned_beat = f"{cleaned_beat}."
    return (
        f"{cleaned_beat} Framing {framing}. "
        "Stay in this location. Do not invent new characters or props. Keep consistent look."
    ).strip()


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
    if len(out) < min_shots and out:
        out = _expand_dialogue_coverage(out, min_shots)
    while len(out) < min_shots and out:
        clone_source = out[(len(out) - 1) % len(out)]
        clone = dict(clone_source)
        clone["type"] = "coverage"
        clone["coverage_kind"] = "hold"
        base_text = _clean_prompt_sentence(str(clone_source.get("text", "")))
        if clone.get("speaker_ids"):
            clone["text"] = f"Hold on {', '.join(str(sid) for sid in clone['speaker_ids'])} after the beat: {base_text}"
        else:
            clone["text"] = f"Hold on the room after the beat: {base_text}"
        clone["notes"] = "Pacing hold"
        clone["salience"] = 1
        out.append(clone)
    return out


def _dialogue_line_from_unit(unit: dict[str, object]) -> tuple[str, str]:
    text = _clean_prompt_sentence(str(unit.get("text", "")))
    if ": " not in text:
        return "", text
    speaker, line = text.split(": ", 1)
    return speaker.strip(), line.strip()


def _speaker_ids_from_unit(unit: dict[str, object]) -> list[str]:
    return [str(sid) for sid in unit.get("speaker_ids", []) if str(sid)]


def _dialogue_variant_units(
    unit: dict[str, object],
    prev_unit: dict[str, object] | None,
    next_unit: dict[str, object] | None,
    variant_budget: int,
) -> list[dict[str, object]]:
    if unit.get("type") != "dialogue" or variant_budget <= 0:
        return []

    speaker_name, line = _dialogue_line_from_unit(unit)
    if not line:
        return []

    current_speaker_ids = _speaker_ids_from_unit(unit)
    other_unit = next_unit if next_unit and next_unit.get("type") == "dialogue" else prev_unit
    other_speaker_name = ""
    other_speaker_ids: list[str] = []
    if other_unit and other_unit.get("type") == "dialogue":
        other_speaker_name, _ = _dialogue_line_from_unit(other_unit)
        other_speaker_ids = _speaker_ids_from_unit(other_unit)
        if other_speaker_name == speaker_name:
            other_speaker_name = ""
            other_speaker_ids = []

    variants: list[dict[str, object]] = []
    if other_speaker_name:
        variants.append(
            {
                "type": "coverage",
                "coverage_kind": "reaction",
                "text": f"Reaction on {other_speaker_name} as {speaker_name} lands the line: {line}",
                "speaker_ids": other_speaker_ids,
                "props": [],
                "salience": 2,
                "notes": "Reaction coverage",
            }
        )
    if variant_budget > len(variants):
        if other_speaker_name:
            variants.append(
                {
                    "type": "coverage",
                    "coverage_kind": "two_shot",
                    "text": f"Two-shot coverage holds {speaker_name} and {other_speaker_name} on the beat: {line}",
                    "speaker_ids": sorted(set(current_speaker_ids + other_speaker_ids)),
                    "props": [],
                    "salience": 1,
                    "notes": "Two-shot coverage",
                }
            )
        else:
            variants.append(
                {
                    "type": "coverage",
                    "coverage_kind": "hold",
                    "text": f"Hold on {speaker_name} after the beat: {line}",
                    "speaker_ids": current_speaker_ids,
                    "props": [],
                    "salience": 1,
                    "notes": "Hold coverage",
                }
            )
    return variants[:variant_budget]


def _expand_dialogue_coverage(units: list[dict[str, object]], min_shots: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    remaining_needed = max(min_shots - len(units), 0)
    dialogue_indices = [idx for idx, unit in enumerate(units) if unit.get("type") == "dialogue"]
    dialogue_count = max(len(dialogue_indices), 1)

    for idx, unit in enumerate(units):
        out.append(dict(unit))
        if remaining_needed <= 0 or unit.get("type") != "dialogue":
            continue

        variants_for_this_unit = max(1, remaining_needed // dialogue_count)
        if remaining_needed % dialogue_count:
            variants_for_this_unit += 1
        prev_unit = units[idx - 1] if idx > 0 else None
        next_unit = units[idx + 1] if idx + 1 < len(units) else None
        variants = _dialogue_variant_units(unit, prev_unit, next_unit, variant_budget=min(2, variants_for_this_unit))
        for variant in variants:
            if remaining_needed <= 0:
                break
            out.append(variant)
            remaining_needed -= 1
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
        inferred_speakers = [] if direct_speakers else _speakers_from_action(str(unit.get("text", "")), speaker_by_id)
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


def _scene_location_label(scene: dict[str, object]) -> str:
    heading = scene.get("heading", {})
    raw = str(heading.get("raw", "")) if isinstance(heading, dict) else ""
    if not raw:
        return "scene_location"
    normalized = re.sub(r"^(INT\\.|EXT\\.|INT/EXT\\.|I/E\\.)\\s*", "", raw.strip(), flags=re.IGNORECASE)
    core = normalized.split(" - ", 1)[0].strip()
    return core or "scene_location"


def _short_beat_label(text: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if ": " in cleaned:
        cleaned = cleaned.split(": ", 1)[1].strip()
    words = cleaned.split(" ")
    return " ".join(words[:max_words]).strip()


def _shot_type_for_unit(unit: dict[str, object], framing: str, index: int) -> str:
    coverage_kind = str(unit.get("coverage_kind", "")).strip()
    if coverage_kind == "reaction":
        return "close_up"
    if coverage_kind == "two_shot":
        return "medium"
    if coverage_kind == "hold":
        return "medium"
    text = str(unit.get("text", "")).lower()
    props = unit.get("props", [])
    if any(token in text for token in ("walk", "run", "move", "crosses", "tracks")):
        return "tracking"
    if unit.get("type") == "dialogue":
        return "over_shoulder"
    if props and index % 4 == 0:
        return "insert"
    if framing == "wide":
        return "wide_establishing"
    if framing == "close":
        return "close_up"
    return "medium"


def _camera_for_shot_type(shot_type: str) -> str:
    mapping = {
        "wide_establishing": "static",
        "medium": "static",
        "close_up": "slow_push",
        "insert": "static",
        "tracking": "tracking",
        "over_shoulder": "over_shoulder",
    }
    return mapping.get(shot_type, "static")


def _description_from_unit_text(text: str, max_words: int = 20) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    words = cleaned.split(" ")
    return " ".join(words[:max_words]).strip()


def _render_prompts(
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    provider: str,
) -> str:
    title = (
        "# Runway Gen-4 Image References Prompts"
        if provider == RUNWAY_PROVIDER
        else "# Universal RenderPackage Prompts"
    )
    lines = [
        title,
        "",
        "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS.",
        "Generate picture-only shots. Audio/dialogue will be added in post.",
        "",
        "> Drift warning: outputs can still vary; review each shot for continuity.",
        "",
    ]
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        lines.append(f"## {shot_id} ({shot['duration_s']}s)")
        lines.append("")
        lines.append("No on-screen text or subtitles.")
        if provider == RUNWAY_PROVIDER:
            lines.append(
                "Apply references: "
                f"character={', '.join(shot_bindings['character_ref_ids']) or 'none'}, "
                f"location={', '.join(shot_bindings['location_ref_ids'])}, "
                f"style={', '.join(shot_bindings['style_ref_ids'])}"
            )
        else:
            lines.append("Apply references: Attach style/location/character reference images if your tool supports them.")
            lines.append(
                "Required ref IDs: "
                f"character={', '.join(shot_bindings['character_ref_ids']) or 'none'}, "
                f"location={', '.join(shot_bindings['location_ref_ids'])}, "
                f"style={', '.join(shot_bindings['style_ref_ids'])}"
            )
        if shot_bindings["prop_ref_ids"]:
            lines.append(f"Props references: {', '.join(shot_bindings['prop_ref_ids'])}")
        lines.append("Prompt: " + _format_prompt_line(str(shot["beat"]), str(shot["framing"])))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _scene_character_names(scene: dict[str, object], speaker_by_id: dict[str, str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for beat in scene.get("beats", []) if isinstance(scene.get("beats", []), list) else []:
        if not isinstance(beat, dict):
            continue
        speaker_id = str(beat.get("speaker_id", "")).strip()
        if speaker_id and speaker_id in speaker_by_id:
            name = speaker_by_id[speaker_id].title()
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _scene_summary_lines(scene: dict[str, object], speaker_by_id: dict[str, str]) -> list[str]:
    heading = scene.get("heading", {})
    heading_raw = str(heading.get("raw", "")).strip() if isinstance(heading, dict) else ""
    ordinal = int(scene.get("ordinal", 0) or 0)
    character_names = _scene_character_names(scene, speaker_by_id)

    beat_parts: list[str] = []
    beats = scene.get("beats", [])
    if isinstance(beats, list):
        for beat in beats:
            if not isinstance(beat, dict):
                continue
            text = _clean_prompt_sentence(str(beat.get("text", "")))
            if not text:
                continue
            if beat.get("type") == "dialogue":
                speaker_id = str(beat.get("speaker_id", "")).strip()
                speaker_name = speaker_by_id.get(speaker_id, "").title()
                if speaker_name:
                    text = f"{speaker_name} says {text.rstrip('.!?')}"
            beat_parts.append(text.rstrip(".!?"))
            if len(beat_parts) == 2:
                break

    beat_summary = ""
    if beat_parts:
        beat_summary = "; ".join(beat_parts)

    lines = ["Scene summary"]
    if ordinal:
        lines.append(f"This package was generated from Scene {ordinal} of the screenplay.")
    else:
        lines.append("This package was generated from one scene of the screenplay.")
    if character_names:
        lines.append(f"Characters: {', '.join(character_names)}")
    if heading_raw:
        lines.append(f"Location: {heading_raw.title()}")
    if beat_summary:
        lines.append(f"Beat: {beat_summary}.")
    return lines


def _extract_dialogue_pairs(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"([A-Za-z][A-Za-z0-9 _'().-]{0,40}):\s*([^:]+?)(?=(?:\s+[A-Za-z][A-Za-z0-9 _'().-]{0,40}:\s)|$)")
    out: list[tuple[str, str]] = []
    for speaker_raw, line_raw in pattern.findall(text):
        speaker = re.sub(r"\s+", " ", speaker_raw).strip()
        line = re.sub(r"\s+", " ", line_raw).strip()
        if speaker and line:
            out.append((speaker, line))
    return out


def _render_voice_bible(speaker_by_id: dict[str, str]) -> str:
    lines = [
        "# Voice Bible",
        "",
        "Audio post guidance only. Avoid personal likeness or impersonation.",
        "",
    ]
    names = sorted(set(speaker_by_id.values()))
    if not names:
        lines.extend(["No named dialogue characters detected.", ""])
        return "\n".join(lines).rstrip() + "\n"
    for name in names:
        lines.extend(
            [
                f"## {name}",
                "- Tone: grounded and clear",
                "- Pace: medium",
                "- Energy: natural, controlled",
                "- Likeness: no real-person mimicry",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _dialogue_lines_by_shot(
    shots: list[dict[str, object]],
    units: list[dict[str, object]],
) -> list[tuple[str, list[tuple[str, str]]]]:
    out: list[tuple[str, list[tuple[str, str]]]] = []
    for index, shot in enumerate(shots):
        shot_id = str(shot["shot_id"])
        unit_text = str(units[index].get("text", "")).strip() if index < len(units) else ""
        pairs = _extract_dialogue_pairs(unit_text)
        if pairs:
            out.append((shot_id, pairs))
    return out


def _render_dialogue_script(shots: list[dict[str, object]], units: list[dict[str, object]]) -> str:
    shot_dialogue = _dialogue_lines_by_shot(shots, units)
    lines = [
        "Dialogue Script (Audio in Post)",
        "External audio reference. Do not burn subtitles into picture.",
        "",
    ]
    if not shot_dialogue:
        lines.extend(["No dialogue lines detected in this package.", ""])
        return "\n".join(lines).rstrip() + "\n"
    for shot_id, pairs in shot_dialogue:
        lines.append(shot_id)
        for speaker, line in pairs:
            lines.append(f"{speaker}: {line}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_sfx_cue_sheet(shots: list[dict[str, object]], units: list[dict[str, object]]) -> str:
    keyword_cues = [
        ("server", "server hum"),
        ("footstep", "footsteps"),
        ("walk", "footsteps"),
        ("keyboard", "keyboard taps"),
        ("type", "keyboard taps"),
        ("door", "door"),
        ("breath", "breathing"),
        ("sigh", "breathing"),
        ("pant", "breathing"),
        ("rain", "rain"),
        ("wind", "wind"),
        ("phone", "phone ring"),
        ("alarm", "alarm"),
        ("car", "engine rumble"),
        ("engine", "engine rumble"),
    ]
    lines = ["# SFX Cue Sheet", "", "Conservative cues for post sound design.", ""]
    for index, shot in enumerate(shots):
        shot_id = str(shot["shot_id"])
        text = str(units[index].get("text", "")).lower() if index < len(units) else ""
        cues: list[str] = []
        for keyword, cue in keyword_cues:
            if keyword in text and cue not in cues:
                cues.append(cue)
        if not cues:
            cues = ["ambient room tone"]
        lines.append(f"## {shot_id}")
        for cue in cues:
            lines.append(f"- {cue}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _format_srt_timestamp(seconds: float) -> str:
    millis = max(int(round(seconds * 1000)), 0)
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _render_subtitles_srt(shots: list[dict[str, object]], units: list[dict[str, object]]) -> str:
    shot_dialogue = _dialogue_lines_by_shot(shots, units)
    lines: list[str] = []
    cue_index = 1
    elapsed = 0.0
    dialogue_by_shot = {shot_id: pairs for shot_id, pairs in shot_dialogue}

    for shot in shots:
        shot_id = str(shot["shot_id"])
        duration = float(shot.get("duration_s", 0) or 0)
        window_start = elapsed
        window_end = elapsed + max(duration, 0.1)
        pairs = dialogue_by_shot.get(shot_id, [])
        if pairs:
            slot = (window_end - window_start) / len(pairs)
            for i, (speaker, line) in enumerate(pairs):
                start = window_start + (i * slot)
                end = window_start + ((i + 1) * slot)
                if i < len(pairs) - 1:
                    end = max(start + 0.2, end - 0.05)
                lines.extend(
                    [
                        str(cue_index),
                        f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                        f"{speaker}: {line}",
                        "",
                    ]
                )
                cue_index += 1
        elapsed = window_end

    if not lines:
        lines = [
            "1",
            "00:00:00,000 --> 00:00:01,000",
            "[No dialogue]",
            "",
        ]
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
    generated_at: str,
    creator_guide_renderer_used: str,
    creator_guide_error: str,
) -> str:
    heading = scene.get("heading", {})
    heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
    payload = {
        "rpack_version": "0.1",
        "target_provider": target_provider,
        "target_provider_version": target_provider_version,
        "source": {"filename": source_name, "hash": source_hash},
        "generator": {"name": "RenderScript AI", "version": __version__},
        "generated_at": generated_at,
        "scene": {
            "scene_id": str(scene.get("id", "")),
            "heading_raw": str(heading_raw),
            "ordinal": int(scene.get("ordinal", 0)),
        },
        "shots": shots,
        "bindings": bindings,
        "required_references": required_refs,
        "risk_flags": [],
        "debug": {
            "creator_guide": {
                "renderer_used": creator_guide_renderer_used,
                "error": creator_guide_error,
            }
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_deterministic_zip(output_path: Path, files: dict[str, str | bytes], ordered_paths: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_STORED) as zf:
        for path in ordered_paths:
            info = ZipInfo(path)
            info.date_time = ZIP_FIXED_DATETIME
            info.compress_type = ZIP_STORED
            if path.endswith("/"):
                info.external_attr = 0o40755 << 16
                content_bytes = b""
            else:
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
    provider: str = DEFAULT_PROVIDER,
    provider_version: str = "",
    include_provider_prompts: list[str] | None = None,
    scene_ordinal: int | None = None,
    duration_s: int = 3,
    project: str = "project",
) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        supported_str = ", ".join(SUPPORTED_PROVIDERS)
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: {supported_str}")

    text = input_path.read_text(encoding="utf-8")
    doc = compile_fountain_text(text, source_name=input_path.name)
    source = doc.get("meta", {}).get("source", {}) if isinstance(doc.get("meta", {}), dict) else {}
    source_hash = source.get("hash", "") if isinstance(source, dict) else ""
    generated_at = _now_iso_utc()
    selected_scene = _extract_scene(doc, scene_ordinal)
    prompt_filename = _prompt_filename_for_provider(provider)
    prompt_files = _prompt_files_for_package(provider=provider, include_provider_prompts=include_provider_prompts)
    ordered_paths = _required_files(prompt_files)
    speaker_by_id = _speaker_lookup(doc)
    resolved_output_path = _resolve_output_path(
        output_path=output_path,
        project=project,
        selected_scene=selected_scene,
        provider=provider,
    )
    shots, shot_units, _ = _build_shots(selected_scene, doc=doc, duration_s=duration_s)
    bindings, required_refs = _build_bindings(shots, units=shot_units, doc=doc)
    character_ref_by_speaker = _character_ref_lookup(speaker_by_id)
    speaker_by_character_ref = {ref_id: speaker_id for speaker_id, ref_id in character_ref_by_speaker.items()}
    character_name_by_ref: dict[str, str] = {}
    character_refs_for_prompts: list[tuple[str, str]] = []
    for ref_id in required_refs["character_ref_ids"]:
        speaker_id = speaker_by_character_ref.get(ref_id, "")
        speaker_name = speaker_by_id.get(speaker_id, speaker_id)
        if speaker_name:
            display_name = speaker_name.title()
            character_name_by_ref[ref_id] = display_name
            character_refs_for_prompts.append((ref_id, display_name))

    location_label = _scene_location_label(selected_scene)
    shot_rows = []
    for idx, shot in enumerate(shots):
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        unit = shot_units[idx] if idx < len(shot_units) else {}
        beat_text = str(shot.get("beat", "")).strip()
        shot_type = _shot_type_for_unit(unit, str(shot.get("framing", "")), idx + 1)
        camera = _camera_for_shot_type(shot_type)
        description = _description_from_unit_text(beat_text)
        character_names = [character_name_by_ref.get(ref_id, ref_id) for ref_id in shot_bindings["character_ref_ids"]]
        shot_rows.append(
            [
                shot_id,
                "",
                _short_beat_label(beat_text),
                shot_type,
                camera,
                description,
                ";".join(character_names),
                location_label,
                shot_bindings["style_ref_ids"][0] if shot_bindings["style_ref_ids"] else "",
                f"{shot['duration_s']}s",
            ]
        )

    bindings_rows = []
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        bindings_rows.append(
            [
                shot_id,
                ";".join(shot_bindings["character_ref_ids"]),
                ";".join(shot_bindings["location_ref_ids"]),
                ";".join(shot_bindings["style_ref_ids"]),
                ";".join(shot_bindings["prop_ref_ids"]),
                "Dialogue-driven shot" if shot_bindings["character_ref_ids"] else "",
            ]
        )

    guide_result = render_creator_guide_pdf(
        prompt_filename,
        asset_prompts_path=ASSET_PROMPTS_FILENAME,
        provider=provider,
        version=__version__,
        logo_path=Path(__file__).resolve().parent / "assets/branding/renderscript_logo_mark_blue_pad5.png",
        scene_heading=str(selected_scene.get("heading", {}).get("raw", ""))
        if isinstance(selected_scene.get("heading", {}), dict)
        else "",
        scene_id=str(selected_scene.get("id", "")),
        shot_count=len(shots),
        example_scene_lines=_scene_summary_lines(selected_scene, speaker_by_id),
    )

    files: dict[str, str | bytes] = {
        "START_HERE.txt": _render_start_here(),
        RPACK_FILENAME: _render_rpack_json(
            source_name=input_path.name,
            source_hash=str(source_hash),
            target_provider=provider,
            target_provider_version=provider_version,
            scene=selected_scene,
            shots=shots,
            bindings=bindings,
            required_refs=required_refs,
            generated_at=generated_at,
            creator_guide_renderer_used=guide_result.renderer_used,
            creator_guide_error=guide_result.error,
        ),
        PROVENANCE_FILENAME: _render_provenance_json(
            source_name=input_path.name,
            source_hash=str(source_hash),
            provider=provider,
            prompt_filename=prompt_filename,
            generated_at=generated_at,
            guide_debug_text=guide_result.debug_text,
        ),
        "PACKAGE_MAP.md": _render_package_map(provider, prompt_filename),
        CREATOR_GUIDE_FILENAME: guide_result.pdf_bytes,
        "assets/ingredients_manifest.md": _render_ingredients_manifest(required_refs),
        ASSET_PROMPTS_FILENAME: _render_asset_prompts(
            selected_scene,
            shots=shots,
            character_refs=character_refs_for_prompts,
        ),
        "assets/refs/styles/": b"",
        "assets/refs/locations/": b"",
        "assets/refs/characters/": b"",
        "assets/refs/props/": b"",
        VOICE_BIBLE_FILENAME: _render_voice_bible(speaker_by_id),
        DIALOGUE_SCRIPT_FILENAME: _render_dialogue_script(shots=shots, units=shot_units),
        SFX_CUE_SHEET_FILENAME: _render_sfx_cue_sheet(shots=shots, units=shot_units),
        SUBTITLES_FILENAME: _render_subtitles_srt(shots=shots, units=shot_units),
        "shots/shot_list.csv": _to_csv(
            headers=[
                "shot_id",
                "status",
                "beat",
                "shot_type",
                "camera",
                "description",
                "characters",
                "location",
                "style_ref",
                "duration_hint",
            ],
            rows=shot_rows,
        ),
        BINDINGS_FILENAME: _to_csv(
            headers=[
                "shot_id",
                "character_refs",
                "location_refs",
                "style_refs",
                "prop_refs",
                "notes",
            ],
            rows=bindings_rows,
        ),
        KEEPER_SHEET_FILENAME: _render_scoring_sheet(shots),
        UNIVERSAL_PROMPTS_FILENAME: _render_prompts(shots, bindings, provider=DEFAULT_PROVIDER),
    }
    if RUNWAY_PROMPTS_FILENAME in prompt_files:
        files[RUNWAY_PROMPTS_FILENAME] = _render_prompts(shots, bindings, provider=RUNWAY_PROVIDER)
    _write_deterministic_zip(resolved_output_path, files, ordered_paths=ordered_paths)
