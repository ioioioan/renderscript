from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from renderscript import cli
from renderscript.renderpackage import package_fountain_file
from renderscript.validate import validate_package


def _package(tmp_path: Path) -> Path:
    out_path = tmp_path / "package.zip"
    package_fountain_file(
        input_path=Path("examples/t1_dialogue_attribution.fountain"),
        output_path=out_path,
    )
    return out_path


def _copy_without(source: Path, target: Path, omitted: set[str], extra: dict[str, bytes] | None = None) -> None:
    with ZipFile(source, "r") as src, ZipFile(target, "w", compression=ZIP_STORED) as dst:
        for info in src.infolist():
            if info.filename in omitted:
                continue
            dst.writestr(info, src.read(info.filename))
        for name, payload in (extra or {}).items():
            dst.writestr(name, payload)


def test_validate_package_accepts_current_renderpackage(tmp_path: Path) -> None:
    ok, message = validate_package(_package(tmp_path))

    assert ok, message
    assert message == "Valid RenderPackage"


def test_validate_package_reports_missing_required_file(tmp_path: Path) -> None:
    source = _package(tmp_path)
    broken = tmp_path / "missing.zip"
    _copy_without(source, broken, {"DEVELOPER_FILES/action_plan.json"})

    ok, message = validate_package(broken)

    assert ok is False
    assert "missing required files" in message
    assert "DEVELOPER_FILES/action_plan.json" in message


def test_validate_package_rejects_deprecated_root_paths(tmp_path: Path) -> None:
    source = _package(tmp_path)
    broken = tmp_path / "deprecated.zip"
    _copy_without(source, broken, set(), {"shots/shot_list.csv": b"shot_id\nshot_001\n"})

    ok, message = validate_package(broken)

    assert ok is False
    assert "deprecated root paths" in message
    assert "shots/" in message


def test_validate_package_rejects_executable_workflow_files(tmp_path: Path) -> None:
    source = _package(tmp_path)
    broken = tmp_path / "executable.zip"
    _copy_without(source, broken, set(), {"DEVELOPER_FILES/run_generation.sh": b"echo no\n"})

    ok, message = validate_package(broken)

    assert ok is False
    assert "must not include executable workflow files" in message
    assert "DEVELOPER_FILES/run_generation.sh" in message


def test_validate_package_rejects_csv_rpack_shot_mismatch(tmp_path: Path) -> None:
    source = _package(tmp_path)
    broken = tmp_path / "mismatch.zip"
    _copy_without(
        source,
        broken,
        {"DEVELOPER_FILES/bindings.csv"},
        {"DEVELOPER_FILES/bindings.csv": b"shot_id,character_refs,location_refs,style_refs,prop_refs,notes\nshot_999,,,,,\n"},
    )

    ok, message = validate_package(broken)

    assert ok is False
    assert "rpack.json and bindings.csv" in message


def test_cli_validate_accepts_renderpackage_zip(tmp_path: Path, monkeypatch, capsys) -> None:
    package_path = _package(tmp_path)
    monkeypatch.setattr("sys.argv", ["renderscript", "validate", str(package_path)])

    assert cli.main() == 0
    assert "Valid RenderPackage" in capsys.readouterr().out
