from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import pytest

from renderscript import cli
from renderscript.project import package_project_file
from renderscript.validate import validate_file, validate_project_bundle


def _zip_bytes_by_name(path: Path) -> dict[str, bytes | None]:
    with ZipFile(path, "r") as zf:
        return {name: None if name.endswith("/") else zf.read(name) for name in zf.namelist()}


def _write_zip(path: Path, files: dict[str, bytes | None]) -> None:
    with ZipFile(path, "w", compression=ZIP_STORED) as zf:
        for name, content in files.items():
            info = ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = ZIP_STORED
            if name.endswith("/"):
                info.external_attr = 0o40755 << 16
                zf.writestr(info, b"")
            else:
                info.external_attr = 0o100644 << 16
                zf.writestr(info, content or b"")


def test_project_cli_generates_manifest_index_refs_and_scene_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path("examples/t3_prop_dependency.fountain")
    out_path = tmp_path / "project_bundle.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "project",
            str(source),
            "--project",
            "pilot",
            "--batch-size",
            "1",
            "-o",
            str(out_path),
        ],
    )

    assert cli.main() == 0
    assert out_path.exists()
    ok, message = validate_file(out_path)
    assert ok, message

    with ZipFile(out_path, "r") as zf:
        names = set(zf.namelist())
        manifest = json.loads(zf.read("project_manifest.json"))
        project_index = json.loads(zf.read("project_index.json"))
        characters = json.loads(zf.read("project_refs/characters.json"))
        locations = json.loads(zf.read("project_refs/locations.json"))
        nested_scene = zf.read("scenes/sc_001/RENDERPACKAGE.zip")

    assert "PROJECT_OVERVIEW.md" in names
    assert "project_refs/style_bible.md" in names
    assert "project_refs/continuity_rules.md" in names
    assert "scenes/sc_001/RENDERPACKAGE.zip" in names
    assert "scenes/sc_002/RENDERPACKAGE.zip" in names
    assert manifest["bundle_type"] == "renderscript.project_bundle"
    assert manifest["project_id"].startswith("prj_pilot_")
    assert manifest["source"]["scene_count"] == 2
    assert len(manifest["scenes"]) == 2
    assert len(manifest["batches"]) == 2
    assert manifest["build"]["incremental_scene_packages"] is True
    assert project_index["scene_count"] == 2
    assert project_index["project_id"] == manifest["project_id"]
    assert characters["rules"]
    assert locations["locations"]
    with ZipFile(BytesIO(nested_scene), "r") as nested:
        rpack = json.loads(nested.read("DEVELOPER_FILES/rpack.json"))
    assert rpack["scene"]["scene_id"] == manifest["scenes"][0]["scene_id"]


def test_project_directory_output_reuses_matching_scene_packages(tmp_path: Path) -> None:
    source = Path("examples/t3_prop_dependency.fountain")
    out_dir = tmp_path / "project_bundle"

    package_project_file(source, out_dir, project="pilot")
    first_manifest = json.loads((out_dir / "project_manifest.json").read_text(encoding="utf-8"))
    assert {scene["build_status"] for scene in first_manifest["scenes"]} == {"generated"}

    package_project_file(source, out_dir, project="pilot")
    second_manifest = json.loads((out_dir / "project_manifest.json").read_text(encoding="utf-8"))
    assert {scene["build_status"] for scene in second_manifest["scenes"]} == {"reused"}
    ok, message = validate_project_bundle(out_dir)
    assert ok, message


def test_project_validation_catches_unknown_batch_scene(tmp_path: Path) -> None:
    source = Path("examples/t3_prop_dependency.fountain")
    out_path = tmp_path / "project_bundle.zip"
    package_project_file(source, out_path, project="pilot")
    files = _zip_bytes_by_name(out_path)
    manifest = json.loads(files["project_manifest.json"] or b"{}")
    manifest["batches"][0]["scene_ids"].append("scn_missing")
    files["project_manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    bad_path = tmp_path / "bad_project_bundle.zip"
    _write_zip(bad_path, files)

    ok, message = validate_file(bad_path)
    assert not ok
    assert "unknown scene_id" in message
