from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from . import __version__
from .compiler import compile_fountain_text
from .providers import DEFAULT_PROVIDER, get_provider
from .renderpackage import package_fountain_file
from .versions import (
    RENDERPACKAGE_SPEC_VERSION,
    RENDERSCRIPT_STUDIO_VERSION,
    RSCRIPT_SCHEMA_VERSION,
)

PROJECT_MANIFEST_FILENAME = "project_manifest.json"
PROJECT_INDEX_FILENAME = "project_index.json"
PROJECT_OVERVIEW_FILENAME = "PROJECT_OVERVIEW.md"
PROJECT_REFS_DIR = "project_refs/"
PROJECT_STYLE_BIBLE_FILENAME = f"{PROJECT_REFS_DIR}style_bible.md"
PROJECT_CONTINUITY_RULES_FILENAME = f"{PROJECT_REFS_DIR}continuity_rules.md"
PROJECT_CHARACTERS_FILENAME = f"{PROJECT_REFS_DIR}characters.json"
PROJECT_LOCATIONS_FILENAME = f"{PROJECT_REFS_DIR}locations.json"
PROJECT_SCENES_DIR = "scenes/"
PROJECT_SCHEMA_VERSION = "1.0"
PROJECT_BUNDLE_VERSION = "0.1"
ZIP_FIXED_DATETIME = (1980, 1, 1, 0, 0, 0)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_hex(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_name(value: str, fallback: str = "project") -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    return safe or fallback


def _project_id(project: str, source_hash: str) -> str:
    return f"prj_{_safe_name(project).lower()}_{_stable_hex(source_hash, 8)}"


def _scene_key(order: int) -> str:
    return f"sc_{order:03d}"


def _scene_heading(scene: dict[str, object]) -> dict[str, object]:
    heading = scene.get("heading", {})
    return heading if isinstance(heading, dict) else {}


def _scene_heading_raw(scene: dict[str, object]) -> str:
    return str(_scene_heading(scene).get("raw", "")).strip()


def _scene_ids(doc: dict[str, object]) -> list[str]:
    scenes = [scene for scene in doc.get("scenes", []) if isinstance(scene, dict)]
    scenes.sort(key=lambda scene: int(scene.get("ordinal", 0)))
    return [str(scene.get("id", "")).strip() for scene in scenes if str(scene.get("id", "")).strip()]


def _source_hash(doc: dict[str, object]) -> str:
    meta = doc.get("meta", {})
    source = meta.get("source", {}) if isinstance(meta, dict) else {}
    return str(source.get("hash", "")) if isinstance(source, dict) else ""


def _source_title(doc: dict[str, object], project: str) -> str:
    meta = doc.get("meta", {})
    title = str(meta.get("title", "")).strip() if isinstance(meta, dict) else ""
    return title if title and title != "Untitled" else _safe_name(project, "Project").replace("_", " ")


def _source_filename(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix not in {".fountain", ".fnt"}:
        suffix = ".fountain"
    return f"{_safe_name(input_path.stem, 'screenplay')}{suffix}"


def _project_ref_characters(doc: dict[str, object]) -> str:
    characters = doc.get("entities", {}).get("characters", []) if isinstance(doc.get("entities", {}), dict) else []
    rows: list[dict[str, object]] = []
    scene_id_set = set(_scene_ids(doc))
    for item in characters if isinstance(characters, list) else []:
        if not isinstance(item, dict):
            continue
        first_scene_id = str(item.get("first_scene_id", "")).strip()
        rows.append(
            {
                "character_id": str(item.get("id", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "first_scene_id": first_scene_id,
                "first_scene_known": first_scene_id in scene_id_set,
                "visual_reference_status": "pending_creator_approval",
                "voice_reference_status": "pending_creator_approval",
                "continuity_anchor": False,
            }
        )
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "characters": rows,
        "rules": [
            "Use approved character references only.",
            "Do not silently invent final character design or voice continuity.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _project_ref_locations(doc: dict[str, object]) -> str:
    locations = doc.get("entities", {}).get("locations", []) if isinstance(doc.get("entities", {}), dict) else []
    rows: list[dict[str, object]] = []
    for item in locations if isinstance(locations, list) else []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "location_id": str(item.get("id", "")).strip(),
                "name": str(item.get("name", "")).strip(),
                "context": item.get("context", {}) if isinstance(item.get("context", {}), dict) else {},
                "visual_reference_status": "pending_creator_approval",
                "continuity_anchor": False,
            }
        )
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "locations": rows,
        "rules": [
            "Use approved location references only.",
            "Scene headings are extraction evidence, not final production design.",
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _style_bible_md(title: str) -> str:
    return "\n".join(
        [
            "# Project Style Bible",
            "",
            f"Project: {title}",
            "",
            "Status: scaffold. A creator must approve project-level style references before agents treat them as continuity anchors.",
            "",
            "## Approved Style Anchors",
            "",
            "- None yet.",
            "",
            "## Notes",
            "",
            "- Keep style notes practical and reusable across scenes.",
            "- Do not infer a final look from tone alone without creator approval.",
        ]
    ).rstrip() + "\n"


def _continuity_rules_md() -> str:
    return "\n".join(
        [
            "# Project Continuity Rules",
            "",
            "Project bundles are made of linked scene RenderPackages.",
            "",
            "## Agent Rules",
            "",
            "- Use approved references only as continuity anchors.",
            "- Treat per-scene reference prompts as scaffolds until approved.",
            "- Preserve approved character, location, prop, style, lighting, VFX, and voice continuity across scene packages.",
            "- If continuity is missing or ambiguous, ask the creator or use only the approved scaffold.",
            "- Do not spend external model credits or run generation without explicit workflow permission.",
            "",
            "## Creator Approval",
            "",
            "Nothing becomes project continuity until the creator approves it.",
        ]
    ).rstrip() + "\n"


def _project_overview_md(manifest: dict[str, object]) -> str:
    scenes = manifest.get("scenes", [])
    scene_count = len(scenes) if isinstance(scenes, list) else 0
    batches = manifest.get("batches", [])
    batch_count = len(batches) if isinstance(batches, list) else 0
    return "\n".join(
        [
            "# RenderScript Project Bundle",
            "",
            "This bundle links multiple scene RenderPackages into one project workspace.",
            "",
            f"- Project: {manifest.get('title', '')}",
            f"- Project ID: `{manifest.get('project_id', '')}`",
            f"- Scenes: {scene_count}",
            f"- Batches: {batch_count}",
            "",
            "## Start Here",
            "",
            "1. Open `project_manifest.json` for the machine-readable project contract.",
            "2. Open `project_index.json` for a compact scene index.",
            "3. Use the scene packages under `scenes/` one at a time.",
            "4. Keep project-wide continuity notes in `project_refs/`.",
            "",
            "## Boundary",
            "",
            "RenderScript prepares the project handoff. It does not generate video, spend credits, or execute external tools.",
        ]
    ).rstrip() + "\n"


def _scene_source_fingerprint(scene: dict[str, object]) -> str:
    heading = _scene_heading_raw(scene)
    beat_lines: list[str] = []
    beats = scene.get("beats", [])
    for beat in beats if isinstance(beats, list) else []:
        if not isinstance(beat, dict):
            continue
        text = str(beat.get("text", "")).strip()
        if text:
            beat_lines.append(text)
    return "\n".join([heading, *beat_lines]).strip()


def _scene_package_reusable(
    package_path: Path,
    *,
    source_hash: str,
    scene_id: str,
    provider: str,
) -> bool:
    if not package_path.exists():
        return False
    try:
        with ZipFile(package_path, "r") as zf:
            rpack = json.loads(zf.read("DEVELOPER_FILES/rpack.json").decode("utf-8"))
    except Exception:
        return False
    source = rpack.get("source", {}) if isinstance(rpack, dict) else {}
    scene = rpack.get("scene", {}) if isinstance(rpack, dict) else {}
    selected = rpack.get("target_provider", "") if isinstance(rpack, dict) else ""
    return (
        isinstance(source, dict)
        and isinstance(scene, dict)
        and str(source.get("hash", "")) == source_hash
        and str(scene.get("scene_id", "")) == scene_id
        and str(selected) == provider
    )


def _batch_rows(scene_rows: list[dict[str, object]], batch_size: int) -> list[dict[str, object]]:
    if batch_size <= 0:
        raise ValueError("--batch-size must be a positive integer")
    batches: list[dict[str, object]] = []
    for index in range(0, len(scene_rows), batch_size):
        items = scene_rows[index : index + batch_size]
        batch_number = len(batches) + 1
        start = int(items[0]["order"])
        end = int(items[-1]["order"])
        batches.append(
            {
                "batch_id": f"batch_{batch_number:03d}",
                "label": f"Scenes {start}-{end}" if start != end else f"Scene {start}",
                "scene_ids": [str(item["scene_id"]) for item in items],
                "scene_keys": [str(item["scene_key"]) for item in items],
                "status": "ready",
            }
        )
    return batches


def _manifest(
    *,
    doc: dict[str, object],
    project: str,
    input_path: Path,
    source_filename: str,
    generated_at: str,
    scene_rows: list[dict[str, object]],
    batch_size: int,
    provider: str,
    include_provider_prompts: list[str],
    duration_s: int,
) -> dict[str, object]:
    source_hash = _source_hash(doc)
    title = _source_title(doc, project)
    batches = _batch_rows(scene_rows, batch_size)
    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "bundle_type": "renderscript.project_bundle",
        "project_bundle_version": PROJECT_BUNDLE_VERSION,
        "project_id": _project_id(project, source_hash),
        "title": title,
        "generated_at": generated_at,
        "versions": {
            "renderscript": __version__,
            "renderscript_studio": RENDERSCRIPT_STUDIO_VERSION,
            "renderpackage_spec": RENDERPACKAGE_SPEC_VERSION,
            "rscript_schema": RSCRIPT_SCHEMA_VERSION,
        },
        "source": {
            "type": "fountain",
            "file": source_filename,
            "original_file": input_path.name,
            "hash": source_hash,
            "scene_count": len(scene_rows),
        },
        "build": {
            "provider": provider,
            "include_provider_prompt_packs": include_provider_prompts,
            "duration_s": duration_s,
            "batch_size": batch_size,
            "incremental_scene_packages": True,
            "reuse_key": "source.hash + scene.scene_id + build.provider",
        },
        "project_index": PROJECT_INDEX_FILENAME,
        "scenes": scene_rows,
        "batches": batches,
        "refs": {
            "style_bible": PROJECT_STYLE_BIBLE_FILENAME,
            "continuity_rules": PROJECT_CONTINUITY_RULES_FILENAME,
            "characters": PROJECT_CHARACTERS_FILENAME,
            "locations": PROJECT_LOCATIONS_FILENAME,
        },
        "approval_status": {
            "project_refs_approved": False,
            "scene_references_approved": False,
            "voice_refs_approved": False,
        },
        "agent_rules": [
            "Use approved references only.",
            "Do not invent final project continuity silently.",
            "Treat each scene RenderPackage as a linked scene package inside this project.",
            "Ask for creator approval when continuity is missing or ambiguous.",
        ],
    }


def _project_index(manifest: dict[str, object]) -> str:
    scenes = manifest.get("scenes", [])
    rows = []
    if isinstance(scenes, list):
        for item in scenes:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "scene_id": item.get("scene_id", ""),
                    "scene_key": item.get("scene_key", ""),
                    "order": item.get("order", 0),
                    "heading": item.get("heading", ""),
                    "package_path": item.get("package_path", ""),
                    "status": item.get("status", ""),
                    "build_status": item.get("build_status", ""),
                }
            )
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_id": manifest.get("project_id", ""),
        "source_hash": manifest.get("source", {}).get("hash", "") if isinstance(manifest.get("source", {}), dict) else "",
        "scene_count": len(rows),
        "scenes": rows,
        "batches": manifest.get("batches", []),
        "incremental_build": manifest.get("build", {}).get("incremental_scene_packages", False)
        if isinstance(manifest.get("build", {}), dict)
        else False,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _ordered_paths(scene_rows: list[dict[str, object]]) -> list[str]:
    paths = [
        PROJECT_OVERVIEW_FILENAME,
        PROJECT_MANIFEST_FILENAME,
        PROJECT_INDEX_FILENAME,
        PROJECT_REFS_DIR,
        PROJECT_STYLE_BIBLE_FILENAME,
        PROJECT_CONTINUITY_RULES_FILENAME,
        PROJECT_CHARACTERS_FILENAME,
        PROJECT_LOCATIONS_FILENAME,
        PROJECT_SCENES_DIR,
    ]
    for scene in scene_rows:
        package_path = str(scene.get("package_path", "")).strip()
        scene_dir = f"{package_path.rsplit('/', 1)[0]}/" if "/" in package_path else ""
        if scene_dir:
            paths.append(scene_dir)
        if package_path:
            paths.append(package_path)
    return paths


def _write_project_zip(output_path: Path, files: dict[str, str | bytes], ordered_paths: list[str]) -> None:
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
                content_bytes = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(info, content_bytes)


def _write_project_dir(output_path: Path, files: dict[str, str | bytes], ordered_paths: list[str]) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    for path in ordered_paths:
        target = output_path / path
        if path.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        content = files[path]
        if isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(content)


def package_project_file(
    input_path: Path,
    output_path: Path,
    provider: str = DEFAULT_PROVIDER,
    provider_version: str = "",
    include_provider_prompts: list[str] | None = None,
    duration_s: int = 3,
    project: str = "project",
    batch_size: int = 8,
    prompt_edits_by_scene: dict[int, dict[str, object]] | None = None,
) -> Path:
    get_provider(provider)
    include_provider_prompts = include_provider_prompts or []
    for extra in include_provider_prompts:
        get_provider(extra)
    if duration_s <= 0:
        raise ValueError("--duration-s must be a positive integer")
    if batch_size <= 0:
        raise ValueError("--batch-size must be a positive integer")

    source_text = input_path.read_text(encoding="utf-8")
    doc = compile_fountain_text(source_text, source_name=input_path.name)
    scenes = [scene for scene in doc.get("scenes", []) if isinstance(scene, dict)]
    scenes.sort(key=lambda scene: int(scene.get("ordinal", 0)))
    if not scenes:
        raise ValueError("No scenes found in input")

    source_hash = _source_hash(doc)
    source_filename = _source_filename(input_path)
    generated_at = _now_iso_utc()
    output_is_zip = output_path.suffix.lower() == ".zip"
    output_root = None if output_is_zip else output_path
    scene_rows: list[dict[str, object]] = []
    scene_package_bytes: dict[str, bytes] = {}
    prompt_edits_by_scene = prompt_edits_by_scene or {}

    with TemporaryDirectory(prefix="renderscript_project_") as tmp:
        tmp_dir = Path(tmp)
        source_copy = tmp_dir / source_filename
        source_copy.write_text(source_text, encoding="utf-8")

        for scene in scenes:
            order = int(scene.get("ordinal", 0))
            scene_prompt_edits = prompt_edits_by_scene.get(order)
            key = _scene_key(order)
            scene_id = str(scene.get("id", "")).strip()
            heading = _scene_heading(scene)
            scene_dir = f"{PROJECT_SCENES_DIR}{key}/"
            package_path = f"{scene_dir}RENDERPACKAGE.zip"
            reusable_path = output_root / package_path if output_root is not None else None
            build_status = "generated"
            if scene_prompt_edits is None and reusable_path is not None and _scene_package_reusable(
                reusable_path,
                source_hash=source_hash,
                scene_id=scene_id,
                provider=provider,
            ):
                package_bytes = reusable_path.read_bytes()
                build_status = "reused"
            else:
                package_tmp = tmp_dir / f"{key}.zip"
                package_fountain_file(
                    input_path=source_copy,
                    output_path=package_tmp,
                    provider=provider,
                    provider_version=provider_version,
                    include_provider_prompts=include_provider_prompts,
                    scene_ordinal=order,
                    duration_s=duration_s,
                    project=project,
                    prompt_edits=scene_prompt_edits,
                )
                package_bytes = package_tmp.read_bytes()

            scene_package_bytes[package_path] = package_bytes
            scene_rows.append(
                {
                    "scene_id": scene_id,
                    "scene_key": key,
                    "order": order,
                    "heading": str(heading.get("raw", "")).strip(),
                    "location_id": str(heading.get("location_id", "")).strip(),
                    "time_of_day": str(heading.get("time_of_day", "")).strip(),
                    "package_path": package_path,
                    "status": "ready",
                    "build_status": build_status,
                    "package_sha256": _sha256_bytes(package_bytes),
                    "scene_source_hash": _stable_hex(_scene_source_fingerprint(scene), 16),
                    "depends_on": [],
                }
            )

        manifest = _manifest(
            doc=doc,
            project=project,
            input_path=input_path,
            source_filename=source_filename,
            generated_at=generated_at,
            scene_rows=scene_rows,
            batch_size=batch_size,
            provider=provider,
            include_provider_prompts=include_provider_prompts,
            duration_s=duration_s,
        )
        files: dict[str, str | bytes] = {
            PROJECT_OVERVIEW_FILENAME: _project_overview_md(manifest),
            PROJECT_MANIFEST_FILENAME: json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            PROJECT_INDEX_FILENAME: _project_index(manifest),
            PROJECT_REFS_DIR: b"",
            PROJECT_STYLE_BIBLE_FILENAME: _style_bible_md(str(manifest.get("title", ""))),
            PROJECT_CONTINUITY_RULES_FILENAME: _continuity_rules_md(),
            PROJECT_CHARACTERS_FILENAME: _project_ref_characters(doc),
            PROJECT_LOCATIONS_FILENAME: _project_ref_locations(doc),
            PROJECT_SCENES_DIR: b"",
        }
        for scene in scene_rows:
            package_path = str(scene["package_path"])
            scene_dir = f"{package_path.rsplit('/', 1)[0]}/"
            files[scene_dir] = b""
            files[package_path] = scene_package_bytes[package_path]

        ordered_paths = _ordered_paths(scene_rows)
        if output_is_zip:
            _write_project_zip(output_path, files, ordered_paths)
        else:
            _write_project_dir(output_path, files, ordered_paths)

    return output_path
