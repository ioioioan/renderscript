from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

SCHEMA_PATH = Path("renderscript.schema.v0.1.json")
REQUIRED_PACKAGE_PATHS = [
    "RENDERPACKAGE.pdf",
    "COPY_PASTE_PROMPTS.docx",
    "KEEPER_SHEET.csv",
    "prompts/",
    "prompts/reference_prompts.md",
    "assets/",
    "assets/refs/",
    "assets/refs/characters/",
    "assets/refs/locations/",
    "assets/refs/props/",
    "assets/refs/costumes/",
    "assets/refs/vehicles/",
    "assets/refs/creatures/",
    "assets/refs/style/",
    "assets/refs/lighting/",
    "assets/refs/vfx/",
    "audio/",
    "audio/voice_bible.md",
    "audio/character_voice_refs/",
    "audio/voice_samples/",
    "DEVELOPER_FILES/",
    "DEVELOPER_FILES/rpack.json",
    "DEVELOPER_FILES/provenance.json",
    "DEVELOPER_FILES/shot_list.csv",
    "DEVELOPER_FILES/bindings.csv",
    "DEVELOPER_FILES/AGENT_ORCHESTRATION.md",
    "DEVELOPER_FILES/provider_capabilities.example.json",
    "DEVELOPER_FILES/package_map.md",
    "DEVELOPER_FILES/action_plan.json",
    "DEVELOPER_FILES/execution_contract.json",
    "DEVELOPER_FILES/approval_checkpoints.json",
    "DEVELOPER_FILES/take_log.csv",
    "DEVELOPER_FILES/keeper_decisions.csv",
    "DEVELOPER_FILES/prompt_packs/",
    "DEVELOPER_FILES/prompt_packs/shot_prompts.md",
    "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md",
    "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md",
]
DEPRECATED_ACTIVE_ROOT_PATHS = [
    "CREATOR_GUIDE_START_HERE.md",
    "START_HERE.txt",
    "PACKAGE_MAP.md",
    "shots/",
    "bindings/",
    "keepers/",
    "edit_guide/",
    "dev/",
]
EXECUTABLE_SUFFIXES = (".py", ".sh", ".bat", ".exe", ".command", ".ps1")
PROJECT_REQUIRED_REFS = {
    "style_bible": "project_refs/style_bible.md",
    "continuity_rules": "project_refs/continuity_rules.md",
    "characters": "project_refs/characters.json",
    "locations": "project_refs/locations.json",
}


class ValidationError(Exception):
    pass


def _resolve_ref(root: dict[str, object], ref: str) -> dict[str, object]:
    if not ref.startswith("#/"):
        raise ValidationError(f"Unsupported $ref: {ref}")
    node: object = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise ValidationError(f"Invalid $ref target: {ref}")
        node = node[part]
    if not isinstance(node, dict):
        raise ValidationError(f"$ref did not resolve to object: {ref}")
    return node


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _matches(instance: object, schema: dict[str, object], root: dict[str, object]) -> bool:
    try:
        _validate(instance, schema, root, "$")
        return True
    except ValidationError:
        return False


