from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ui_get_root_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "RenderScript Studio" in response.text


def test_ui_build_returns_zip_for_one_scene_example(monkeypatch) -> None:
    def fake_package_fountain_file(
        *, input_path, output_path, provider, scene_ordinal, project, provider_version="", include_provider_prompts=None
    ):
        with ZipFile(output_path, "w", compression=ZIP_STORED) as zf:
            zf.writestr(
                "dev/provenance.json",
                b'{"creator_guide":{"renderer_used":"html","engine":"playwright","error":""}}\n',
            )
            zf.writestr("CREATOR_GUIDE.pdf", b"%PDF-1.4\n%%EOF\n")
            zf.writestr("dev/rpack.json", b"{}\n")

    monkeypatch.setattr("app.main.package_fountain_file", fake_package_fountain_file)

    payload = Path("examples/t1_dialogue_attribution.fountain").read_bytes()
    response = client.post(
        "/build",
        data={
            "provider": "universal",
            "scene": "1",
            "project": "ui_test",
        },
        files={"screenplay_file": ("t1_dialogue_attribution.fountain", payload, "text/plain")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert len(response.content) > 0
