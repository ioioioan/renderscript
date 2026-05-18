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
    assert "SCREENPLAY TO AI-VIDEO SHOOTING PACK." in response.text
    assert (
        "Turn one screenplay scene into shot cards, base prompts, references, keeper tracking, and post-production notes."
        in response.text
    )
    assert "storyboard-led RenderPackage" in response.text
    assert "Example RenderPackage" in response.text
    assert "Quick Start" in response.text
    assert "preferred AI video tools" in response.text
    assert "AGENT_ORCHESTRATION.md" in response.text
    assert "provider_capabilities.example.json" in response.text


def test_public_app_tab_hides_provider_controls() -> None:
    response = client.get("/")
    app_html = response.text.split('data-pane="app"', 1)[1].split('data-pane="quick-start"', 1)[0]
    assert "name=\"provider\"" not in app_html
    assert "name=\"include_provider_prompts\"" not in app_html
    assert "Runway" not in app_html
    assert "Grok" not in app_html
    assert "prompt pack" not in app_html.lower()
    assert "Screenplay file" in app_html
    assert "Scene" in app_html
    assert "Project name (optional)" in app_html
    assert "Downloads a storyboard-led RenderPackage for one screenplay scene." in app_html


def test_public_tab_order() -> None:
    response = client.get("/")
    tab_labels = [
        text.split(">", 1)[1].split("<", 1)[0]
        for text in response.text.split('<button class="tab-btn')[1:]
    ]
    assert tab_labels == ["App", "Quick Start", "Creators", "About", "Developers &amp; Agents"]


def test_quick_start_contains_creator_workflow_links() -> None:
    response = client.get("/")
    assert "START_HERE.pdf" not in response.text
    assert "RENDERPACKAGE.pdf" in response.text
    assert "COPY_PASTE_PROMPTS.docx" in response.text
    assert "KEEPER_SHEET.csv" in response.text
    assert "The source <code>.fountain</code> file is included in the package for reference." in response.text
    assert "https://fountain.io/" in response.text
    assert "https://obsidian.md/download" not in response.text
    assert "https://www.notion.com/desktop" not in response.text
    assert "https://code.visualstudio.com/download" not in response.text
    assert "RenderScript does not generate video." in response.text


def test_ui_build_returns_zip_for_one_scene_example(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_package_fountain_file(
        *, input_path, output_path, provider, scene_ordinal, project, provider_version="", include_provider_prompts=None
    ):
        captured["provider"] = provider
        captured["include_provider_prompts"] = include_provider_prompts
        with ZipFile(output_path, "w", compression=ZIP_STORED) as zf:
            zf.writestr(
                "DEVELOPER_FILES/provenance.json",
                b'{"creator_guide":{"renderer_used":"text_pdf","engine":"renderscript_pdf","error":""}}\n',
            )
            zf.writestr("RENDERPACKAGE.pdf", b"%PDF-1.4\n%%EOF\n")
            zf.writestr("COPY_PASTE_PROMPTS.docx", b"PK\n")
            zf.writestr("DEVELOPER_FILES/rpack.json", b"{}\n")

    monkeypatch.setattr("app.main.package_fountain_file", fake_package_fountain_file)

    payload = Path("examples/t1_dialogue_attribution.fountain").read_bytes()
    response = client.post(
        "/build",
        data={
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
    assert captured["include_provider_prompts"] == []


def test_ui_build_rejects_txt_upload_with_friendly_error() -> None:
    response = client.post(
        "/build",
        data={
            "scene": "1",
            "project": "ui_test",
        },
        files={"screenplay_file": ("notes.txt", b"INT. TEST ROOM - DAY\nA test.\n", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported file type. Upload a .fountain or .fnt screenplay file." in response.text