def _validate(instance: object, schema: dict[str, object], root: dict[str, object], path: str) -> None:
    if "$ref" in schema:
        ref_schema = _resolve_ref(root, str(schema["$ref"]))
        _validate(instance, ref_schema, root, path)
        return

    if "allOf" in schema:
        for sub in schema["allOf"]:  # type: ignore[index]
            _validate(instance, sub, root, path)

    if "if" in schema and "then" in schema:
        if_schema = schema["if"]  # type: ignore[index]
        then_schema = schema["then"]  # type: ignore[index]
        if _matches(instance, if_schema, root):
            _validate(instance, then_schema, root, path)

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(instance, dict):
            raise ValidationError(f"{path} must be an object")
        required = schema.get("required", [])
        for key in required:  # type: ignore[assignment]
            if key not in instance:
                raise ValidationError(f"{path}.{key} is required")

        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)

        if additional is False:
            allowed = set(properties.keys())
            for key in instance.keys():
                if key not in allowed:
                    raise ValidationError(f"{path}.{key} is not allowed")

        for key, subschema in properties.items():
            if key in instance:
                _validate(instance[key], subschema, root, f"{path}.{key}")

    elif expected_type == "array":
        if not isinstance(instance, list):
            raise ValidationError(f"{path} must be an array")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(instance):
                _validate(item, item_schema, root, f"{path}[{i}]")
        if schema.get("uniqueItems"):
            seen: set[str] = set()
            for item in instance:
                key = json.dumps(item, sort_keys=True)
                if key in seen:
                    raise ValidationError(f"{path} items must be unique")
                seen.add(key)

    elif expected_type == "string":
        if not isinstance(instance, str):
            raise ValidationError(f"{path} must be a string")
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            raise ValidationError(f"{path} is shorter than {min_length}")
        max_length = schema.get("maxLength")
        if isinstance(max_length, int) and len(instance) > max_length:
            raise ValidationError(f"{path} is longer than {max_length}")
        enum = schema.get("enum")
        if isinstance(enum, list) and instance not in enum:
            raise ValidationError(f"{path} must be one of {enum}")
        if schema.get("format") == "date-time" and not _is_datetime(instance):
            raise ValidationError(f"{path} must be date-time")

    elif expected_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            raise ValidationError(f"{path} must be an integer")
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and instance < minimum:
            raise ValidationError(f"{path} must be >= {minimum}")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{path} must equal {schema['const']!r}")


def validate_document(document: dict[str, object]) -> tuple[bool, str]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        _validate(document, schema, schema, "$")
        return True, "Valid"
    except FileNotFoundError:
        return False, f"Missing schema file: {SCHEMA_PATH}"
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON: {exc}"
    except ValidationError as exc:
        return False, f"Schema validation failed: {exc}"


