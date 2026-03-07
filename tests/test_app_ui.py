from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ui_get_root_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "RenderScript Studio" in response.text


def test_ui_build_returns_zip_for_one_scene_example() -> None:
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
