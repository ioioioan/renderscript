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
    assert "Build a RenderPackage" in response.text
    assert "Screenplay to AI video workflow" in response.text
    assert "Quick Start" in response.text
    assert "Use the AI video tools you already know." in response.text


def test_public_app_tab_hides_provider_controls() -> None:
    response = client.get("/")
    app_html = response.text.split('data-pane="app"', 1)[1].split('data-pane="quick-start"', 1)[0]
    assert "name=\"provider\" value=\"universal\"" in app_html
    assert "name=\"include_provider_prompts\"" not in app_html
    assert "Runway" not in app_html
    assert "Grok" not in app_html
    assert "prompt pack" not in app_html.lower()


def test_public_tab_order() -> None:
    response = client.get("/")
    tab_labels = [
        text.split(">", 1)[1].split("<", 1)[0]
        for text in response.text.split('<button class="tab-btn')[1:]
    ]
    assert tab_labels == ["App", "Quick Start", "Creators", "About", "Developers"]


def test_quick_start_contains_creator_workflow_links() -> None:
    response = client.get("/")
    assert "START_HERE.txt" in response.text
    assert "CREATOR_GUIDE.pdf" in response.text
    assert "https://fountain.io/" in response.text
    assert "https://obsidian.md/download" in response.text
    assert "https://www.notion.com/desktop" in response.text
    assert "https://code.visualstudio.com/download" in response.text


def test_ui_build_returns_zip_for_one_scene_example(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_package_fountain_file(
        *, input_path, output_path, provider, scene_ordinal, project, provider_version="", include_provider_prompts=None
    ):
        captured["provider"] = provider
        captured["include_provider_prompts"] = include_provider_prompts
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
            "include_provider_prompts": ["grok.imagine"],
            "scene": "1",
            "project": "ui_test",
        },
        files={"screenplay_file": ("t1_dialogue_attribution.fountain", payload, "text/plain")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "attachment; filename=" in response.headers.get("content-disposition", "")
    assert len(response.content) > 0
    assert captured["provider"] == "universal"
    assert captured["include_provider_prompts"] == ["grok.imagine"]


def test_ui_build_rejects_txt_upload_with_friendly_error() -> None:
    response = client.post(
        "/build",
        data={
            "provider": "universal",
            "scene": "1",
            "project": "ui_test",
        },
        files={"screenplay_file": ("notes.txt", b"INT. TEST ROOM - DAY\nA test.\n", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type. Upload a .fountain or .fnt screenplay file." in response.text
