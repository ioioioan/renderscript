from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from .compiler import compile_fountain_text


SUPPORTED_PROVIDER = "runway.gen4_image_refs"
PROMPTS_FILENAME = "prompts/runway.gen4_image_refs_prompts.md"
REQUIRED_FILES = [
    "rpack.json",
    "README.md",
    "assets/ingredients_manifest.md",
    "shots/shot_list.csv",
    "bindings/bindings.csv",
    PROMPTS_FILENAME,
]
ZIP_FIXED_DATETIME = (1980, 1, 1, 0, 0, 0)


def _render_readme() -> str:
    return (
        "# How to run this RenderPackage in Runway Gen-4 Image References\n\n"
        "This package is prepared for `runway.gen4_image_refs` workflows.\n\n"
        "## Drift warnings\n\n"
        "- Reference quality and consistency still depend on source image quality.\n"
        "- Overly broad prompt edits can reduce visual continuity across shots.\n"
        "- Re-check identity, wardrobe, and location consistency after each run.\n\n"
        "## Steps\n\n"
        "1. Open Runway and start a Gen-4 image generation workflow.\n"
        "2. Enable **References** for the generation task.\n"
        "3. For each shot, review required references in `bindings/bindings.csv`.\n"
        "4. Add up to 3 references in Runway for that shot as needed.\n"
        "5. Paste the shot prompt from `prompts/runway.gen4_image_refs_prompts.md`.\n"
        "6. Generate, review drift, and iterate while preserving shot intent.\n"
    )


def _render_ingredients_manifest() -> str:
    return (
        "# Ingredients Manifest\n\n"
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
        "- `loc_01_ref_01`\n"
        "- `style_01_ref_01`\n"
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


def _build_shots(scene: dict[str, object]) -> list[dict[str, object]]:
    heading = scene.get("heading", {})
    heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
    return [
        {
            "shot_id": "shot_001",
            "duration_s": 5,
            "framing": "wide",
            "beat": f"Whole scene: {heading_raw}",
            "notes": "RP1 placeholder shot",
            "risk_flags": [],
        }
    ]


def _build_bindings(shots: list[dict[str, object]]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for shot in shots:
        shot_id = str(shot["shot_id"])
        out[shot_id] = {
            "character_ref_ids": [],
            "location_ref_ids": [],
            "style_ref_ids": [],
            "prop_ref_ids": [],
        }
    return out


def _render_prompts(shots: list[dict[str, object]], bindings: dict[str, dict[str, list[str]]]) -> str:
    lines = ["# Runway Gen-4 Image References Prompts", ""]
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        lines.append(f"## {shot_id}")
        lines.append("")
        lines.append(f"Prompt: {shot['beat']}. {shot['notes']}.")
        lines.append("Required references:")
        lines.append(f"- character_ref_ids: {', '.join(shot_bindings['character_ref_ids']) or 'none'}")
        lines.append(f"- location_ref_ids: {', '.join(shot_bindings['location_ref_ids']) or 'none'}")
        lines.append(f"- style_ref_ids: {', '.join(shot_bindings['style_ref_ids']) or 'none'}")
        lines.append(f"- prop_ref_ids: {', '.join(shot_bindings['prop_ref_ids']) or 'none'}")
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
        "risk_flags": [],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_deterministic_zip(output_path: Path, files: dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_STORED) as zf:
        for path in REQUIRED_FILES:
            info = ZipInfo(path)
            info.date_time = ZIP_FIXED_DATETIME
            info.compress_type = ZIP_STORED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, files[path].encode("utf-8"))


def package_fountain_file(
    input_path: Path,
    output_path: Path,
    provider: str,
    provider_version: str = "",
    scene_ordinal: int | None = None,
) -> None:
    if provider != SUPPORTED_PROVIDER:
        raise ValueError(f"Unsupported provider: {provider}. Supported providers: {SUPPORTED_PROVIDER}")

    text = input_path.read_text(encoding="utf-8")
    doc = compile_fountain_text(text, source_name=input_path.name)
    source = doc.get("meta", {}).get("source", {}) if isinstance(doc.get("meta", {}), dict) else {}
    source_hash = source.get("hash", "") if isinstance(source, dict) else ""
    selected_scene = _extract_scene(doc, scene_ordinal)
    shots = _build_shots(selected_scene)
    bindings = _build_bindings(shots)

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

    files = {
        "rpack.json": _render_rpack_json(
            source_name=input_path.name,
            source_hash=str(source_hash),
            target_provider=provider,
            target_provider_version=provider_version,
            scene=selected_scene,
            shots=shots,
            bindings=bindings,
        ),
        "README.md": _render_readme(),
        "assets/ingredients_manifest.md": _render_ingredients_manifest(),
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
        PROMPTS_FILENAME: _render_prompts(shots, bindings),
    }
    _write_deterministic_zip(output_path, files)
