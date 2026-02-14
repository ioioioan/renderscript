from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

SCHEMA_PATH = Path("renderscript.schema.v0.1.json")


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


def validate_file(path: Path) -> tuple[bool, str]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return False, f"Missing file: {path}"
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON: {exc}"
    return validate_document(document)