def _read_json(zf: ZipFile, path: str) -> dict[str, object]:
    try:
        value = json.loads(zf.read(path).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be a JSON object")
    return value


def _csv_ids(zf: ZipFile, path: str) -> set[str]:
    import csv
    from io import StringIO

    rows = csv.DictReader(StringIO(zf.read(path).decode("utf-8")))
    ids: set[str] = set()
    if rows.fieldnames is None or "shot_id" not in rows.fieldnames:
        raise ValidationError(f"{path} must include a shot_id column")
    for row in rows:
        shot_id = (row.get("shot_id") or "").strip()
        if shot_id:
            ids.add(shot_id)
    return ids


def validate_package(path: Path) -> tuple[bool, str]:
    try:
        with ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            missing = [required for required in REQUIRED_PACKAGE_PATHS if required not in names]
            if missing:
                return False, "RenderPackage is missing required files: " + ", ".join(missing)

            source_files = [
                name
                for name in names
                if "/" not in name and name.lower().endswith((".fountain", ".fnt"))
            ]
            if not source_files:
                return False, "RenderPackage is missing the source screenplay at the package root."

            missing_roots = [root for root in ("refs/", "generated_shots/") if not any(name.startswith(root) for name in names)]
            if missing_roots:
                return False, "RenderPackage is missing required folders: " + ", ".join(missing_roots)

            deprecated = [old for old in DEPRECATED_ACTIVE_ROOT_PATHS if any(name == old or name.startswith(old) for name in names)]
            if deprecated:
                return False, "RenderPackage uses deprecated root paths: " + ", ".join(sorted(set(deprecated)))

            executables = sorted(name for name in names if name.lower().endswith(EXECUTABLE_SUFFIXES))
            if executables:
                return False, "RenderPackage must not include executable workflow files: " + ", ".join(executables)

            rpack = _read_json(zf, "DEVELOPER_FILES/rpack.json")
            shots = rpack.get("shots", [])
            if not isinstance(shots, list):
                return False, "DEVELOPER_FILES/rpack.json shots must be a list."
            rpack_shot_ids = {str(shot.get("shot_id", "")).strip() for shot in shots if isinstance(shot, dict)}
            rpack_shot_ids.discard("")
            shot_list_ids = _csv_ids(zf, "DEVELOPER_FILES/shot_list.csv")
            binding_ids = _csv_ids(zf, "DEVELOPER_FILES/bindings.csv")
            if rpack_shot_ids != shot_list_ids:
                return False, "RenderPackage shot IDs do not match between rpack.json and shot_list.csv."
            if rpack_shot_ids != binding_ids:
                return False, "RenderPackage shot IDs do not match between rpack.json and bindings.csv."

            for prompt_path in (
                "DEVELOPER_FILES/prompt_packs/shot_prompts.md",
                "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md",
                "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md",
            ):
                text = zf.read(prompt_path).decode("utf-8", errors="replace")
                missing_ids = sorted(shot_id for shot_id in rpack_shot_ids if shot_id not in text)
                if missing_ids:
                    return False, f"{prompt_path} is missing shot IDs: {', '.join(missing_ids)}"

            orchestration = zf.read("DEVELOPER_FILES/AGENT_ORCHESTRATION.md").decode("utf-8", errors="replace")
            if "RenderPackage is agent-actionable, not auto-executable" not in orchestration:
                return False, "AGENT_ORCHESTRATION.md must state that RenderPackage is agent-actionable, not auto-executable."

            for data_path in (
                "DEVELOPER_FILES/action_plan.json",
                "DEVELOPER_FILES/execution_contract.json",
                "DEVELOPER_FILES/approval_checkpoints.json",
            ):
                data = _read_json(zf, data_path)
                if data.get("non_executable") is not True:
                    return False, f"{data_path} must be marked non_executable."
    except FileNotFoundError:
        return False, f"Missing file: {path}"
    except BadZipFile:
        return False, f"Invalid RenderPackage zip: {path}"
    except KeyError as exc:
        return False, f"RenderPackage is missing required file: {exc}"
    except ValidationError as exc:
        return False, f"RenderPackage validation failed: {exc}"
    return True, "Valid RenderPackage"


def _safe_project_member(path: str) -> bool:
    if not path or path.startswith("/") or path.startswith("\\"):
        return False
    parts = path.replace("\\", "/").split("/")
    return ".." not in parts and all(part != "" for part in parts if part != parts[-1])


def _zip_has_project_manifest(path: Path) -> bool:
    try:
        with ZipFile(path, "r") as zf:
            return "project_manifest.json" in zf.namelist()
    except (FileNotFoundError, BadZipFile):
        return False


def _project_bundle_zip_entries(path: Path) -> tuple[set[str], dict[str, bytes]]:
    with ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        payloads = {name: zf.read(name) for name in names if not name.endswith("/")}
    return names, payloads


def _project_bundle_dir_entries(path: Path) -> tuple[set[str], dict[str, bytes]]:
    names: set[str] = set()
    payloads: dict[str, bytes] = {}
    for item in path.rglob("*"):
        relative = item.relative_to(path).as_posix()
        if item.is_dir():
            names.add(f"{relative}/")
        else:
            names.add(relative)
            payloads[relative] = item.read_bytes()
    return names, payloads


def _read_project_json(payloads: dict[str, bytes], path: str) -> dict[str, object]:
    if path not in payloads:
        raise ValidationError(f"Missing required project file: {path}")
    try:
        value = json.loads(payloads[path].decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be a JSON object")
    return value


def _validate_nested_renderpackage(payload: bytes, expected_scene_id: str) -> None:
    try:
        with ZipFile(BytesIO(payload), "r") as zf:
            names = set(zf.namelist())
            missing = [required for required in REQUIRED_PACKAGE_PATHS if required not in names]
            if missing:
                raise ValidationError("nested RenderPackage is missing required files: " + ", ".join(missing))
            rpack = _read_json(zf, "DEVELOPER_FILES/rpack.json")
    except BadZipFile as exc:
        raise ValidationError("scene package is not a valid RenderPackage zip") from exc
    scene = rpack.get("scene", {}) if isinstance(rpack, dict) else {}
    if not isinstance(scene, dict) or str(scene.get("scene_id", "")) != expected_scene_id:
        raise ValidationError("scene package scene_id does not match project_manifest.json")


def validate_project_bundle(path: Path) -> tuple[bool, str]:
    try:
        if path.is_dir():
            names, payloads = _project_bundle_dir_entries(path)
        else:
            names, payloads = _project_bundle_zip_entries(path)

        for required in ("project_manifest.json", "project_index.json", "PROJECT_OVERVIEW.md", "project_refs/"):
            if required not in names and required not in payloads:
                return False, f"Project bundle is missing required path: {required}"

        manifest = _read_project_json(payloads, "project_manifest.json")
        if manifest.get("bundle_type") != "renderscript.project_bundle":
            return False, "project_manifest.json bundle_type must be renderscript.project_bundle."
        if not manifest.get("project_id"):
            return False, "project_manifest.json project_id is required."
        source = manifest.get("source", {})
        if not isinstance(source, dict) or not source.get("hash"):
            return False, "project_manifest.json source.hash is required."

        refs = manifest.get("refs", {})
        if not isinstance(refs, dict):
            return False, "project_manifest.json refs must be an object."
        for key, required_path in PROJECT_REQUIRED_REFS.items():
            if refs.get(key) != required_path:
                return False, f"project_manifest.json refs.{key} must be {required_path}."
            if required_path not in payloads:
                return False, f"Project bundle is missing required project ref: {required_path}"

        scenes = manifest.get("scenes", [])
        if not isinstance(scenes, list) or not scenes:
            return False, "project_manifest.json scenes must be a non-empty list."
        scene_ids: set[str] = set()
        scene_keys: set[str] = set()
        orders: set[int] = set()
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                return False, f"project_manifest.json scenes[{index}] must be an object."
            scene_id = str(scene.get("scene_id", "")).strip()
            scene_key = str(scene.get("scene_key", "")).strip()
            package_path = str(scene.get("package_path", "")).strip()
            order = scene.get("order")
            if not scene_id:
                return False, f"project_manifest.json scenes[{index}].scene_id is required."
            if scene_id in scene_ids:
                return False, f"Duplicate scene_id in project_manifest.json: {scene_id}"
            scene_ids.add(scene_id)
            if not scene_key:
                return False, f"project_manifest.json scenes[{index}].scene_key is required."
            if scene_key in scene_keys:
                return False, f"Duplicate scene_key in project_manifest.json: {scene_key}"
            scene_keys.add(scene_key)
            if not isinstance(order, int) or isinstance(order, bool) or order <= 0:
                return False, f"project_manifest.json scenes[{index}].order must be a positive integer."
            if order in orders:
                return False, f"Duplicate scene order in project_manifest.json: {order}"
            orders.add(order)
            if not _safe_project_member(package_path):
                return False, f"Unsafe scene package path in project_manifest.json: {package_path}"
            if package_path not in payloads:
                return False, f"Project bundle is missing scene package: {package_path}"
            _validate_nested_renderpackage(payloads[package_path], scene_id)

        batches = manifest.get("batches", [])
        if not isinstance(batches, list) or not batches:
            return False, "project_manifest.json batches must be a non-empty list."
        batch_ids: set[str] = set()
        for index, batch in enumerate(batches):
            if not isinstance(batch, dict):
                return False, f"project_manifest.json batches[{index}] must be an object."
            batch_id = str(batch.get("batch_id", "")).strip()
            if not batch_id:
                return False, f"project_manifest.json batches[{index}].batch_id is required."
            if batch_id in batch_ids:
                return False, f"Duplicate batch_id in project_manifest.json: {batch_id}"
            batch_ids.add(batch_id)
            batch_scene_ids = batch.get("scene_ids", [])
            if not isinstance(batch_scene_ids, list) or not batch_scene_ids:
                return False, f"project_manifest.json batches[{index}].scene_ids must be a non-empty list."
            unknown = sorted(str(scene_id) for scene_id in batch_scene_ids if str(scene_id) not in scene_ids)
            if unknown:
                return False, f"Batch references unknown scene_id values: {', '.join(unknown)}"

        project_index = _read_project_json(payloads, "project_index.json")
        if project_index.get("project_id") != manifest.get("project_id"):
            return False, "project_index.json project_id does not match project_manifest.json."

    except FileNotFoundError:
        return False, f"Missing file: {path}"
    except BadZipFile:
        return False, f"Invalid project bundle zip: {path}"
    except KeyError as exc:
        return False, f"Project bundle is missing required file: {exc}"
    except ValidationError as exc:
        return False, f"Project bundle validation failed: {exc}"
    return True, "Valid RenderScript project bundle"


def validate_file(path: Path) -> tuple[bool, str]:
    if path.suffix.lower() == ".zip":
        if _zip_has_project_manifest(path):
            return validate_project_bundle(path)
        return validate_package(path)
    if path.is_dir() and (path / "project_manifest.json").exists():
        return validate_project_bundle(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"Missing file: {path}"
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON: {exc}"
    return validate_document(document)
