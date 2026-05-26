from __future__ import annotations

import csv
import io
import json
import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo
from xml.sax.saxutils import escape as xml_escape

from . import __version__
from .compiler import compile_fountain_text
from .pdf_guide import PROGRESS_TEXT, CreatorGuideRenderResult, _logo_uri, render_template_pdf
from .providers import (
    DEFAULT_PROVIDER,
    GROK_PROVIDER,
    RUNWAY_PROVIDER,
    SUPPORTED_PROVIDERS,
    get_provider,
)
from .versions import (
    PROMPT_TUNER_VERSION,
    RENDERPACKAGE_SPEC_VERSION,
    RENDERSCRIPT_STUDIO_VERSION,
    RSCRIPT_SCHEMA_VERSION,
)

RENDERPACKAGE_FILENAME = "RENDERPACKAGE.pdf"
COPY_PASTE_PROMPTS_FILENAME = "COPY_PASTE_PROMPTS.docx"
KEEPER_SHEET_FILENAME = "KEEPER_SHEET.csv"
GENERATED_TAKES_DIR = "generated_shots/takes/"
GENERATED_KEEPERS_DIR = "generated_shots/keepers/"
PROMPT_PACKS_DIR = "DEVELOPER_FILES/prompt_packs"
REFERENCE_PROMPTS_FILENAME = "prompts/reference_prompts.md"
UNIVERSAL_PROMPTS_FILENAME = f"{PROMPT_PACKS_DIR}/shot_prompts.md"
RUNWAY_PROMPTS_FILENAME = f"{PROMPT_PACKS_DIR}/runway.gen4_image_refs_prompts.md"
GROK_PROMPTS_FILENAME = f"{PROMPT_PACKS_DIR}/grok.imagine_prompts.md"
BINDINGS_FILENAME = "DEVELOPER_FILES/bindings.csv"
SHOT_LIST_FILENAME = "DEVELOPER_FILES/shot_list.csv"
PACKAGE_MAP_FILENAME = "DEVELOPER_FILES/package_map.md"
RPACK_FILENAME = "DEVELOPER_FILES/rpack.json"
PROVENANCE_FILENAME = "DEVELOPER_FILES/provenance.json"
AGENT_ORCHESTRATION_FILENAME = "DEVELOPER_FILES/AGENT_ORCHESTRATION.md"
PROVIDER_CAPABILITIES_EXAMPLE_FILENAME = "DEVELOPER_FILES/provider_capabilities.example.json"
ACTION_PLAN_FILENAME = "DEVELOPER_FILES/action_plan.json"
EXECUTION_CONTRACT_FILENAME = "DEVELOPER_FILES/execution_contract.json"
APPROVAL_CHECKPOINTS_FILENAME = "DEVELOPER_FILES/approval_checkpoints.json"
TAKE_LOG_FILENAME = "DEVELOPER_FILES/take_log.csv"
KEEPER_DECISIONS_FILENAME = "DEVELOPER_FILES/keeper_decisions.csv"
ASSET_REFS_DIR = "assets/refs/"
ASSET_REFERENCE_DIRS = [
    "assets/",
    ASSET_REFS_DIR,
    "assets/refs/characters/",
    "assets/refs/locations/",
    "assets/refs/props/",
    "assets/refs/costumes/",
    "assets/refs/vehicles/",
    "assets/refs/creatures/",
    "assets/refs/style/",
    "assets/refs/lighting/",
    "assets/refs/vfx/",
]
AUDIO_DIR = "audio/"
AUDIO_VOICE_BIBLE_FILENAME = "audio/voice_bible.md"
VOICE_REFS_DIR = "audio/character_voice_refs/"
VOICE_SAMPLES_DIR = "audio/voice_samples/"
BASE_REQUIRED_FILES = [
    "DEVELOPER_FILES/",
    RPACK_FILENAME,
    PROVENANCE_FILENAME,
    SHOT_LIST_FILENAME,
    BINDINGS_FILENAME,
    AGENT_ORCHESTRATION_FILENAME,
    PROVIDER_CAPABILITIES_EXAMPLE_FILENAME,
    ACTION_PLAN_FILENAME,
    EXECUTION_CONTRACT_FILENAME,
    APPROVAL_CHECKPOINTS_FILENAME,
    TAKE_LOG_FILENAME,
    KEEPER_DECISIONS_FILENAME,
    f"{PROMPT_PACKS_DIR}/",
    UNIVERSAL_PROMPTS_FILENAME,
    RUNWAY_PROMPTS_FILENAME,
    GROK_PROMPTS_FILENAME,
    PACKAGE_MAP_FILENAME,
]
ZIP_FIXED_DATETIME = (1980, 1, 1, 0, 0, 0)
MIN_SHOTS = 8
MAX_SHOTS = 12
FRAMING_CYCLE = ("wide", "medium", "close")
REFERENCE_ASSET_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
VOICE_ASSET_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
REFERENCE_TYPE_PLURALS = {
    "character": "characters",
    "location": "locations",
    "prop": "props",
    "costume": "costumes",
    "vehicle": "vehicles",
    "creature": "creatures",
    "style": "style",
    "lighting": "lighting",
    "vfx": "vfx",
}


def _prompt_filename_for_provider(provider: str) -> str:
    get_provider(provider)
    if provider == RUNWAY_PROVIDER:
        return RUNWAY_PROMPTS_FILENAME
    if provider == GROK_PROVIDER:
        return GROK_PROMPTS_FILENAME
    return UNIVERSAL_PROMPTS_FILENAME


def _required_files(prompt_files: list[str]) -> list[str]:
    return list(BASE_REQUIRED_FILES)


def _prompt_files_for_package(provider: str, include_provider_prompts: list[str] | None = None) -> list[str]:
    get_provider(provider)
    for extra in include_provider_prompts or []:
        get_provider(extra)
    return [UNIVERSAL_PROMPTS_FILENAME, RUNWAY_PROMPTS_FILENAME, GROK_PROMPTS_FILENAME]


def _selected_providers(provider: str, include_provider_prompts: list[str] | None = None) -> list[str]:
    selected = [DEFAULT_PROVIDER]
    if provider != DEFAULT_PROVIDER:
        selected.append(provider)
    for extra in include_provider_prompts or []:
        get_provider(extra)
        if extra != DEFAULT_PROVIDER and extra not in selected:
            selected.append(extra)
    return selected


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    return safe or "project"


