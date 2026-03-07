from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
import zipfile

NAME = "renderscript"
VERSION = "0.1.0"
REQUIRES_PYTHON = ">=3.9"
REQUIRES_DIST = [
    "jinja2>=3.1.0",
    "pillow>=10.0.0",
    "pypdf>=5.0.0",
    "playwright>=1.58.0",
]


def _dist_info_dir() -> str:
    return f"{NAME}-{VERSION}.dist-info"


def _wheel_name() -> str:
    return f"{NAME}-{VERSION}-py3-none-any.whl"


def _metadata() -> str:
    requires_dist_lines = "".join(f"Requires-Dist: {dep}\n" for dep in REQUIRES_DIST)
    return (
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: RenderScript Phase 1A bootstrap\n"
        f"Requires-Python: {REQUIRES_PYTHON}\n"
        f"{requires_dist_lines}"
    )


def _wheel() -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: build_backend.py\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    )


def _entry_points() -> str:
    return "[console_scripts]\nrenderscript = renderscript.cli:main\n"


def _record_line(path: str, data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    b64 = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return f"{path},sha256={b64},{len(data)}"


def _package_files() -> list[Path]:
    package_root = Path("renderscript")
    files: list[Path] = []
    for path in package_root.rglob("*"):
        if path.is_dir():
            continue
        if path.suffix in {".py", ".html", ".css", ".png"}:
            files.append(path)
    return sorted(files)


def _build(wheel_directory: str) -> str:
    wheel_dir = Path(wheel_directory)
    wheel_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = wheel_dir / _wheel_name()

    dist_info = _dist_info_dir()
    record: list[str] = []

    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src in _package_files():
            arc = src.as_posix()
            data = src.read_bytes()
            zf.writestr(arc, data)
            record.append(_record_line(arc, data))

        meta_path = f"{dist_info}/METADATA"
        meta_data = _metadata().encode("utf-8")
        zf.writestr(meta_path, meta_data)
        record.append(_record_line(meta_path, meta_data))

        wheel_meta_path = f"{dist_info}/WHEEL"
        wheel_meta_data = _wheel().encode("utf-8")
        zf.writestr(wheel_meta_path, wheel_meta_data)
        record.append(_record_line(wheel_meta_path, wheel_meta_data))

        entry_path = f"{dist_info}/entry_points.txt"
        entry_data = _entry_points().encode("utf-8")
        zf.writestr(entry_path, entry_data)
        record.append(_record_line(entry_path, entry_data))

        record_path = f"{dist_info}/RECORD"
        record_data = ("\n".join(record + [f"{record_path},,"]) + "\n").encode("utf-8")
        zf.writestr(record_path, record_data)

    return os.path.basename(wheel_path)


def build_wheel(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build(wheel_directory)


def build_editable(wheel_directory: str, config_settings=None, metadata_directory=None) -> str:
    return _build(wheel_directory)


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory: str, config_settings=None) -> str:
    dist_info = Path(metadata_directory) / _dist_info_dir()
    dist_info.mkdir(parents=True, exist_ok=True)
    (dist_info / "METADATA").write_text(_metadata(), encoding="utf-8")
    (dist_info / "WHEEL").write_text(_wheel(), encoding="utf-8")
    (dist_info / "entry_points.txt").write_text(_entry_points(), encoding="utf-8")
    return dist_info.name