def _source_screenplay_filename(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix not in {".fountain", ".fnt"}:
        suffix = ".fountain"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", input_path.stem.strip()).strip("_")
    return f"{stem or 'source_screenplay'}{suffix}"


def _slug_name(name: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    safe = safe.strip("_")
    return safe or "reference"


def _reference_id_from_path(path: str) -> str:
    return path.rstrip("/").split("/")[-1] if path else ""


def _asset_reference_folder_for_type(ref_type: str) -> str:
    folder = REFERENCE_TYPE_PLURALS.get(ref_type, ref_type or "style")
    return f"assets/refs/{folder}/"


def _list_from_multiline(value: str) -> list[str]:
    items: list[str] = []
    for raw in str(value or "").splitlines():
        item = raw.strip().lstrip("-").strip()
        if item:
            items.append(item)
    return items


def _dedupe_ordered(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


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
    rows = [[str(shot["shot_id"]), "", "", ""] for shot in shots]
    return _to_csv(
        headers=["shot_id", "keeper_take", "usable", "notes"],
        rows=rows,
    )


def _render_package_map(provider: str, prompt_path: str, selected_provider_ids: list[str]) -> str:
    workflow_line = "This package uses the Universal workflow."
    if provider != DEFAULT_PROVIDER:
        workflow_line = f"This package uses the {get_provider(provider).label} workflow."
    optional_lines: list[str] = []
    optional_provider_ids = [provider_id for provider_id in selected_provider_ids if provider_id != DEFAULT_PROVIDER]
    if optional_provider_ids:
        optional_labels = ", ".join(get_provider(provider_id).label for provider_id in optional_provider_ids)
        optional_files = ", ".join(f"`{_prompt_filename_for_provider(provider_id)}`" for provider_id in optional_provider_ids)
        optional_lines.append(f"- Optional provider prompt packs in this package: {optional_labels}.")
        optional_lines.append(f"- Optional provider prompt files: {optional_files}.")
    else:
        optional_lines.append("- Add optional provider prompt packs when you want tool-specific prompt formatting.")
    return (
        "# RenderPackage Map\n\n"
        "## Creator-facing files\n\n"
        f"- `{RENDERPACKAGE_FILENAME}`: main storyboard-led shooting pack.\n"
        f"- `{COPY_PASTE_PROMPTS_FILENAME}`: portable copy/paste prompts.\n"
        f"- `{KEEPER_SHEET_FILENAME}`: minimal keeper tracking sheet.\n\n"
        "- The source `.fountain` screenplay is included at the package root for reference.\n\n"
        "## Generated shot folders\n\n"
        f"- `{GENERATED_TAKES_DIR}`: suggested place to save generated test takes.\n"
        f"- `{GENERATED_KEEPERS_DIR}`: suggested place to save selected keeper clips.\n\n"
        "## Reference folders\n\n"
        "- Human-readable folders under `refs/` are generated automatically for extracted reference candidates.\n"
        f"- Structured reference prompts are collected in `{REFERENCE_PROMPTS_FILENAME}`.\n"
        f"- Structured visual reference notes live under `{ASSET_REFS_DIR}`.\n"
        f"- Voice continuity scaffolds live in `{AUDIO_VOICE_BIBLE_FILENAME}` and `{VOICE_REFS_DIR}`.\n"
        "- Creators manually attach or upload those images in their AI video tool.\n\n"
        "## Developer files\n\n"
        f"- Machine-readable source of truth: `{RPACK_FILENAME}`.\n"
        f"- Build/provenance metadata: `{PROVENANCE_FILENAME}`.\n"
        f"- Shot list: `{SHOT_LIST_FILENAME}`.\n"
        f"- Reference bindings: `{BINDINGS_FILENAME}`.\n"
        f"- Prompt packs: `{PROMPT_PACKS_DIR}/`.\n"
        f"- {workflow_line}\n"
        f"- Selected prompt profile: `{prompt_path}`.\n"
        + "\n".join(optional_lines)
        + "\n\n"
        "## Agent orchestration\n\n"
        f"- `{AGENT_ORCHESTRATION_FILENAME}` explains how external/local agents can consume this package.\n"
        f"- `{ACTION_PLAN_FILENAME}` describes model-agnostic shot execution steps.\n"
        f"- `{EXECUTION_CONTRACT_FILENAME}` defines responsibilities, limits, and human approval boundaries.\n"
        f"- `{APPROVAL_CHECKPOINTS_FILENAME}` defines prompt, reference, take, keeper, and revision approvals.\n"
        f"- `{TAKE_LOG_FILENAME}` and `{KEEPER_DECISIONS_FILENAME}` are empty templates for downstream tracking.\n"
        f"- `{PROVIDER_CAPABILITIES_EXAMPLE_FILENAME}` is a template for optional workflow capability hints.\n"
        f"- `{RPACK_FILENAME}` remains the machine-readable source of truth.\n"
        "- RenderPackage is agent-actionable, not auto-executable.\n"
        "- Agents should use the package after it is generated; they should not recreate the RenderPackage or expect it to run code.\n\n"
        "Creator workflow does not depend on opening this folder.\n"
    )


def _render_agent_orchestration_md() -> str:
    return (
        "# Agent Orchestration\n\n"
        "This RenderPackage has already been generated.\n\n"
        "An agent should not recreate the package.\n"
        "An agent should consume this package as a workflow contract for downstream AI-video generation.\n"
        "RenderPackage is agent-actionable, not auto-executable: it contains data, instructions, prompts, and approval checkpoints, not runnable workflow code.\n\n"
        "## Source of truth\n\n"
        "Use:\n\n"
        "DEVELOPER_FILES/rpack.json\n\n"
        "as the machine-readable source of truth.\n\n"
        "Use creator-facing files only for human review.\n\n"
        "## Continuity and reference rules\n\n"
        "- Use approved references only as continuity anchors.\n"
        "- Do not invent final character, voice, prop, location, style, lighting, or effect references silently.\n"
        "- Treat character sheets as visual continuity anchors only after creator approval.\n"
        "- Treat Voice Bible entries as speech-performance continuity anchors only after creator approval.\n"
        "- Treat uploaded assets as source references, not optional decoration.\n"
        "- Preserve locked visual anchors across generated shots.\n"
        "- Preserve accent, pace, tone, rhythm, volume, and delivery style across dialogue generation.\n"
        "- If a reference is missing or ambiguous, ask for creator approval or use only the approved scaffold.\n\n"
        "## Agent workflow\n\n"
        "1. Read DEVELOPER_FILES/rpack.json\n"
        "2. Load the scene metadata\n"
        "3. Load the shot list\n"
        "4. For each shot, read:\n"
        "   - shot ID\n"
        "   - shot intent\n"
        "   - base prompt\n"
        "   - required references\n"
        "   - suggested framing\n"
        "   - post-production notes where available\n"
        "5. Check whether required reference folders contain user-provided assets\n"
        "6. If references are missing, ask the user to add them or use a separate image-generation workflow\n"
        "7. Ask the user which AI-video tool or agent-assisted workflow to use\n"
        "8. Map the shot data to that approved execution route\n"
        "9. Prepare generation tasks using:\n"
        "   - base prompt\n"
        "   - selected references\n"
        "   - provider settings\n"
        "   - shot ID\n"
        "10. Submit generation jobs only when the user has configured external access and approved the action\n"
        "11. Poll or monitor generation jobs only if the external workflow supports it\n"
        "12. Save generated takes using shot IDs\n"
        "13. Preserve provider settings and provenance\n"
        "14. Let the creator choose keepers, or assist with keeper review if explicitly supported\n"
        "15. Update keeper/provenance outputs\n\n"
        "## Boundaries\n\n"
        "The agent must not assume:\n"
        "- provider API access exists\n"
        "- provider capabilities are available\n"
        "- references will be accepted by every tool\n"
        "- output will be deterministic\n"
        "- lip-sync will be accurate\n"
        "- exact duration will be obeyed\n"
        "- the first generation will be usable\n\n"
        "## Human-in-the-loop rule\n\n"
        "The creator remains responsible for:\n"
        "- creative judgment\n"
        "- prompt tuning\n"
        "- selecting keepers\n"
        "- editing\n"
        "- final dialogue/audio\n"
        "- post-production polish\n\n"
        "## File handling\n\n"
        "Generated takes should be saved using shot IDs.\n\n"
        "Preferred naming:\n\n"
        "shot_001_take_01.mp4\n"
        "shot_001_take_02.mp4\n"
        "shot_001_keeper.mp4\n\n"
        "Use the package folders:\n\n"
        "generated_shots/takes/\n"
        "generated_shots/keepers/\n\n"
        "If an agent creates per-shot subfolders, keep them under generated_shots/takes/.\n\n"
        "Do not place generated media inside DEVELOPER_FILES.\n\n"
        "## Optional execution templates\n\n"
        "Execution templates may translate RenderPackage data into workflow-specific requests.\n"
        "Universal prompts remain canonical; agent-assisted workflows are optional, while downstream AI-video tools are creator-selected execution targets.\n\n"
        "Templates may use:\n"
        "- base prompts\n"
        "- reference folders\n"
        "- shot metadata\n"
        "- duration/editing targets\n"
        "- optional capability hints\n\n"
        "Templates must not claim:\n"
        "- deterministic output\n"
        "- guaranteed continuity\n"
        "- guaranteed lip-sync\n"
        "- finished-film quality\n\n"
        "## Safety and provenance\n\n"
        "Agents should preserve:\n"
        "- shot ID\n"
        "- prompt text used\n"
        "- reference assets used\n"
        "- provider name\n"
        "- provider settings\n"
        "- generation timestamp\n"
        "- output filename\n"
        "- user keeper choice where available\n"
    )


def _render_provider_capabilities_example_json() -> str:
    payload = {
        "provider": "example_provider",
        "adapter_id": "example.provider",
        "execution_template_id": "example.provider",
        "supports_text_to_video": True,
        "supports_image_references": True,
        "supports_video_references": False,
        "supports_audio_references": False,
        "supports_keyframes": False,
        "supports_task_polling": True,
        "supports_batch_generation": False,
        "supports_download": True,
        "max_reference_images_per_generation": 3,
        "duration_control": "provider_setting",
        "notes": "Example capability hint only. Real execution templates must verify workflow behaviour.",
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_action_plan_json(agent_shots: list[dict[str, object]], reference_rows: list[dict[str, str]]) -> str:
    references = [
        {
            "folder": row.get("path", ""),
            "type": row.get("type", ""),
            "label": row.get("name", ""),
            "base_prompt": row.get("base_prompt", ""),
        }
        for row in reference_rows
    ]
    steps: list[dict[str, object]] = [
        {
            "step": "review_package",
            "description": "Read creator-facing files and DEVELOPER_FILES/rpack.json before any generation work.",
            "requires_human_approval": False,
        },
        {
            "step": "approve_prompts",
            "description": "Human reviews reference and shot prompts before generation.",
            "requires_human_approval": True,
        },
        {
            "step": "approve_references",
            "description": "Human confirms reference assets are present and match the intended look.",
            "requires_human_approval": True,
        },
    ]
    for shot in agent_shots:
        steps.append(
            {
                "step": "generate_takes",
                "shot_id": shot.get("shot_id", ""),
                "description": "Generate candidate takes using the canonical prompt and listed references in the selected external workflow.",
                "prompt": shot.get("base_prompt", ""),
                "references": shot.get("references", []),
                "take_path": GENERATED_TAKES_DIR,
                "requires_human_approval": True,
            }
        )
    steps.extend(
        [
            {
                "step": "review_takes",
                "description": "Human reviews generated takes for continuity, shot usefulness, and edit fit.",
                "requires_human_approval": True,
            },
            {
                "step": "select_keepers",
                "description": "Record selected keepers in keeper_decisions.csv and place selected clips under generated_shots/keepers/.",
                "requires_human_approval": True,
            },
        ]
    )
    payload = {
        "schema": "renderscript.action_plan.v1",
        "non_executable": True,
        "source_of_truth": RPACK_FILENAME,
        "canonical_prompt_pack": UNIVERSAL_PROMPTS_FILENAME,
        "references": references,
        "steps": steps,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_execution_contract_json(selected_provider_ids: list[str]) -> str:
    payload = {
        "schema": "renderscript.execution_contract.v1",
        "non_executable": True,
        "renderpackage_is": "agent-actionable, not auto-executable",
        "responsibilities": {
            "renderscript": [
                "compile the screenplay scene",
                "export the RenderPackage",
                "provide canonical prompts, references, shot data, and orchestration files",
            ],
            "creator": [
                "approve prompts",
                "approve reference assets",
                "choose the external AI-video workflow",
                "review generated takes",
                "select keepers",
                "edit and finish the scene",
            ],
            "agent_or_external_workflow": [
                "read package data",
                "prepare generation tasks from approved prompts and references",
                "log generated takes when configured",
                "assist keeper review only when explicitly asked",
            ],
        },
        "limits": [
            "No provider access is assumed.",
            "No video generation is performed by RenderScript.",
            "No deterministic continuity is promised.",
            "No executable workflow files are included in the standard package.",
            "Universal prompts are canonical; optional prompt packs are example execution templates.",
        ],
        "selected_execution_profiles": selected_provider_ids,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_approval_checkpoints_json() -> str:
    payload = {
        "schema": "renderscript.approval_checkpoints.v1",
        "non_executable": True,
        "checkpoints": [
            {
                "id": "prompt_approval",
                "label": "Prompt approval",
                "description": "Creator approves reference and shot prompts before generation.",
                "required": True,
            },
            {
                "id": "reference_approval",
                "label": "Reference approval",
                "description": "Creator approves style, location, character, and prop references before generation.",
                "required": True,
            },
            {
                "id": "take_review",
                "label": "Take review",
                "description": "Creator reviews generated takes for continuity, performance, and usefulness.",
                "required": True,
            },
            {
                "id": "keeper_selection",
                "label": "Keeper selection",
                "description": "Creator selects keeper takes and records decisions.",
                "required": True,
            },
            {
                "id": "revision_decisions",
                "label": "Revision decisions",
                "description": "Creator decides whether to revise prompts, references, or generation settings.",
                "required": True,
            },
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


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
    prompt_tuner_metadata: dict[str, object] | None = None,
) -> str:
    debug = _parse_debug_text(guide_debug_text)
    payload = {
        "generator": {"name": "RenderScript AI", "version": __version__},
        "generated_at": generated_at,
        "source": {"filename": source_name, "hash": source_hash},
        "provider": provider,
        "prompt_profile": prompt_filename,
        "versions": {
            "renderscript_studio_version": RENDERSCRIPT_STUDIO_VERSION,
            "prompt_tuner_version": PROMPT_TUNER_VERSION,
            "renderpackage_spec_version": RENDERPACKAGE_SPEC_VERSION,
            "rscript_schema_version": RSCRIPT_SCHEMA_VERSION,
        },
        "prompt_tuner": prompt_tuner_metadata
        or {
            "version": PROMPT_TUNER_VERSION,
            "edited": False,
            "edited_reference_prompts": [],
            "edited_shot_prompts": [],
        },
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


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_pdf_line(line: str, width: int = 88) -> list[str]:
    if not line:
        return [""]
    if len(line) <= width:
        return [line]
    return textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False) or [line]


def _pdf_page_stream(lines: list[str], start_y: int = 800) -> bytes:
    out = ["BT", "/F1 10 Tf", f"42 {start_y} Td", "13 TL"]
    for line in lines:
        if line in {
            "RENDERPACKAGE",
            "Scene Summary",
            "Shot Cards / Storyboard",
            "Reference Board",
            "Keeper Workflow",
            "Audio/Post Notes",
        }:
            out.append("/F1 16 Tf")
        elif line.startswith("Shot "):
            out.append("/F1 13 Tf")
        else:
            out.append("/F1 10 Tf")
        out.append(f"({_pdf_escape(line)}) Tj")
        out.append("T*")
    out.append("ET")
    return ("\n".join(out) + "\n").encode("latin-1", errors="replace")


def _render_text_pdf(pages: list[list[str]], title: str) -> bytes:
    wrapped_pages: list[list[str]] = []
    for page in pages:
        wrapped: list[str] = []
        for line in page:
            wrapped.extend(_wrap_pdf_line(line))
        wrapped_pages.append(wrapped)

    streams = [_pdf_page_stream(page) for page in wrapped_pages]
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_ids = [3 + i for i in range(len(wrapped_pages))]
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(wrapped_pages)} >>".encode("ascii"))

    font_id = 3 + (2 * len(wrapped_pages))
    for idx in range(len(wrapped_pages)):
        content_id = 3 + len(wrapped_pages) + idx
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )

    for stream in streams:
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream")

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        (
            f"<< /Title ({_pdf_escape(title)}) /Author (renderscript) "
            "/Creator (renderscript) /Producer (renderscript) >>"
        ).encode("ascii")
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
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


def _branding_logo_uri() -> str | None:
    return _logo_uri(Path(__file__).resolve().parent / "assets/branding/renderscript_logo_mark_blue_pad5.png")


def _docx_paragraph(text: str, style: str | None = None) -> str:
    style_xml = f'<w:pStyle w:val="{style}"/>' if style else ""
    return (
        "<w:p>"
        f"<w:pPr>{style_xml}</w:pPr>"
        "<w:r>"
        f"<w:t xml:space=\"preserve\">{xml_escape(text)}</w:t>"
        "</w:r>"
        "</w:p>"
    )


def _render_docx_bytes(blocks: list[tuple[str, str | None]]) -> bytes:
    body = "".join(_docx_paragraph(text, style) for text, style in blocks)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>'
    )
    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
        "</w:styles>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        "</Types>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/></Relationships>'
    )

    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as zf:
        for path, content in [
            ("[Content_Types].xml", content_types_xml.encode("utf-8")),
            ("_rels/.rels", rels_xml.encode("utf-8")),
            ("word/document.xml", document_xml.encode("utf-8")),
            ("word/styles.xml", styles_xml.encode("utf-8")),
        ]:
            info = ZipInfo(path)
            info.date_time = ZIP_FIXED_DATETIME
            info.compress_type = ZIP_STORED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, content)
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


def _creator_beat_text(text: str, addressee: str = "") -> str:
    cleaned = _clean_prompt_sentence(text)
    reaction_match = re.match(r"Reaction on (.+?) as (.+?) lands the line:\s*(.+)$", cleaned, flags=re.IGNORECASE)
    if reaction_match:
        listener = reaction_match.group(1).strip().title()
        speaker = reaction_match.group(2).strip().title()
        line = reaction_match.group(3).strip()
        if line.lower().startswith("did you print the permit form"):
            return f"Reaction on {listener} as {speaker} asks, \"Did you print the permit form?\""
        return f"Reaction on {listener} as {speaker} asks a brief question."
    two_shot_match = re.match(r"Two-shot coverage holds (.+?) and (.+?) on the beat:\s*(.+)$", cleaned, flags=re.IGNORECASE)
    if two_shot_match:
        first = two_shot_match.group(1).strip().title()
        second = two_shot_match.group(2).strip().title()
        line = two_shot_match.group(3).strip()
        if line.lower().startswith("did you print the permit form"):
            return f"Two-shot coverage holds {first} and {second} as the permit question lands."
        return f"Two-shot coverage holds {first} and {second} through the dialogue beat."
    if ": " not in cleaned:
        return re.sub(r"\b[A-Z][A-Z0-9]{1,}\b", lambda match: match.group(0).title(), cleaned)
    speaker_raw, line_raw = cleaned.split(": ", 1)
    if len(speaker_raw.split()) > 4 or speaker_raw.lower().startswith(("reaction on", "two-shot", "hold on")):
        return cleaned
    speaker = re.sub(r"\([^)]*\)", "", speaker_raw)
    speaker = re.sub(r"\s+", " ", speaker).strip().title()
    parenthetical_match = re.search(r"\(([^)]*)\)", speaker_raw)
    parenthetical = parenthetical_match.group(1).strip().lower() if parenthetical_match else ""
    line = line_raw.strip()
    if not speaker or not line:
        return cleaned
    delivery = f" {parenthetical}" if parenthetical else ""
    normalized_line = line.rstrip("?!.").strip()
    lower_line = normalized_line.lower()
    if line.endswith("?"):
        if lower_line.startswith("did you print the permit form"):
            target = f" {addressee}" if addressee else ""
            return f"{speaker}{delivery} asks{target}, \"Did you print the permit form?\""
        target = f" {addressee}" if addressee else ""
        return f"{speaker}{delivery} asks{target} a brief question."
    if lower_line.startswith("it's in "):
        return f"{speaker}{delivery} answers, \"{line.rstrip('.')},\" with a quick practical response."
    verb = "says"
    return f"{speaker}{delivery} {verb} {line}"


def _format_prompt_line(beat: str, framing: str) -> str:
    cleaned_beat = _creator_beat_text(beat)
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


PROP_PHRASES = (
    "permit form",
    "tape measure",
    "city map",
    "map",
    "watch",
    "tote",
    "blue folder",
    "folder",
    "clipboard",
    "gaffer tape",
    "umbrella",
    "keys",
)


def _extract_prop_tokens(text: str, speaker_by_id: dict[str, str]) -> list[str]:
    speaker_names = {name.upper() for name in speaker_by_id.values()}
    props = [token for token in _extract_caps_tokens(text) if token.upper() not in speaker_names]
    lower = text.lower()
    for phrase in PROP_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lower, flags=re.IGNORECASE):
            label = phrase.replace("city ", "").title()
            if label not in props:
                props.append(label)
    return props


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
                "props": _extract_prop_tokens(action_text, speaker_by_id),
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
    return speaker.strip().title(), line.strip()


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
    normalized = re.sub(r"^(INT\.|EXT\.|INT/EXT\.|I/E\.)\s*", "", raw.strip(), flags=re.IGNORECASE)
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
    shot_prompt_by_id: dict[str, str] | None = None,
) -> str:
    provider_label = get_provider(provider).label
    if provider == DEFAULT_PROVIDER:
        title = "# Universal RenderPackage Prompts"
    else:
        title = f"# {provider_label} Prompts"
    lines = [
        title,
        "",
        "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS.",
        "Generate picture-only shots. Audio/dialogue will be added in post.",
        "",
        "> Drift warning: outputs can still vary; review each shot for continuity.",
        "",
    ]
    if provider == GROK_PROVIDER:
        lines.extend(
            [
                "Legacy example execution template only: this is not a supported RenderScript integration.",
                "Use this prompt pack only if you have independently validated the target workflow.",
                "",
            ]
        )
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
        elif provider == GROK_PROVIDER:
            lines.append(
                "Required ref IDs: "
                f"character={', '.join(shot_bindings['character_ref_ids']) or 'none'}, "
                f"location={', '.join(shot_bindings['location_ref_ids'])}, "
                f"style={', '.join(shot_bindings['style_ref_ids'])}"
            )
            lines.append(
                "How to apply refs: follow the target workflow's current reference-image limits, and keep the same approved refs on rerolls when supported."
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
        prompt = (shot_prompt_by_id or {}).get(shot_id) or _format_prompt_line(str(shot["beat"]), str(shot["framing"]))
        lines.append("Prompt: " + prompt)
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


def _scene_speaker_lookup(scene: dict[str, object], speaker_by_id: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    beats = scene.get("beats", [])
    if not isinstance(beats, list):
        return out
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        speaker_id = str(beat.get("speaker_id", "")).strip()
        if speaker_id and speaker_id in speaker_by_id:
            out[speaker_id] = speaker_by_id[speaker_id]
    return out


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
            text = _creator_beat_text(str(beat.get("text", "")))
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


def _scene_location_reference_label(scene: dict[str, object]) -> str:
    label = _scene_location_label(scene).replace("_", " ").strip()
    if not label or label == "scene location":
        return "Location reference"
    return f"{label.title()} reference"


def _location_context(scene: dict[str, object]) -> str:
    heading = scene.get("heading", {})
    heading_raw = str(heading.get("raw", "")).strip() if isinstance(heading, dict) else ""
    location = _scene_location_label(scene).replace("_", " ").strip()
    if heading_raw:
        time_match = re.search(r"\s-\s(.+)$", heading_raw)
        time_part = time_match.group(1).strip().lower() if time_match else ""
        if location and time_part:
            return f"{location.title()}, {time_part}."
        if location:
            return f"{location.title()}."
    return f"{location.title()}." if location else "Scene location."


def _prop_ref_lookup(units: list[dict[str, object]]) -> dict[str, str]:
    out: dict[str, str] = {}
    prop_lookup: dict[str, str] = {}
    for unit in units:
        for token in unit.get("props", []):
            prop = str(token).strip()
            if not prop:
                continue
            if prop not in prop_lookup:
                prop_lookup[prop] = f"prop_{len(prop_lookup) + 1:02d}_ref_01"
                out[prop_lookup[prop]] = f"{prop.title()} reference"
    return out


GARMENT_WORDS = (
    "coat",
    "jacket",
    "uniform",
    "dress",
    "suit",
    "shirt",
    "boots",
    "shoes",
    "hat",
    "scarf",
    "gloves",
    "hoodie",
    "robe",
    "armor",
    "armour",
    "mask",
)
VEHICLE_TERMS = (
    "car",
    "truck",
    "van",
    "bus",
    "train",
    "taxi",
    "motorcycle",
    "bike",
    "boat",
    "ship",
    "plane",
    "helicopter",
)
CREATURE_TERMS = (
    "creature",
    "monster",
    "alien",
    "horse",
    "wolf",
    "dragon",
)
LIGHTING_TERMS = (
    "neon",
    "flickering light",
    "flickers",
    "dim light",
    "moonlight",
    "harsh fluorescent",
    "backlit",
    "silhouette",
    "golden hour",
    "strobe",
)
VFX_TERMS = (
    "explosion",
    "sparks",
    "smoke",
    "fire",
    "lightning",
    "portal",
    "hologram",
    "shatters",
    "glitch",
)


def _action_texts(scene: dict[str, object]) -> list[str]:
    out: list[str] = []
    beats = scene.get("beats", [])
    if not isinstance(beats, list):
        return out
    for beat in beats:
        if not isinstance(beat, dict) or beat.get("type") != "action":
            continue
        text = re.sub(r"\s+", " ", str(beat.get("text", "")).strip())
        if text:
            out.append(text)
    return out


def _append_reference_candidate(
    out: list[dict[str, str]],
    seen: set[tuple[str, str]],
    ref_type: str,
    label: str,
    evidence: str,
) -> None:
    clean_label = re.sub(r"\s+", " ", label.strip()).strip(" .,:;")
    if not clean_label:
        return
    key = (ref_type, clean_label.lower())
    if key in seen:
        return
    seen.add(key)
    out.append(
        {
            "type": ref_type,
            "label": clean_label,
            "source": "screenplay_extraction",
            "extraction_basis": evidence[:180],
        }
    )


def _extract_costume_candidates(
    action_texts: list[str],
    character_names: list[str],
    out: list[dict[str, str]],
    seen: set[tuple[str, str]],
) -> None:
    garment_pattern = "|".join(re.escape(word) for word in GARMENT_WORDS)
    for text in action_texts:
        lower = text.lower()
        if not any(word in lower for word in GARMENT_WORDS):
            continue
        for character_name in character_names:
            match = re.search(
                rf"\b{re.escape(character_name)}\b[^.]*?\b(wears|wearing|dressed in|in a|in an)\b([^.;]*)",
                text,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            detail = match.group(2).strip(" ,")
            if not re.search(rf"\b(?:{garment_pattern})\b", detail, flags=re.IGNORECASE):
                continue
            _append_reference_candidate(out, seen, "costume", f"{character_name} {detail}", text)
        generic = re.search(
            rf"\b(wears|wearing|dressed in)\b([^.;]*\b(?:{garment_pattern})\b[^.;]*)",
            text,
            flags=re.IGNORECASE,
        )
        if generic:
            _append_reference_candidate(out, seen, "costume", generic.group(2).strip(" ,"), text)


def _extract_term_candidates(
    action_texts: list[str],
    terms: tuple[str, ...],
    ref_type: str,
    out: list[dict[str, str]],
    seen: set[tuple[str, str]],
) -> None:
    for text in action_texts:
        lower = text.lower()
        for term in terms:
            if re.search(rf"\b{re.escape(term)}s?\b", lower):
                _append_reference_candidate(out, seen, ref_type, term.title(), text)


def _extract_lighting_candidates(
    scene: dict[str, object],
    action_texts: list[str],
    out: list[dict[str, str]],
    seen: set[tuple[str, str]],
) -> None:
    heading = scene.get("heading", {})
    time_of_day = str(heading.get("time_of_day", "")).strip() if isinstance(heading, dict) else ""
    if time_of_day:
        _append_reference_candidate(out, seen, "lighting", f"{time_of_day.title()} lighting", str(heading.get("raw", "")))
    _extract_term_candidates(action_texts, LIGHTING_TERMS, "lighting", out, seen)


def _extract_reference_candidates(scene: dict[str, object], character_names: list[str]) -> list[dict[str, str]]:
    action_lines = _action_texts(scene)
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    _extract_costume_candidates(action_lines, character_names, out, seen)
    _extract_term_candidates(action_lines, VEHICLE_TERMS, "vehicle", out, seen)
    _extract_term_candidates(action_lines, CREATURE_TERMS, "creature", out, seen)
    _extract_lighting_candidates(scene, action_lines, out, seen)
    _extract_term_candidates(action_lines, VFX_TERMS, "vfx", out, seen)
    return out


def _reference_names_for_shot(
    shot_bindings: dict[str, list[str]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
) -> list[str]:
    names: list[str] = []
    if shot_bindings["style_ref_ids"]:
        names.append("Style reference")
    if shot_bindings["location_ref_ids"]:
        names.append(location_reference)
    for ref_id in shot_bindings["character_ref_ids"]:
        names.append(f"{character_name_by_ref.get(ref_id, 'Character')} reference")
    for ref_id in shot_bindings["prop_ref_ids"]:
        names.append(prop_name_by_ref.get(ref_id, "Prop reference"))
    return names


def _build_reference_rows(
    location_reference: str,
    character_names: list[str],
    prop_names: list[str],
    extra_references: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    rows = [
        {
            "name": "Style reference",
            "path": "refs/01_style_reference/",
            "type": "style",
            "purpose": "overall look, visual tone, and image style.",
            "source": "screenplay_extraction",
        },
        {
            "name": location_reference,
            "path": "refs/02_location_reference/",
            "type": "location",
            "purpose": "location layout, lighting, and environment.",
            "source": "screenplay_extraction",
        },
    ]
    next_index = 3
    for name in character_names:
        character_id = _slug_name(name)
        rows.append(
            {
                "name": f"{name} reference",
                "path": f"refs/{next_index:02d}_character_reference_{_slug_name(name)}/",
                "type": "character",
                "purpose": f"{name}'s face, wardrobe, and general look.",
                "source": "screenplay_extraction",
                "character_id": character_id,
                "structured_notes_path": f"assets/refs/characters/{character_id}_character_reference.md",
                "reference_sheet_path": f"assets/refs/characters/{character_id}_character_reference_sheet.png",
            }
        )
        next_index += 1
    for name in prop_names:
        label = re.sub(r"\s+reference$", "", name, flags=re.IGNORECASE)
        rows.append(
            {
                "name": name,
                "path": f"refs/{next_index:02d}_prop_reference_{_slug_name(label)}/",
                "type": "prop",
                "purpose": f"the {label.lower()} shape, scale, and visible details.",
                "source": "screenplay_extraction",
            }
        )
        next_index += 1
    for candidate in extra_references or []:
        ref_type = candidate.get("type", "reference")
        label = candidate.get("label", ref_type).strip()
        name = f"{label} reference" if not label.lower().endswith("reference") else label
        rows.append(
            {
                "name": name,
                "path": f"refs/{next_index:02d}_{ref_type}_reference_{_slug_name(label)}/",
                "type": ref_type,
                "purpose": _reference_purpose(ref_type, label),
                "source": candidate.get("source", "screenplay_extraction"),
                "extraction_basis": candidate.get("extraction_basis", ""),
            }
        )
        next_index += 1
    return rows


def _reference_purpose(ref_type: str, label: str) -> str:
    clean = label.strip() or ref_type
    if ref_type == "costume":
        return f"explicit wardrobe or costume continuity for {clean.lower()}."
    if ref_type == "vehicle":
        return f"the {clean.lower()} design, scale, materials, and continuity details."
    if ref_type == "creature":
        return f"the {clean.lower()} design, silhouette, movement cues, and continuity details."
    if ref_type == "lighting":
        return f"{clean.lower()} continuity, mood, light direction, and exposure guidance."
    if ref_type == "vfx":
        return f"{clean.lower()} visual effect shape, timing, scale, and shot continuity."
    return f"{clean.lower()} continuity reference."


def _reference_folder_paths(reference_rows: list[dict[str, str]]) -> list[str]:
    return [row["path"] for row in reference_rows]


def _reference_base_prompt(row: dict[str, str]) -> str:
    name = row["name"]
    label = re.sub(r"\s+reference$", "", name, flags=re.IGNORECASE)
    ref_type = row.get("type", "")
    if ref_type == "style":
        return (
            "Create a clean style / look bible reference sheet for AI video generation. Use a white or very light grey "
            "background, thin black panel borders, neutral layout, no poster composition, no logos, and no text overlays "
            "outside the labelled production notes. Include colour palette, lens feel, realism level, texture, lighting "
            "range, avoid / do-not-change notes, and locked style anchors."
        )
    if ref_type == "location":
        return (
            f"Create a clean location / set reference sheet for {label}. Use a white or very light grey background, "
            "thin black panel borders, no people, no poster styling, and neutral production lighting. Include wide "
            "layout view, key angle, entrance / exit cues, reusable background details, lighting direction, locked "
            "environment anchors, scale notes, and avoid / do-not-change notes."
        )
    if ref_type == "character":
        return (
            f"Create a clean white-background CHARACTER REFERENCE SHEET for AI video generation for {label}. "
            "Use a landscape film-production layout with thin black panel borders, neutral studio lighting, no other "
            "characters, no cinematic environment background, no poster composition, and no story-heavy biography. "
            "Include front full-body view, side full-body view, back full-body view, 3/4 full-body view, portrait / "
            "close-up, action pose, expression mini-head studies, details / texture references, locked visual anchors, "
            "avoid / do-not-change notes, and short role / energy notes. Maintain the same face, hair, build, costume, "
            "shoes, silhouette, and proportions across every panel."
        )
    if ref_type == "costume":
        return (
            f"Create a clean costume / wardrobe continuity sheet for {label}. Use a white or very light grey background, "
            "thin black panel borders, no model drift, no unrelated props, and neutral lighting. Include front, side, "
            "back, detail close-ups, material texture, fastener / trim details, footwear, wear state, locked costume "
            "anchors, scale notes, and avoid / do-not-change notes."
        )
    if ref_type == "vehicle":
        return (
            f"Create a clean vehicle reference sheet for {label}. Use a white or very light grey background, thin black "
            "panel borders, no cinematic road scene, and neutral lighting. Include front, side, rear, 3/4 view, interior "
            "or key detail panels, material / finish notes, scale cues, locked design anchors, and avoid / do-not-change "
            "notes."
        )
    if ref_type == "creature":
        return (
            f"Create a clean creature reference sheet for {label}. Use a white or very light grey background, thin black "
            "panel borders, no environment scene, and neutral lighting. Include front, side, back, 3/4 view, close-up, "
            "movement pose, texture details, silhouette notes, locked design anchors, and avoid / do-not-change notes."
        )
    if ref_type == "lighting":
        return (
            f"Create a clean lighting / mood reference sheet for {label}. Use a white or very light grey production-board "
            "layout with thin black panel borders. Include key light direction, contrast level, colour temperature, "
            "exposure notes, practical light sources, shadows, mood range, locked lighting anchors, and avoid / "
            "do-not-change notes."
        )
    if ref_type == "vfx":
        return (
            f"Create a clean VFX / action-beat reference sheet for {label}. Use a white or very light grey background, "
            "thin black panel borders, no poster styling, and no unrelated story elements. Include effect shape, scale, "
            "timing beats, material / particle cues, interaction with performers or environment, locked effect anchors, "
            "and avoid / do-not-change notes."
        )
    return (
        f"Create a clean prop / hero object reference sheet for the {label.lower()}: white or very light grey background, "
        "thin black panel borders, clear shape, scale, useful visible details, material texture, key angles, locked "
        "object anchors, avoid / do-not-change notes, no text, no logo."
    )


def _reference_tuning_notes(row: dict[str, str]) -> str:
    ref_type = row.get("type", "")
    if ref_type == "style":
        return "Adjust realism level, lighting mood, texture, and visual style only if they match your intended look."
    if ref_type == "location":
        return "Adjust layout, light direction, realism level, and visual style only if they match the scene."
    if ref_type == "character":
        return (
            "Adjust clothing, age range, hair, realism level, and visual style only if those details are supported by "
            "the screenplay or your intended look."
        )
    if ref_type == "costume":
        return "Adjust garment details only when they are explicit in the screenplay or approved by the creator."
    if ref_type == "vehicle":
        return "Adjust model, era, condition, materials, and scale only when approved by the creator."
    if ref_type == "creature":
        return "Adjust anatomy, silhouette, texture, and movement only when approved by the creator."
    if ref_type == "lighting":
        return "Adjust mood, contrast, colour temperature, and practical sources to match the intended scene look."
    if ref_type == "vfx":
        return "Adjust effect scale, timing, particles, and interaction only when approved by the creator."
    return "Adjust scale, material, realism level, angle, or visual style only as needed for your project."


def _enrich_reference_rows(
    reference_rows: list[dict[str, object]],
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
) -> list[dict[str, str]]:
    used_by: dict[str, list[str]] = {row["name"]: [] for row in reference_rows}
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        for reference_name in _reference_names_for_shot(
            shot_bindings,
            character_name_by_ref,
            location_reference,
            prop_name_by_ref,
        ):
            used_by.setdefault(reference_name, []).append(f"Shot {_shot_number(shot_id)}")

    enriched: list[dict[str, str]] = []
    for index, row in enumerate(reference_rows, start=1):
        item = dict(row)
        item["number"] = f"{index:02d}"
        item["base_prompt"] = _reference_base_prompt(row)
        item["tuning_notes"] = _reference_tuning_notes(row)
        item["used_in"] = ", ".join(used_by.get(row["name"], [])) or "Scene reference"
        enriched.append(item)
    return enriched


def _shot_number(shot_id: str) -> str:
    match = re.search(r"(\d+)$", shot_id)
    return f"{int(match.group(1)):03d}" if match else shot_id


def _framing_label(framing: str) -> str:
    return str(framing).replace("_", " ").title()


def _prompt_preview(beat: str, framing: str) -> str:
    line = _format_prompt_line(beat, framing)
    return re.sub(r"\s+", " ", line).strip()


def _shot_addressee(character_names: list[str], scene_character_names: list[str]) -> str:
    if len(character_names) != 1:
        return ""
    speaker = character_names[0]
    for name in scene_character_names:
        if name != speaker:
            return name
    return ""


def _base_prompt(
    shot: dict[str, object],
    location_context: str,
    character_names: list[str],
    scene_character_names: list[str],
    references: list[str],
) -> str:
    action = _creator_beat_text(str(shot.get("beat", "")), addressee=_shot_addressee(character_names, scene_character_names))
    if action and not re.search(r'[.!?]"?$', action):
        action += "."
    frame = _framing_label(str(shot.get("framing", ""))).lower()
    location = location_context.rstrip(".")
    stable_items = _keep_consistent_items(character_names, references[1] if len(references) > 1 else "", references)
    stable_items = stable_items[:5]
    if not stable_items:
        consistency = "Keep the attached references and visual style consistent."
    elif len(stable_items) == 1:
        consistency = f"Keep {stable_items[0]} and the visual style consistent with the attached references."
    else:
        consistency = f"Keep {', '.join(stable_items)}, and the visual style consistent with the attached references."
    return re.sub(
        r"\s+",
        " ",
        (
            f"{action} {frame.capitalize()} shot in {location.lower()}. Natural movement, practical focused energy, "
            "grounded realistic performance. "
            f"{consistency} "
            "Do not add new characters, locations, props, text, or story events. "
            "No subtitles, captions, logos, watermarks, or on-screen text."
        ),
    ).strip()


def _keep_consistent_items(
    character_names: list[str],
    location_reference: str,
    references: list[str],
) -> list[str]:
    items: list[str] = []
    items.extend(character_names)
    location = re.sub(r"\s+reference$", "", location_reference, flags=re.IGNORECASE)
    if location:
        items.append(location)
    for ref in references:
        if "prop" not in ref.lower() and not re.search(r"\b(map|watch|folder|tote|measure|tape|umbrella|keys)\b", ref, re.I):
            continue
        items.append(re.sub(r"\s+reference$", "", ref, flags=re.IGNORECASE))
    return list(dict.fromkeys(item for item in items if item))


def _shot_card_lines(
    shot: dict[str, object],
    bindings: dict[str, dict[str, list[str]]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
    location_context: str,
    scene_character_names: list[str],
    shot_prompt_by_id: dict[str, str] | None = None,
) -> list[str]:
    shot_id = str(shot["shot_id"])
    shot_bindings = bindings[shot_id]
    references = _reference_names_for_shot(shot_bindings, character_name_by_ref, location_reference, prop_name_by_ref)
    character_names = [character_name_by_ref.get(ref_id, "Character") for ref_id in shot_bindings["character_ref_ids"]]
    title = _short_beat_label(str(shot.get("beat", "")), max_words=5) or "Scene beat"
    keep_items = _keep_consistent_items(character_names, location_reference, references)
    base_prompt = (shot_prompt_by_id or {}).get(shot_id) or _base_prompt(
        shot, location_context, character_names, scene_character_names, references
    )
    return [
        f"SHOT {_shot_number(shot_id)} - {title}",
        "SHOT INTENT",
        _creator_beat_text(
            str(shot.get("beat", "")),
            addressee=_shot_addressee(character_names, scene_character_names),
        ),
        "FRAME",
        f"{_framing_label(str(shot.get('framing', '')))} shot",
        "SCENE CONTEXT",
        location_context,
        "CHARACTERS",
        ", ".join(character_names) if character_names else "None",
        "REFERENCES TO ATTACH",
        ", ".join(references) if references else "None",
        "BASE PROMPT",
        "Copy this section into your AI video tool as the starting prompt.",
        base_prompt,
        "OPTIONAL TUNING",
        "Adjust the base prompt for your chosen AI video tool: camera movement, shot energy, performance intensity, realism level, reference emphasis, or tool-specific wording.",
        "KEEP CONSISTENT",
        ", ".join(keep_items) if keep_items else "Scene context and reference images",
        "GENERATION CHECK",
        "Start with one test take. If the shot is close, generate 2-3 more and pick a keeper. If the shot is wrong, simplify the base prompt or strengthen the references before generating more. Save takes here: generated_shots/takes/. Save selected keepers here: generated_shots/keepers/. Track the selected keeper in: KEEPER_SHEET.csv.",
        "POST-PRODUCTION NOTE",
        "This shot can support the scene rhythm in the edit. Use it with reaction shots, inserts, or wider coverage as needed, then finish dialogue and sound in post.",
    ]


def _shot_card_context(
    shot: dict[str, object],
    bindings: dict[str, dict[str, list[str]]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
    location_context: str,
    scene_character_names: list[str],
    shot_prompt_by_id: dict[str, str] | None = None,
) -> dict[str, object]:
    shot_id = str(shot["shot_id"])
    shot_bindings = bindings[shot_id]
    references = _reference_names_for_shot(shot_bindings, character_name_by_ref, location_reference, prop_name_by_ref)
    character_names = [character_name_by_ref.get(ref_id, "Character") for ref_id in shot_bindings["character_ref_ids"]]
    title = _short_beat_label(str(shot.get("beat", "")), max_words=5) or "Scene beat"
    keep_items = _keep_consistent_items(character_names, location_reference, references)
    base_prompt = (shot_prompt_by_id or {}).get(shot_id) or _base_prompt(
        shot, location_context, character_names, scene_character_names, references
    )
    return {
        "title": f"SHOT {_shot_number(shot_id)} - {title}",
        "intent": _creator_beat_text(
            str(shot.get("beat", "")),
            addressee=_shot_addressee(character_names, scene_character_names),
        ),
        "frame": f"{_framing_label(str(shot.get('framing', '')))} shot",
        "scene_context": location_context,
        "characters": ", ".join(character_names) if character_names else "None",
        "references": references,
        "base_prompt": base_prompt,
        "keep_consistent": keep_items or ["Scene context", "Reference images"],
        "generation_check": [
            "preserve the listed references",
            "show the intended action clearly",
            "keep the shot readable for the edit",
            "avoid unwanted text or logos",
        ],
        "generation_note": "Start with one test take. If the shot is close, generate 2-3 more and pick a keeper. If the shot is wrong, simplify the base prompt or strengthen the references before generating more.",
        "take_path": GENERATED_TAKES_DIR,
        "keeper_path": GENERATED_KEEPERS_DIR,
        "keeper_sheet_path": KEEPER_SHEET_FILENAME,
        "post_note": "This shot can support the scene rhythm in the edit. Use it with reaction shots, inserts, or wider coverage as needed, then finish dialogue and sound in post.",
    }


def _chunked(items: list[dict[str, object]], size: int) -> list[list[dict[str, object]]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _render_renderpackage_pdf(
    scene: dict[str, object],
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    speaker_by_id: dict[str, str],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
    units: list[dict[str, object]],
    reference_rows: list[dict[str, object]],
    shot_prompt_by_id: dict[str, str] | None = None,
) -> CreatorGuideRenderResult:
    location_context = _location_context(scene)
    scene_character_names = _scene_character_names(scene, speaker_by_id)
    summary = ["RENDERPACKAGE", "", "Scene Summary", *_scene_summary_lines(scene, speaker_by_id)]
    reference_names = [str(row.get("name", "")) for row in reference_rows if row.get("name")]
    summary.extend(
        [
            "",
            "Reference Setup",
            "Reference folders are already created for this scene.",
            "They are here to help you keep the scene organized in one place: style, location, character, and prop references stay beside the shooting pack instead of scattered across downloads or desktop folders.",
            "Add your reference images into these folders before generating shots so you can quickly find the right assets while working shot by shot.",
            "Use one strong reference image to start. Add more only if your AI video tool supports multiple references and the extra images improve consistency.",
            "Your AI video tool only uses these images when you manually attach or upload them during generation.",
            f"Needed: {', '.join(dict.fromkeys(reference_names))}",
            "",
            "REFERENCE BOARD",
            "References are reusable visual ingredients for your shots.",
            "Create or collect the references before generating video takes.",
            "Reference folders are already created for you.",
        ]
    )
    for row in reference_rows:
        summary.extend(
            [
                f"REFERENCE {row['number']} - {row['name']}",
                f"USE FOR {row['purpose']}",
                f"SAVE HERE {row['path']}",
                f"REFERENCE BASE PROMPT {row['base_prompt']}",
                f"TUNING NOTES {row['tuning_notes']}",
                f"USED IN {row['used_in']}",
            ]
        )

    pages = [summary]
    current = ["Shot Cards / Storyboard"]
    for shot in shots:
        card = [
            "",
            *_shot_card_lines(
                shot,
                bindings,
                character_name_by_ref,
                location_reference,
                prop_name_by_ref,
                location_context,
                scene_character_names,
                shot_prompt_by_id,
            ),
        ]
        if len(current) + len(card) > 48:
            pages.append(current)
            current = ["Shot Cards / Storyboard"]
        current.extend(card)
    pages.append(current)

    audio_lines = ["POST-PRODUCTION WORKFLOW"]
    audio_lines.extend(
        [
            "Generate picture-first clips, then build the final scene in the edit.",
            "Use speaking shots, reaction shots, inserts, and wider coverage together to support dialogue and rhythm.",
            "Add final dialogue, sound effects, ambience, subtitles, colour, and polish in post.",
            "Dialogue in the prompt helps the video tool understand the performance moment. It is not the final audio track.",
        ]
    )
    dialogue = _dialogue_lines_by_shot(shots, units)
    if dialogue:
        for shot_id, pairs in dialogue:
            audio_lines.append(f"Shot {_shot_number(shot_id)} dialogue reference:")
            for speaker, line in pairs:
                audio_lines.append(f"{speaker}: {line}")
    else:
        audio_lines.append("No exact dialogue lines detected. Build final sound, music, and dialogue separately in post.")
    audio_lines.extend(
        [
            "",
            "Keeper Workflow",
            "Use generated_shots/takes/ for all attempts.",
            "Use generated_shots/keepers/ for selected clips.",
            "Use KEEPER_SHEET.csv to record which take you chose and why.",
            "A keeper does not need to be perfect. It needs to be useful in the edit.",
        ]
    )
    pages.append(audio_lines)
    cards = [
        _shot_card_context(
            shot,
            bindings,
            character_name_by_ref,
            location_reference,
            prop_name_by_ref,
            location_context,
            scene_character_names,
            shot_prompt_by_id,
        )
        for shot in shots
    ]
    dialogue_lines = [
        {"shot_number": _shot_number(shot_id), "lines": pairs}
        for shot_id, pairs in _dialogue_lines_by_shot(shots, units)
    ]
    result = render_template_pdf(
        "renderpackage_storyboard.html",
        {
            "title": "RENDERPACKAGE",
            "logo_uri": _branding_logo_uri(),
            "progress_text": PROGRESS_TEXT,
            "scene_summary": _scene_summary_lines(scene, speaker_by_id),
            "reference_names": list(dict.fromkeys(reference_names)),
            "reference_rows": reference_rows,
            "shot_pages": _chunked(cards, 3),
            "dialogue_lines": dialogue_lines,
        },
    )
    if result.pdf_bytes:
        return result
    return CreatorGuideRenderResult(
        pdf_bytes=_render_text_pdf(pages, title="RENDERPACKAGE"),
        renderer_used=result.renderer_used,
        error=result.error,
        debug_text=result.debug_text,
    )


def _render_copy_paste_prompts_docx(
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
    location_context: str,
    scene_character_names: list[str],
    reference_rows: list[dict[str, str]],
    shot_prompt_by_id: dict[str, str] | None = None,
) -> bytes:
    blocks: list[tuple[str, str | None]] = [
        ("COPY / PASTE BASE PROMPTS", "Title"),
        ("RenderScript provides base prompts and tuning notes.", None),
        ("Reference base prompts help you create reusable visual ingredients.", None),
        ("Shot base prompts help you generate video takes.", None),
        ("You can tune these prompts for your preferred AI video tool.", None),
        ("For the full workflow, use RENDERPACKAGE.pdf.", None),
        ("", None),
        ("REFERENCE BASE PROMPTS", "Heading1"),
        ("These prompts are for creating or capturing reference images. RenderScript does not generate these images automatically.", None),
        ("", None),
    ]
    for row in reference_rows:
        blocks.extend(
            [
                (f"REFERENCE {row['number']} - {row['name']}", "Heading1"),
                ("SAVE TO", "Heading1"),
                (row["path"], None),
                ("BASE PROMPT", "Heading1"),
                (row["base_prompt"], None),
                ("TUNING NOTES", "Heading1"),
                (row["tuning_notes"], None),
                ("USED IN", "Heading1"),
                (row["used_in"], None),
                ("", None),
            ]
        )
    blocks.extend(
        [
            ("SHOT BASE PROMPTS", "Heading1"),
            ("These prompts are for generating video takes.", None),
            ("Attach the listed references in your AI video tool before generating if your tool supports references.", None),
            ("", None),
        ]
    )
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        references = _reference_names_for_shot(shot_bindings, character_name_by_ref, location_reference, prop_name_by_ref)
        character_names = [character_name_by_ref.get(ref_id, "Character") for ref_id in shot_bindings["character_ref_ids"]]
        prompt = (shot_prompt_by_id or {}).get(shot_id) or _base_prompt(
            shot, location_context, character_names, scene_character_names, references
        )
        title = _short_beat_label(str(shot.get("beat", "")), max_words=5) or "Scene beat"
        blocks.extend(
            [
                (f"SHOT {_shot_number(shot_id)} - {title}", "Heading1"),
                ("BASE PROMPT", "Heading1"),
                (prompt, None),
                ("TUNING NOTES", "Heading1"),
                ("Camera movement:", None),
                ("Shot energy:", None),
                ("Performance intensity:", None),
                ("Reference emphasis:", None),
                ("Tool-specific wording:", None),
                ("", None),
            ]
        )
    return _render_docx_bytes(blocks)


def _extract_dialogue_pairs(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"([A-Za-z][A-Za-z0-9 _'().-]{0,40}):\s*([^:]+?)(?=(?:\s+[A-Za-z][A-Za-z0-9 _'().-]{0,40}:\s)|$)")
    out: list[tuple[str, str]] = []
    for speaker_raw, line_raw in pattern.findall(text):
        speaker = re.sub(r"\s+", " ", speaker_raw).strip()
        line = re.sub(r"\s+", " ", line_raw).strip()
        if speaker and line:
            out.append((speaker, line))
    return out


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


def _agent_shot_data(
    shots: list[dict[str, object]],
    bindings: dict[str, dict[str, list[str]]],
    character_name_by_ref: dict[str, str],
    location_reference: str,
    prop_name_by_ref: dict[str, str],
    location_context: str,
    scene_character_names: list[str],
    reference_rows: list[dict[str, str]],
    shot_prompt_by_id: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    reference_path_by_name = {row["name"]: row["path"] for row in reference_rows}
    out: list[dict[str, object]] = []
    for shot in shots:
        shot_id = str(shot["shot_id"])
        shot_bindings = bindings[shot_id]
        references = _reference_names_for_shot(shot_bindings, character_name_by_ref, location_reference, prop_name_by_ref)
        character_names = [character_name_by_ref.get(ref_id, "Character") for ref_id in shot_bindings["character_ref_ids"]]
        intent = _creator_beat_text(
            str(shot.get("beat", "")),
            addressee=_shot_addressee(character_names, scene_character_names),
        )
        base_prompt = (shot_prompt_by_id or {}).get(shot_id) or _base_prompt(
            shot, location_context, character_names, scene_character_names, references
        )
        out.append(
            {
                "shot_id": shot_id,
                "shot_number": _shot_number(shot_id),
                "shot_title": _short_beat_label(str(shot.get("beat", "")), max_words=5) or "Scene beat",
                "shot_intent": intent,
                "beat": str(shot.get("beat", "")),
                "base_prompt": base_prompt,
                "suggested_framing": f"{_framing_label(str(shot.get('framing', '')))} shot",
                "scene_context": location_context,
                "characters": character_names,
                "references": [
                    {
                        "label": reference,
                        "folder": reference_path_by_name.get(reference, ""),
                    }
                    for reference in references
                ],
                "reference_ids": {
                    "character_refs": shot_bindings["character_ref_ids"],
                    "location_refs": shot_bindings["location_ref_ids"],
                    "style_refs": shot_bindings["style_ref_ids"],
                    "prop_refs": shot_bindings["prop_ref_ids"],
                },
                "post_production_note": (
                    "This shot can support the scene rhythm in the edit. Use it with reaction shots, inserts, "
                    "or wider coverage as needed, then finish dialogue and sound in post."
                ),
            }
        )
    return out


def _render_character_reference_notes(row: dict[str, object]) -> str:
    name = str(row.get("name", "Character reference"))
    label = re.sub(r"\s+reference$", "", name, flags=re.IGNORECASE)
    lines = [
        f"# {label} Character Reference",
        "",
        "Structured notes for a creator-approved character reference sheet.",
        "",
        f"- Character ID: {row.get('character_id', _slug_name(label))}",
        f"- Reference ID: {row.get('reference_id', '')}",
        f"- Reference sheet target: {row.get('reference_sheet_path', '')}",
        f"- Prompt source: {row.get('path', '')}",
        f"- Approval status: {row.get('approval_status', 'pending_creator_approval')}",
        "",
        "Locked visual anchors:",
    ]
    anchors = row.get("locked_visual_anchors", [])
    if isinstance(anchors, list) and anchors:
        lines.extend(f"- {anchor}" for anchor in anchors)
    else:
        lines.append("- Creator to approve hair, face, clothing, silhouette, posture, and signature items.")
    lines.extend(["", "Avoid / do-not-change:"])
    avoid_rules = row.get("avoid_rules", [])
    if isinstance(avoid_rules, list) and avoid_rules:
        lines.extend(f"- {rule}" for rule in avoid_rules)
    else:
        lines.append("- Creator to approve visual drift risks before this becomes a continuity anchor.")
    lines.extend(["", "Base prompt:", str(row.get("base_prompt", "")).strip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def _render_reference_prompts_md(
    reference_rows: list[dict[str, object]],
    voice_profiles: list[dict[str, object]],
) -> str:
    lines = [
        "# Reference Prompts",
        "",
        "These are scaffold prompts for creator review. RenderScript extracts obvious candidates and does not silently invent final designs.",
        "",
        "Approval rule: nothing becomes a continuity anchor until the creator approves it in PromptTuner or an equivalent review step.",
        "",
        "## Visual References",
        "",
    ]
    for row in reference_rows:
        lines.extend(
            [
                f"### {row.get('name', 'Reference')}",
                f"- Type: {row.get('type', 'reference')}",
                f"- Package folder: {row.get('path', '')}",
                f"- Asset folder: {row.get('asset_folder', '')}",
                f"- Source: {row.get('source', 'screenplay_extraction')}",
                f"- Approval status: {row.get('approval_status', 'pending_creator_approval')}",
                "",
                str(row.get("base_prompt", "")).strip(),
                "",
            ]
        )
    lines.extend(["## Voice References", ""])
    if not voice_profiles:
        lines.extend(["No character voice references were detected.", ""])
    for profile in voice_profiles:
        lines.extend(
            [
                f"### {profile.get('name', 'Character')}",
                f"- Path: {profile.get('path', '')}",
                f"- Sample folder: {profile.get('sample_folder', '')}",
                f"- Approval status: {profile.get('approval_status', 'pending_creator_approval')}",
                f"- Accent: {profile.get('accent', '')}",
                f"- Pace: {profile.get('pace', '')}",
                f"- Tone: {profile.get('tone', '')}",
                f"- Rhythm: {profile.get('rhythm', '')}",
                f"- Volume: {profile.get('volume', '')}",
                f"- Speech style: {profile.get('speech_style', '')}",
                f"- Emotional delivery states: {profile.get('emotional_delivery_states', '')}",
                f"- Avoid / do-not-change: {profile.get('avoid_rules', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _references_payload(reference_rows: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {plural: [] for plural in REFERENCE_TYPE_PLURALS.values()}
    for row in reference_rows:
        ref_type = str(row.get("type", ""))
        plural = REFERENCE_TYPE_PLURALS.get(ref_type, ref_type or "references")
        grouped.setdefault(plural, [])
        entry: dict[str, object] = {
            "reference_id": row.get("reference_id", _reference_id_from_path(str(row.get("path", "")))),
            "name": row.get("name", ""),
            "type": ref_type,
            "path": row.get("path", ""),
            "asset_folder": row.get("asset_folder", ""),
            "base_prompt": row.get("base_prompt", ""),
            "source": row.get("source", "screenplay_extraction"),
            "approval_required": True,
            "approved": bool(row.get("approved")),
            "approval_status": row.get("approval_status", "pending_creator_approval"),
            "continuity_anchor": bool(row.get("continuity_anchor")),
            "locked_visual_anchors": row.get("locked_visual_anchors", []),
            "avoid_rules": row.get("avoid_rules", []),
        }
        for optional_key in ("character_id", "reference_sheet_path", "structured_notes_path", "extraction_basis"):
            if row.get(optional_key):
                entry[optional_key] = row[optional_key]
        grouped[plural].append(entry)
    return grouped


def _voice_references_payload(voice_profiles: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    return {
        "characters": [
            {
                "character_id": profile.get("character_id", ""),
                "speaker_id": profile.get("speaker_id", ""),
                "reference_id": profile.get("reference_id", ""),
                "name": profile.get("name", ""),
                "path": profile.get("path", ""),
                "sample_folder": profile.get("sample_folder", ""),
                "accent": profile.get("accent", ""),
                "pace": profile.get("pace", ""),
                "tone": profile.get("tone", ""),
                "rhythm": profile.get("rhythm", ""),
                "volume": profile.get("volume", ""),
                "speech_style": profile.get("speech_style", ""),
                "emotional_delivery_states": profile.get("emotional_delivery_states", ""),
                "avoid_rules": profile.get("avoid_rules", ""),
                "dialogue_reference": profile.get("dialogue_reference", ""),
                "approval_required": True,
                "approved": bool(profile.get("approved")),
                "approval_status": profile.get("approval_status", "pending_creator_approval"),
                "continuity_anchor": bool(profile.get("continuity_anchor")),
            }
            for profile in voice_profiles
        ]
    }


def _approval_status_payload(
    reference_rows: list[dict[str, object]],
    voice_profiles: list[dict[str, object]],
    shots: list[dict[str, object]],
) -> dict[str, object]:
    visual_total = len(reference_rows)
    visual_approved = sum(1 for row in reference_rows if row.get("approved"))
    voice_total = len(voice_profiles)
    voice_approved = sum(1 for profile in voice_profiles if profile.get("approved"))
    shot_total = len(shots)
    shot_approved = sum(1 for shot in shots if shot.get("approved"))
    return {
        "prompts_approved": shot_total > 0 and shot_approved == shot_total,
        "approved_shot_count": shot_approved,
        "total_shot_count": shot_total,
        "references_approved": visual_total > 0 and visual_approved == visual_total,
        "voice_refs_approved": voice_total > 0 and voice_approved == voice_total,
        "approved_reference_count": visual_approved,
        "total_reference_count": visual_total,
        "approved_voice_reference_count": voice_approved,
        "total_voice_reference_count": voice_total,
    }


def _continuity_anchors_payload(
    reference_rows: list[dict[str, object]],
    voice_profiles: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    return {
        "visual_references": [
            {
                "reference_id": row.get("reference_id", ""),
                "name": row.get("name", ""),
                "type": row.get("type", ""),
                "path": row.get("path", ""),
            }
            for row in reference_rows
            if row.get("continuity_anchor")
        ],
        "voice_references": [
            {
                "character_id": profile.get("character_id", ""),
                "name": profile.get("name", ""),
                "path": profile.get("path", ""),
            }
            for profile in voice_profiles
            if profile.get("continuity_anchor")
        ],
    }


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
    selected_providers: list[str],
    agent_shots: list[dict[str, object]],
    reference_rows: list[dict[str, str]],
    voice_profiles: list[dict[str, object]],
    asset_sources: dict[str, list[dict[str, str]]],
    prompt_tuner_metadata: dict[str, object] | None = None,
) -> str:
    heading = scene.get("heading", {})
    heading_raw = heading.get("raw", "") if isinstance(heading, dict) else ""
    payload = {
        "rpack_version": "0.1",
        "execution_profile": target_provider,
        "execution_profile_version": target_provider_version,
        "selected_execution_profiles": selected_providers,
        "target_provider": target_provider,
        "target_provider_version": target_provider_version,
        "selected_providers": selected_providers,
        "source": {"filename": source_name, "hash": source_hash},
        "generator": {"name": "RenderScript AI", "version": __version__},
        "generated_at": generated_at,
        "renderscript_studio_version": RENDERSCRIPT_STUDIO_VERSION,
        "prompt_tuner_version": PROMPT_TUNER_VERSION,
        "renderpackage_spec_version": RENDERPACKAGE_SPEC_VERSION,
        "rscript_schema_version": RSCRIPT_SCHEMA_VERSION,
        "prompt_tuner": prompt_tuner_metadata
        or {
            "version": PROMPT_TUNER_VERSION,
            "edited": False,
            "edited_reference_prompts": [],
            "edited_shot_prompts": [],
        },
        "scene": {
            "scene_id": str(scene.get("id", "")),
            "heading_raw": str(heading_raw),
            "ordinal": int(scene.get("ordinal", 0)),
        },
        "shots": shots,
        "agent_orchestration": {
            "source_of_truth": RPACK_FILENAME,
            "agent_contract": AGENT_ORCHESTRATION_FILENAME,
            "provider_capabilities_example": PROVIDER_CAPABILITIES_EXAMPLE_FILENAME,
            "action_plan_path": ACTION_PLAN_FILENAME,
            "execution_contract_path": EXECUTION_CONTRACT_FILENAME,
            "approval_checkpoints_path": APPROVAL_CHECKPOINTS_FILENAME,
            "take_log_path": TAKE_LOG_FILENAME,
            "keeper_decisions_path": KEEPER_DECISIONS_FILENAME,
            "keeper_sheet_path": KEEPER_SHEET_FILENAME,
            "provenance_path": PROVENANCE_FILENAME,
            "prompt_pack_paths": {
                "universal": UNIVERSAL_PROMPTS_FILENAME,
                "runway.gen4_image_refs": RUNWAY_PROMPTS_FILENAME,
                "grok.imagine": GROK_PROMPTS_FILENAME,
            },
            "reference_folders": reference_rows,
            "shots": agent_shots,
        },
        "references": _references_payload(reference_rows),
        "voice_references": _voice_references_payload(voice_profiles),
        "asset_sources": asset_sources,
        "approval_status": _approval_status_payload(reference_rows, voice_profiles, shots),
        "continuity_anchors": _continuity_anchors_payload(reference_rows, voice_profiles),
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


def _normalized_prompt_edits(prompt_edits: dict[str, object] | None) -> tuple[dict[str, str], dict[str, str], dict[str, object]]:
    reference_edits: dict[str, str] = {}
    shot_edits: dict[str, str] = {}
    prompt_assist: dict[str, object] = {}
    if isinstance(prompt_edits, dict):
        references = prompt_edits.get("reference_prompts", {})
        shots = prompt_edits.get("shot_prompts", {})
        if isinstance(references, dict):
            for key, value in references.items():
                text = str(value).strip()
                if text:
                    reference_edits[str(key)] = text
        if isinstance(shots, dict):
            for key, value in shots.items():
                text = str(value).strip()
                if text:
                    shot_edits[str(key)] = text
        assist = prompt_edits.get("prompt_assist", {})
        if isinstance(assist, dict):
            prompt_assist = assist
    prompt_assist_used = bool(prompt_assist.get("prompt_assist_used"))
    reference_prompts_improved = bool(prompt_assist.get("reference_prompts_improved"))
    shot_prompts_anchored = bool(prompt_assist.get("shot_prompts_anchored"))
    provider = str(prompt_assist.get("provider", "")).strip()
    deployment = str(prompt_assist.get("deployment", "")).strip()
    metadata = {
        "version": PROMPT_TUNER_VERSION,
        "edited": bool(reference_edits or shot_edits),
        "edited_reference_prompts": sorted(reference_edits.keys()),
        "edited_shot_prompts": sorted(shot_edits.keys()),
        "prompt_assist_used": prompt_assist_used,
        "reference_prompts_improved": reference_prompts_improved,
        "shot_prompts_anchored": shot_prompts_anchored,
    }
    if prompt_assist_used:
        metadata["provider"] = provider or "azure_openai"
        if deployment:
            metadata["deployment"] = deployment
    return reference_edits, shot_edits, metadata


def _apply_reference_prompt_edits(reference_rows: list[dict[str, str]], reference_edits: dict[str, str]) -> None:
    for row in reference_rows:
        path = row.get("path", "")
        if path in reference_edits:
            row["base_prompt"] = reference_edits[path]


def _normalized_review_state(prompt_edits: dict[str, object] | None) -> dict[str, object]:
    reference_approvals: set[str] = set()
    shot_approvals: set[str] = set()
    voice_approvals: set[str] = set()
    voice_bible: dict[str, dict[str, str]] = {}
    continuity: dict[str, dict[str, str]] = {}
    if not isinstance(prompt_edits, dict):
        return {
            "reference_approvals": reference_approvals,
            "shot_approvals": shot_approvals,
            "voice_approvals": voice_approvals,
            "voice_bible": voice_bible,
            "continuity": continuity,
        }

    approvals = prompt_edits.get("reference_approvals", {})
    if isinstance(approvals, dict):
        reference_approvals = {str(key) for key, value in approvals.items() if bool(value)}

    voice_approval_raw = prompt_edits.get("voice_approvals", {})
    if isinstance(voice_approval_raw, dict):
        voice_approvals = {str(key) for key, value in voice_approval_raw.items() if bool(value)}

    shot_approval_raw = prompt_edits.get("shot_approvals", {})
    if isinstance(shot_approval_raw, dict):
        shot_approvals = {str(key) for key, value in shot_approval_raw.items() if bool(value)}

    voice_raw = prompt_edits.get("voice_bible", {})
    if isinstance(voice_raw, dict):
        for key, value in voice_raw.items():
            if not isinstance(value, dict):
                continue
            fields: dict[str, str] = {}
            for field_key, field_value in value.items():
                text = str(field_value).strip()
                if text:
                    fields[str(field_key)] = text
            if fields:
                voice_bible[str(key)] = fields

    continuity_raw = prompt_edits.get("continuity", {})
    if isinstance(continuity_raw, dict):
        for key, value in continuity_raw.items():
            if not isinstance(value, dict):
                continue
            fields = {}
            for field_key, field_value in value.items():
                text = str(field_value).strip()
                if text:
                    fields[str(field_key)] = text
            if fields:
                continuity[str(key)] = fields

    return {
        "reference_approvals": reference_approvals,
        "shot_approvals": shot_approvals,
        "voice_approvals": voice_approvals,
        "voice_bible": voice_bible,
        "continuity": continuity,
    }


def _apply_reference_review_state(reference_rows: list[dict[str, object]], review_state: dict[str, object]) -> None:
    approved = review_state.get("reference_approvals", set())
    continuity = review_state.get("continuity", {})
    approved_paths = approved if isinstance(approved, set) else set()
    continuity_by_path = continuity if isinstance(continuity, dict) else {}
    for row in reference_rows:
        path = str(row.get("path", ""))
        row["reference_id"] = _reference_id_from_path(path)
        row["approval_required"] = True
        row["approved"] = path in approved_paths
        row["approval_status"] = "approved" if row["approved"] else "pending_creator_approval"
        row["continuity_anchor"] = bool(row["approved"])
        row["source"] = str(row.get("source", "screenplay_extraction") or "screenplay_extraction")
        row["asset_folder"] = _asset_reference_folder_for_type(str(row.get("type", "")))
        notes = continuity_by_path.get(path, {}) if isinstance(continuity_by_path.get(path, {}), dict) else {}
        locked = _list_from_multiline(str(notes.get("locked_visual_anchors", ""))) if isinstance(notes, dict) else []
        avoid = _list_from_multiline(str(notes.get("avoid_rules", ""))) if isinstance(notes, dict) else []
        row["locked_visual_anchors"] = locked
        row["avoid_rules"] = avoid


def _apply_shot_review_state(
    shots: list[dict[str, object]],
    agent_shots: list[dict[str, object]],
    review_state: dict[str, object],
) -> None:
    approved = review_state.get("shot_approvals", set())
    approved_ids = approved if isinstance(approved, set) else set()
    for shot in shots:
        shot_id = str(shot.get("shot_id", ""))
        is_approved = shot_id in approved_ids
        shot["approval_required"] = True
        shot["approved"] = is_approved
        shot["approval_status"] = "approved" if is_approved else "pending_creator_approval"
    for shot in agent_shots:
        shot_id = str(shot.get("shot_id", ""))
        is_approved = shot_id in approved_ids
        shot["approval_required"] = True
        shot["approved"] = is_approved
        shot["approval_status"] = "approved" if is_approved else "pending_creator_approval"


def _safe_reference_asset_filename(filename: str) -> str:
    name = Path(filename or "reference.png").name
    suffix = Path(name).suffix.lower()
    if suffix not in REFERENCE_ASSET_SUFFIXES:
        raise ValueError("Reference assets must be JPG, PNG, or WebP images.")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._-")
    return f"{stem or 'reference'}{suffix}"


def _reference_asset_files(
    reference_assets: list[dict[str, object]] | None,
    reference_paths: list[str],
) -> tuple[dict[str, bytes], dict[str, list[dict[str, str]]]]:
    if not reference_assets:
        return {}, {}

    allowed = set(reference_paths)
    files: dict[str, bytes] = {}
    metadata: dict[str, list[dict[str, str]]] = {}
    used_names: dict[str, set[str]] = {}
    for asset in reference_assets:
        folder = str(asset.get("reference_path") or asset.get("folder") or "").replace("\\", "/")
        if folder not in allowed:
            raise ValueError("Reference asset does not match a package reference folder.")
        content = asset.get("content")
        if not isinstance(content, bytes):
            raise ValueError("Reference asset content is missing.")
        filename = _safe_reference_asset_filename(str(asset.get("filename") or "reference.png"))
        names = used_names.setdefault(folder, set())
        if filename in names:
            suffix = Path(filename).suffix
            stem = Path(filename).stem
            counter = 2
            while f"{stem}_{counter}{suffix}" in names:
                counter += 1
            filename = f"{stem}_{counter}{suffix}"
        names.add(filename)
        path = f"{folder}{filename}"
        files[path] = content
        metadata.setdefault(folder, []).append(
            {
                "filename": filename,
                "path": path,
                "source": "user_upload",
            }
        )
    return files, metadata


def _attach_reference_asset_metadata(
    reference_rows: list[dict[str, object]],
    metadata: dict[str, list[dict[str, str]]],
) -> None:
    for row in reference_rows:
        path = str(row.get("path", ""))
        if path in metadata:
            row["attached_reference_files"] = metadata[path]


def _default_voice_profile(name: str) -> dict[str, str]:
    return {
        "accent": "creator to define",
        "pace": "medium unless the scene requires a change",
        "tone": "grounded and clear",
        "rhythm": "natural conversational rhythm",
        "volume": "natural speaking volume",
        "speech_style": "specific, repeatable, non-impersonation performance style",
        "emotional_delivery_states": "neutral; tense; relieved; urgent when explicitly motivated by the scene",
        "avoid_rules": "Do not imitate a real person. Do not change accent, pace, tone, rhythm, or delivery unless the scene explicitly motivates it.",
        "dialogue_reference": f"Use {name}'s screenplay dialogue as performance context only. Voice style is continuity data, not final dialogue.",
    }


def _build_voice_profiles(
    speaker_by_id: dict[str, str],
    character_ref_by_speaker: dict[str, str],
    review_state: dict[str, object],
) -> list[dict[str, object]]:
    edited_voice = review_state.get("voice_bible", {})
    approvals = review_state.get("voice_approvals", set())
    edited_by_id = edited_voice if isinstance(edited_voice, dict) else {}
    approved_ids = approvals if isinstance(approvals, set) else set()

    profiles: list[dict[str, object]] = []
    for speaker_id, name in sorted(speaker_by_id.items(), key=lambda item: item[1].lower()):
        character_id = _slug_name(name)
        reference_id = character_ref_by_speaker.get(speaker_id, "")
        fields = _default_voice_profile(name.title())
        for key in (character_id, reference_id, speaker_id):
            override = edited_by_id.get(key, {})
            if isinstance(override, dict):
                for field_key, field_value in override.items():
                    text = str(field_value).strip()
                    if text:
                        fields[str(field_key)] = text
        approved = bool({character_id, reference_id, speaker_id} & approved_ids)
        profiles.append(
            {
                "character_id": character_id,
                "speaker_id": speaker_id,
                "reference_id": reference_id,
                "name": name.title(),
                "path": f"{VOICE_REFS_DIR}{character_id}_voice_reference.md",
                "sample_folder": VOICE_SAMPLES_DIR,
                "approved": approved,
                "approval_required": True,
                "approval_status": "approved" if approved else "pending_creator_approval",
                "continuity_anchor": approved,
                "source": "screenplay_extraction",
                **fields,
            }
        )
    return profiles


def _attach_voice_profiles(
    reference_rows: list[dict[str, object]],
    voice_profiles: list[dict[str, object]],
) -> None:
    profile_by_character_id = {str(profile.get("character_id", "")): profile for profile in voice_profiles}
    profile_by_reference_id = {str(profile.get("reference_id", "")): profile for profile in voice_profiles}
    for row in reference_rows:
        if row.get("type") != "character":
            continue
        profile = profile_by_character_id.get(str(row.get("character_id", ""))) or profile_by_reference_id.get(
            str(row.get("reference_id", ""))
        )
        if profile:
            row["voice_bible"] = profile


def _render_voice_profile_md(profile: dict[str, object]) -> str:
    name = str(profile.get("name", "Character"))
    lines = [
        f"# {name} Voice Reference",
        "",
        "Voice style is continuity data, not dialogue. Accent, pace, tone, rhythm, volume, speech style, and delivery should remain stable unless the scene explicitly changes the character's emotional state.",
        "",
        f"- Accent: {profile.get('accent', '')}",
        f"- Pace: {profile.get('pace', '')}",
        f"- Tone: {profile.get('tone', '')}",
        f"- Rhythm: {profile.get('rhythm', '')}",
        f"- Volume: {profile.get('volume', '')}",
        f"- Speech style: {profile.get('speech_style', '')}",
        f"- Emotional delivery states: {profile.get('emotional_delivery_states', '')}",
        f"- Avoid / do-not-change: {profile.get('avoid_rules', '')}",
        "",
        "Dialogue reference:",
        str(profile.get("dialogue_reference", "")).strip(),
        "",
        f"Approval status: {profile.get('approval_status', 'pending_creator_approval')}",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _render_voice_bible(voice_profiles: list[dict[str, object]]) -> str:
    lines = [
        "# Voice Bible",
        "",
        "Audio post guidance only. Avoid personal likeness or impersonation.",
        "",
        "Voice continuity rule: voice style is continuity data, not dialogue. Accent, pace, tone, rhythm, volume, speech style, and delivery must remain stable unless the scene explicitly changes the character's emotional state.",
        "",
    ]
    if not voice_profiles:
        lines.extend(["No named dialogue characters detected.", ""])
        return "\n".join(lines).rstrip() + "\n"
    for profile in voice_profiles:
        lines.extend(
            [
                f"## {profile.get('name', 'Character')}",
                f"- Accent: {profile.get('accent', '')}",
                f"- Pace: {profile.get('pace', '')}",
                f"- Tone: {profile.get('tone', '')}",
                f"- Rhythm: {profile.get('rhythm', '')}",
                f"- Volume: {profile.get('volume', '')}",
                f"- Speech style: {profile.get('speech_style', '')}",
                f"- Emotional delivery states: {profile.get('emotional_delivery_states', '')}",
                f"- Avoid / do-not-change: {profile.get('avoid_rules', '')}",
                f"- Approval status: {profile.get('approval_status', 'pending_creator_approval')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _safe_voice_asset_filename(filename: str) -> str:
    name = Path(filename or "voice_sample.wav").name
    suffix = Path(name).suffix.lower()
    if suffix not in VOICE_ASSET_SUFFIXES:
        raise ValueError("Voice assets must be WAV, MP3, M4A, AAC, FLAC, or OGG files.")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).stem).strip("._-")
    return f"{stem or 'voice_sample'}{suffix}"


def _voice_asset_files(
    voice_assets: list[dict[str, object]] | None,
    voice_profiles: list[dict[str, object]],
) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    if not voice_assets:
        return {}, []
    profiles_by_key: dict[str, dict[str, object]] = {}
    for profile in voice_profiles:
        for key in (
            str(profile.get("character_id", "")),
            str(profile.get("reference_id", "")),
            str(profile.get("speaker_id", "")),
        ):
            if key:
                profiles_by_key[key] = profile
    files: dict[str, bytes] = {}
    metadata: list[dict[str, str]] = []
    used_names: set[str] = set()
    for asset in voice_assets:
        key = str(asset.get("character_id") or asset.get("reference_id") or asset.get("speaker_id") or "").strip()
        profile = profiles_by_key.get(key)
        if not profile:
            raise ValueError("Voice sample could not be matched to a package character.")
        content = asset.get("content")
        if not isinstance(content, bytes):
            raise ValueError("Voice sample content is missing.")
        filename = _safe_voice_asset_filename(str(asset.get("filename") or "voice_sample.wav"))
        prefix = str(profile.get("character_id", "character"))
        candidate = f"{prefix}_{filename}"
        if candidate in used_names:
            suffix = Path(candidate).suffix
            stem = Path(candidate).stem
            counter = 2
            while f"{stem}_{counter}{suffix}" in used_names:
                counter += 1
            candidate = f"{stem}_{counter}{suffix}"
        used_names.add(candidate)
        path = f"{VOICE_SAMPLES_DIR}{candidate}"
        files[path] = content
        metadata.append(
            {
                "filename": candidate,
                "path": path,
                "character_id": str(profile.get("character_id", "")),
                "character_name": str(profile.get("name", "")),
                "source": "user_upload",
            }
        )
    return files, metadata


def package_fountain_file(
    input_path: Path,
    output_path: Path,
    provider: str = DEFAULT_PROVIDER,
    provider_version: str = "",
    include_provider_prompts: list[str] | None = None,
    scene_ordinal: int | None = None,
    duration_s: int = 3,
    project: str = "project",
    prompt_edits: dict[str, object] | None = None,
    reference_assets: list[dict[str, object]] | None = None,
    voice_assets: list[dict[str, object]] | None = None,
) -> None:
    get_provider(provider)

    text = input_path.read_text(encoding="utf-8")
    doc = compile_fountain_text(text, source_name=input_path.name)
    source = doc.get("meta", {}).get("source", {}) if isinstance(doc.get("meta", {}), dict) else {}
    source_hash = source.get("hash", "") if isinstance(source, dict) else ""
    generated_at = _now_iso_utc()
    selected_scene = _extract_scene(doc, scene_ordinal)
    prompt_filename = _prompt_filename_for_provider(provider)
    selected_provider_ids = _selected_providers(provider=provider, include_provider_prompts=include_provider_prompts)
    prompt_files = _prompt_files_for_package(provider=provider, include_provider_prompts=include_provider_prompts)
    speaker_by_id = _speaker_lookup(doc)
    resolved_output_path = _resolve_output_path(
        output_path=output_path,
        project=project,
        selected_scene=selected_scene,
        provider=provider,
    )
    shots, shot_units, _ = _build_shots(selected_scene, doc=doc, duration_s=duration_s)
    bindings, required_refs = _build_bindings(shots, units=shot_units, doc=doc)
    reference_prompt_edits, shot_prompt_by_id, prompt_tuner_metadata = _normalized_prompt_edits(prompt_edits)
    review_state = _normalized_review_state(prompt_edits)
    character_ref_by_speaker = _character_ref_lookup(speaker_by_id)
    speaker_by_character_ref = {ref_id: speaker_id for speaker_id, ref_id in character_ref_by_speaker.items()}
    character_name_by_ref: dict[str, str] = {}
    character_refs_for_prompts: list[tuple[str, str]] = []
    scene_character_ref_order: list[str] = []
    for character_name in _scene_character_names(selected_scene, speaker_by_id):
        for speaker_id, speaker_name in speaker_by_id.items():
            if speaker_name.title() == character_name and speaker_id in character_ref_by_speaker:
                ref_id = character_ref_by_speaker[speaker_id]
                if ref_id in required_refs["character_ref_ids"] and ref_id not in scene_character_ref_order:
                    scene_character_ref_order.append(ref_id)
    for ref_id in required_refs["character_ref_ids"]:
        if ref_id not in scene_character_ref_order:
            scene_character_ref_order.append(ref_id)
    for ref_id in scene_character_ref_order:
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

    location_reference = _scene_location_reference_label(selected_scene)
    prop_name_by_ref = _prop_ref_lookup(shot_units)
    reference_names: list[str] = ["Style reference", location_reference]
    reference_names.extend(f"{name} reference" for name in character_name_by_ref.values())
    reference_names.extend(prop_name_by_ref.values())
    reference_rows = _build_reference_rows(
        location_reference=location_reference,
        character_names=list(character_name_by_ref.values()),
        prop_names=list(prop_name_by_ref.values()),
        extra_references=_extract_reference_candidates(selected_scene, list(character_name_by_ref.values())),
    )
    reference_rows = _enrich_reference_rows(
        reference_rows=reference_rows,
        shots=shots,
        bindings=bindings,
        character_name_by_ref=character_name_by_ref,
        location_reference=location_reference,
        prop_name_by_ref=prop_name_by_ref,
    )
    _apply_reference_prompt_edits(reference_rows, reference_prompt_edits)
    _apply_reference_review_state(reference_rows, review_state)
    voice_profiles = _build_voice_profiles(
        _scene_speaker_lookup(selected_scene, speaker_by_id),
        character_ref_by_speaker,
        review_state,
    )
    _attach_voice_profiles(reference_rows, voice_profiles)
    source_screenplay_filename = _source_screenplay_filename(input_path)
    reference_paths = _reference_folder_paths(reference_rows)
    reference_asset_files, reference_asset_metadata = _reference_asset_files(reference_assets, reference_paths)
    _attach_reference_asset_metadata(reference_rows, reference_asset_metadata)
    voice_asset_files, voice_asset_metadata = _voice_asset_files(voice_assets, voice_profiles)
    if reference_asset_metadata:
        prompt_tuner_metadata["reference_assets_attached"] = True
        prompt_tuner_metadata["attached_reference_files"] = [
            item["path"] for items in reference_asset_metadata.values() for item in items
        ]
    if voice_asset_metadata:
        prompt_tuner_metadata["voice_assets_attached"] = True
        prompt_tuner_metadata["attached_voice_files"] = [item["path"] for item in voice_asset_metadata]
    approved_reference_paths = sorted(str(row.get("path", "")) for row in reference_rows if row.get("approved"))
    approved_voice_ids = sorted(str(profile.get("character_id", "")) for profile in voice_profiles if profile.get("approved"))
    if approved_reference_paths:
        prompt_tuner_metadata["approved_reference_prompts"] = approved_reference_paths
    if approved_voice_ids:
        prompt_tuner_metadata["approved_voice_references"] = approved_voice_ids
    character_notes_files = {
        str(row["structured_notes_path"]): _render_character_reference_notes(row)
        for row in reference_rows
        if row.get("type") == "character" and row.get("structured_notes_path")
    }
    voice_reference_files = {str(profile["path"]): _render_voice_profile_md(profile) for profile in voice_profiles}
    ordered_paths = [
        RENDERPACKAGE_FILENAME,
        COPY_PASTE_PROMPTS_FILENAME,
        KEEPER_SHEET_FILENAME,
        source_screenplay_filename,
        *reference_paths,
        *sorted(reference_asset_files.keys()),
        "prompts/",
        REFERENCE_PROMPTS_FILENAME,
        *ASSET_REFERENCE_DIRS,
        *sorted(character_notes_files.keys()),
        AUDIO_DIR,
        AUDIO_VOICE_BIBLE_FILENAME,
        VOICE_REFS_DIR,
        *sorted(voice_reference_files.keys()),
        VOICE_SAMPLES_DIR,
        *sorted(voice_asset_files.keys()),
        GENERATED_TAKES_DIR,
        GENERATED_KEEPERS_DIR,
        *_required_files(prompt_files),
    ]
    ordered_paths = _dedupe_ordered(ordered_paths)
    location_context = _location_context(selected_scene)
    scene_character_names = _scene_character_names(selected_scene, speaker_by_id)
    agent_shots = _agent_shot_data(
        shots=shots,
        bindings=bindings,
        character_name_by_ref=character_name_by_ref,
        location_reference=location_reference,
        prop_name_by_ref=prop_name_by_ref,
        location_context=location_context,
        scene_character_names=scene_character_names,
        reference_rows=reference_rows,
        shot_prompt_by_id=shot_prompt_by_id,
    )
    _apply_shot_review_state(shots, agent_shots, review_state)
    approved_shot_ids = sorted(str(shot.get("shot_id", "")) for shot in shots if shot.get("approved"))
    if approved_shot_ids:
        prompt_tuner_metadata["approved_shot_prompts"] = approved_shot_ids
    renderpackage_pdf = _render_renderpackage_pdf(
        scene=selected_scene,
        shots=shots,
        bindings=bindings,
        speaker_by_id=speaker_by_id,
        character_name_by_ref=character_name_by_ref,
        location_reference=location_reference,
        prop_name_by_ref=prop_name_by_ref,
        units=shot_units,
        reference_rows=reference_rows,
        shot_prompt_by_id=shot_prompt_by_id,
    )
    guide_debug_text = renderpackage_pdf.debug_text

    files: dict[str, str | bytes] = {
        RENDERPACKAGE_FILENAME: renderpackage_pdf.pdf_bytes,
        COPY_PASTE_PROMPTS_FILENAME: _render_copy_paste_prompts_docx(
            shots,
            bindings,
            character_name_by_ref,
            location_reference,
            prop_name_by_ref,
            location_context,
            scene_character_names,
            reference_rows,
            shot_prompt_by_id,
        ),
        KEEPER_SHEET_FILENAME: _render_scoring_sheet(shots),
        source_screenplay_filename: text,
        GENERATED_TAKES_DIR: b"",
        GENERATED_KEEPERS_DIR: b"",
        "DEVELOPER_FILES/": b"",
        f"{PROMPT_PACKS_DIR}/": b"",
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
            creator_guide_renderer_used=renderpackage_pdf.renderer_used,
            creator_guide_error=renderpackage_pdf.error,
            selected_providers=selected_provider_ids,
            agent_shots=agent_shots,
            reference_rows=reference_rows,
            voice_profiles=voice_profiles,
            asset_sources={
                "uploaded_images": [item for items in reference_asset_metadata.values() for item in items],
                "uploaded_voice_samples": voice_asset_metadata,
            },
            prompt_tuner_metadata=prompt_tuner_metadata,
        ),
        PROVENANCE_FILENAME: _render_provenance_json(
            source_name=input_path.name,
            source_hash=str(source_hash),
            provider=provider,
            prompt_filename=prompt_filename,
            generated_at=generated_at,
            guide_debug_text=guide_debug_text,
            prompt_tuner_metadata=prompt_tuner_metadata,
        ),
        PACKAGE_MAP_FILENAME: _render_package_map(provider, prompt_filename, selected_provider_ids),
        AGENT_ORCHESTRATION_FILENAME: _render_agent_orchestration_md(),
        REFERENCE_PROMPTS_FILENAME: _render_reference_prompts_md(reference_rows, voice_profiles),
        AUDIO_VOICE_BIBLE_FILENAME: _render_voice_bible(voice_profiles),
        PROVIDER_CAPABILITIES_EXAMPLE_FILENAME: _render_provider_capabilities_example_json(),
        ACTION_PLAN_FILENAME: _render_action_plan_json(agent_shots, reference_rows),
        EXECUTION_CONTRACT_FILENAME: _render_execution_contract_json(selected_provider_ids),
        APPROVAL_CHECKPOINTS_FILENAME: _render_approval_checkpoints_json(),
        TAKE_LOG_FILENAME: _to_csv(
            headers=[
                "shot_id",
                "take_id",
                "filename",
                "workflow",
                "prompt_used",
                "references_used",
                "notes",
            ],
            rows=[],
        ),
        KEEPER_DECISIONS_FILENAME: _to_csv(
            headers=[
                "shot_id",
                "keeper_take",
                "filename",
                "decision",
                "reason",
                "revision_needed",
                "notes",
            ],
            rows=[],
        ),
        SHOT_LIST_FILENAME: _to_csv(
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
        UNIVERSAL_PROMPTS_FILENAME: _render_prompts(
            shots, bindings, provider=DEFAULT_PROVIDER, shot_prompt_by_id=shot_prompt_by_id
        ),
        RUNWAY_PROMPTS_FILENAME: _render_prompts(
            shots, bindings, provider=RUNWAY_PROVIDER, shot_prompt_by_id=shot_prompt_by_id
        ),
        GROK_PROMPTS_FILENAME: _render_prompts(
            shots, bindings, provider=GROK_PROVIDER, shot_prompt_by_id=shot_prompt_by_id
        ),
    }
    for reference_path in reference_paths:
        files[reference_path] = b""
    files.update(character_notes_files)
    files.update(voice_reference_files)
    files.update(reference_asset_files)
    files.update(voice_asset_files)
    _write_deterministic_zip(resolved_output_path, files, ordered_paths=ordered_paths)
