from __future__ import annotations

import json
import re
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from renderscript import cli
from renderscript.providers import GROK_PROVIDER, PROVIDER_REGISTRY


BASE_REQUIRED_PATHS = [
    "RENDERPACKAGE.pdf",
    "COPY_PASTE_PROMPTS.docx",
    "KEEPER_SHEET.csv",
    "DEVELOPER_FILES/",
    "DEVELOPER_FILES/rpack.json",
    "DEVELOPER_FILES/provenance.json",
    "DEVELOPER_FILES/shot_list.csv",
    "DEVELOPER_FILES/bindings.csv",
    "DEVELOPER_FILES/AGENT_ORCHESTRATION.md",
    "DEVELOPER_FILES/provider_capabilities.example.json",
    "DEVELOPER_FILES/prompt_packs/",
    "DEVELOPER_FILES/prompt_packs/shot_prompts.md",
    "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md",
    "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md",
    "DEVELOPER_FILES/package_map.md",
]


def _required_paths(
    *,
    source_filename: str = "t1_dialogue_attribution.fountain",
    reference_paths: list[str] | None = None,
    include_runway_prompts: bool = False,
    include_grok_prompts: bool = False,
) -> list[str]:
    refs = reference_paths or [
        "refs/01_style_reference/",
        "refs/02_location_reference/",
        "refs/03_character_reference_alice/",
        "refs/04_character_reference_bob/",
    ]
    return [
        "RENDERPACKAGE.pdf",
        "COPY_PASTE_PROMPTS.docx",
        "KEEPER_SHEET.csv",
        source_filename,
        *refs,
        "generated_shots/takes/",
        "generated_shots/keepers/",
        *BASE_REQUIRED_PATHS[3:],
    ]


def test_provider_registry_includes_grok_imagine() -> None:
    grok = PROVIDER_REGISTRY[GROK_PROVIDER]
    assert grok.id == "grok.imagine"
    assert grok.label == "Grok Imagine"
    assert grok.prompt_filename == "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md"
    assert grok.supported is True
    assert grok.requires_reference_image is True


def _zip_contents(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _csv_rows(raw: bytes) -> list[dict[str, str]]:
    import csv

    return list(csv.DictReader(StringIO(raw.decode("utf-8"))))


def _rpack_without_generated_at(raw: bytes) -> dict[str, object]:
    payload = json.loads(raw.decode("utf-8"))
    payload.pop("generated_at", None)
    return payload


def _provenance_without_generated_at(raw: bytes) -> dict[str, object]:
    payload = json.loads(raw.decode("utf-8"))
    payload.pop("generated_at", None)
    return payload


def _pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return raw.decode("latin-1", errors="ignore")
    from io import BytesIO

    # pypdf expects a binary stream; keep fallback above for environments without pypdf.
    reader = PdfReader(BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _pdf_page_count(raw: bytes) -> int:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return 0
    from io import BytesIO

    reader = PdfReader(BytesIO(raw))
    return len(reader.pages)


def _has_pypdf() -> bool:
    try:
        import pypdf  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return False
    return True


def _docx_text(raw: bytes) -> str:
    with ZipFile(BytesIO(raw), "r") as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join(node.text or "" for node in root.findall(".//w:t", ns))


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_package_generates_required_files_and_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_one = tmp_path / "out_one.zip"
    out_two = tmp_path / "out_two.zip"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "-o",
            str(out_one),
        ],
    )
    assert cli.main() == 0
    assert out_one.exists()

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "-o",
            str(out_two),
        ],
    )
    assert cli.main() == 0
    assert out_two.exists()

    required_paths = _required_paths()
    with ZipFile(out_one, "r") as zf:
        assert zf.namelist() == required_paths

    contents_one = _zip_contents(out_one)
    contents_two = _zip_contents(out_two)
    assert set(contents_one.keys()) == set(required_paths)
    assert set(contents_two.keys()) == set(required_paths)
    assert contents_one["t1_dialogue_attribution.fountain"] == source.read_bytes()

    for path in required_paths:
        if path == "DEVELOPER_FILES/rpack.json":
            assert _rpack_without_generated_at(contents_one[path]) == _rpack_without_generated_at(contents_two[path])
            continue
        if path == "DEVELOPER_FILES/provenance.json":
            assert _provenance_without_generated_at(contents_one[path]) == _provenance_without_generated_at(
                contents_two[path]
            )
            continue
        if path.endswith(".pdf"):
            if _has_pypdf():
                assert _pdf_text(contents_one[path]) == _pdf_text(contents_two[path])
            continue
        if path == "COPY_PASTE_PROMPTS.docx":
            assert _docx_text(contents_one[path]) == _docx_text(contents_two[path])
            continue
        assert contents_one[path] == contents_two[path]

    rpack = json.loads(contents_one["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    provenance = json.loads(contents_one["DEVELOPER_FILES/provenance.json"].decode("utf-8"))
    assert rpack["target_provider"] == "universal"
    assert rpack["selected_providers"] == ["universal"]
    assert rpack["generator"]["name"] == "RenderScript AI"
    assert "version" in rpack["generator"]
    assert isinstance(rpack["generated_at"], str)
    assert rpack["generated_at"].endswith("Z")
    assert 8 <= len(rpack["shots"]) <= 12
    assert rpack["debug"]["creator_guide"]["renderer_used"] == "html"
    assert isinstance(rpack["debug"]["creator_guide"]["error"], str)
    agent_contract = rpack["agent_orchestration"]
    assert agent_contract["source_of_truth"] == "DEVELOPER_FILES/rpack.json"
    assert agent_contract["agent_contract"] == "DEVELOPER_FILES/AGENT_ORCHESTRATION.md"
    assert agent_contract["provider_capabilities_example"] == "DEVELOPER_FILES/provider_capabilities.example.json"
    assert agent_contract["keeper_sheet_path"] == "KEEPER_SHEET.csv"
    assert agent_contract["provenance_path"] == "DEVELOPER_FILES/provenance.json"
    assert agent_contract["prompt_pack_paths"]["universal"] == "DEVELOPER_FILES/prompt_packs/shot_prompts.md"
    assert agent_contract["reference_folders"]
    for reference in agent_contract["reference_folders"]:
        assert reference["path"].startswith("refs/")
        assert reference["base_prompt"]
        assert reference["used_in"]
    assert len(agent_contract["shots"]) == len(rpack["shots"])
    for agent_shot in agent_contract["shots"]:
        assert agent_shot["shot_id"]
        assert agent_shot["shot_intent"]
        assert agent_shot["base_prompt"]
        assert "No subtitles, captions, logos, watermarks, or on-screen text." in agent_shot["base_prompt"]
        assert agent_shot["references"]
        assert agent_shot["reference_ids"]
        assert "character_refs" in agent_shot["reference_ids"]

    shot_rows = _csv_rows(contents_one["DEVELOPER_FILES/shot_list.csv"])
    bindings_rows = _csv_rows(contents_one["DEVELOPER_FILES/bindings.csv"])
    rubric_rows = _csv_rows(contents_one["KEEPER_SHEET.csv"])
    prompt_text = contents_one["DEVELOPER_FILES/prompt_packs/shot_prompts.md"].decode("utf-8")

    assert len(shot_rows) == len(rpack["shots"])
    assert len(bindings_rows) == len(rpack["shots"])
    assert len(rubric_rows) == len(rpack["shots"])
    assert list(shot_rows[0].keys()) == [
        "shot_id",
        "status",
        "beat",
        "shot_type",
        "camera",
        "description",
        "characters",
        "location",
        "style_ref",
        "duration_hint",
    ]
    assert list(bindings_rows[0].keys()) == [
        "shot_id",
        "character_refs",
        "location_refs",
        "style_refs",
        "prop_refs",
        "notes",
    ]
    assert list(rubric_rows[0].keys()) == [
        "shot_id",
        "keeper_take",
        "usable",
        "notes",
    ]

    shot_beats = {row["shot_id"]: row["beat"] for row in shot_rows}
    rubric_ids = {row["shot_id"] for row in rubric_rows}
    for row in bindings_rows:
        assert row["location_refs"] == "loc_01_ref_01"
        assert row["style_refs"] == "style_01_ref_01"
        if row["shot_id"] in shot_beats and ": " in shot_beats[row["shot_id"]]:
            assert row["character_refs"], f"dialogue shot missing character refs: {row['shot_id']}"
    assert rubric_ids == {shot["shot_id"] for shot in rpack["shots"]}

    for shot in rpack["shots"]:
        assert shot["shot_id"] in prompt_text
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in prompt_text
    assert prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])
    assert ".." not in prompt_text
    assert "?." not in prompt_text
    assert "!." not in prompt_text
    assert "  " not in prompt_text

    package_map = contents_one["DEVELOPER_FILES/package_map.md"].decode("utf-8")
    assert "## Creator-facing files" in package_map
    assert "The source `.fountain` screenplay is included at the package root for reference." in package_map
    assert "## Reference folders" in package_map
    assert "## Developer files" in package_map
    assert "## Agent orchestration" in package_map
    assert "AGENT_ORCHESTRATION.md" in package_map
    assert "provider_capabilities.example.json" in package_map
    assert "Agents should use the package after it is generated" in package_map
    assert "DEVELOPER_FILES/bindings.csv" in package_map
    assert "KEEPER_SHEET.csv" in package_map
    assert "This package uses the Universal workflow." in package_map
    assert "Selected prompt profile: `DEVELOPER_FILES/prompt_packs/shot_prompts.md`." in package_map
    assert "provider profile" not in package_map
    assert "Grok Imagine" not in package_map

    assert provenance["provider"] == "universal"
    assert provenance["creator_guide"]["renderer_used"] == "html"

    universal_pdf_text = _pdf_text(contents_one["RENDERPACKAGE.pdf"])
    normalized_universal_pdf_text = _normalize_ws(universal_pdf_text)
    if _has_pypdf():
        assert "Shot Cards / Storyboard" in normalized_universal_pdf_text
        assert "Reference Setup" in normalized_universal_pdf_text
        assert "REFERENCE BOARD" in normalized_universal_pdf_text
        assert "References are reusable visual ingredients for your shots." in normalized_universal_pdf_text
        assert "REFERENCE BASE PROMPT" in normalized_universal_pdf_text
        assert "Reference folders are already created for this scene." in normalized_universal_pdf_text
        assert "help you keep the scene organized in one place" in normalized_universal_pdf_text
        assert "Use one strong reference image to start." in normalized_universal_pdf_text
        assert "USE FOR" in normalized_universal_pdf_text
        assert "manually attach or upload" in normalized_universal_pdf_text
        assert "Keeper Workflow" in normalized_universal_pdf_text
        assert "POST-PRODUCTION WORKFLOW" in normalized_universal_pdf_text
        assert "Dialogue in the prompt helps the video tool understand the performance moment." in normalized_universal_pdf_text
        assert "Scene summary" in normalized_universal_pdf_text
        assert "This package was generated from Scene 1 of the screenplay." in normalized_universal_pdf_text
        assert "Characters: Alice, Bob" in normalized_universal_pdf_text
        assert "Location: Int. Server Room - Night" in normalized_universal_pdf_text
        assert "SHOT 001" in normalized_universal_pdf_text
        assert normalized_universal_pdf_text.count("BASE PROMPT") == len(rpack["shots"]) + len(
            agent_contract["reference_folders"]
        )
        assert "Copy this section into your AI video tool as the starting prompt." in normalized_universal_pdf_text
        assert "OPTIONAL TUNING" in normalized_universal_pdf_text
        assert "KEEP CONSISTENT" in normalized_universal_pdf_text
        assert "GENERATION CHECK" in normalized_universal_pdf_text
        assert "A usable take should:" in normalized_universal_pdf_text
        assert "generated_shots/takes/" in normalized_universal_pdf_text
        assert "generated_shots/keepers/" in normalized_universal_pdf_text
        assert "You do not need DEVELOPER_FILES to use this package." in normalized_universal_pdf_text
        assert "DEVELOPER_FILES" in normalized_universal_pdf_text
        assert "style_01_ref_01" not in normalized_universal_pdf_text
    copy_doc = _docx_text(contents_one["COPY_PASTE_PROMPTS.docx"])
    assert "COPY / PASTE BASE PROMPTS" in copy_doc
    assert "RenderScript provides base prompts and tuning notes." in copy_doc
    assert "REFERENCE BASE PROMPTS" in copy_doc
    assert "SHOT BASE PROMPTS" in copy_doc
    assert "Reference base prompts help you create reusable visual ingredients." in copy_doc
    assert "Shot base prompts help you generate video takes." in copy_doc
    assert "SHOT 001 -" in copy_doc
    assert copy_doc.count("BASE PROMPT") == len(rpack["shots"]) + len(agent_contract["reference_folders"]) + 3
    assert "TUNING NOTES" in copy_doc
    assert "Camera movement:" in copy_doc
    for shot in rpack["shots"]:
        assert str(shot["shot_id"]).replace("shot_", "SHOT ") in copy_doc
    assert "ALICE:" not in copy_doc
    assert "BOB:" not in copy_doc
    assert "MAYA:" not in copy_doc
    assert provenance["creator_guide"]["engine"] == "playwright"
    assert isinstance(provenance["creator_guide"]["error"], str)
    assert "START_HERE.pdf" not in contents_one
    assert "START_HERE.txt" not in contents_one
    assert "PACKAGE_MAP.md" not in contents_one
    assert not any(name.endswith(".md") and not name.startswith("DEVELOPER_FILES/") for name in contents_one)
    agent_orchestration = contents_one["DEVELOPER_FILES/AGENT_ORCHESTRATION.md"].decode("utf-8")
    assert "# Agent Orchestration" in agent_orchestration
    assert "An agent should not recreate the package." in agent_orchestration
    assert "Submit generation jobs only when the user has configured provider access" in agent_orchestration
    assert "generated_shots/takes/" in agent_orchestration
    assert "generated_shots/keepers/" in agent_orchestration
    assert "Do not place generated media inside DEVELOPER_FILES." in agent_orchestration
    provider_capabilities = json.loads(
        contents_one["DEVELOPER_FILES/provider_capabilities.example.json"].decode("utf-8")
    )
    assert provider_capabilities == {
        "adapter_id": "example.provider",
        "duration_control": "provider_setting",
        "max_reference_images_per_generation": 3,
        "notes": "Example capability map only. Real adapters must verify provider behaviour.",
        "provider": "example_provider",
        "supports_audio_references": False,
        "supports_batch_generation": False,
        "supports_download": True,
        "supports_image_references": True,
        "supports_keyframes": False,
        "supports_task_polling": True,
        "supports_text_to_video": True,
        "supports_video_references": False,
    }


def test_package_errors_for_multi_scene_without_scene_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    source = Path("examples/realistic.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "-o",
            str(out_path),
        ],
    )

    assert cli.main() == 1
    captured = capsys.readouterr()
    assert "v1 supports one scene; pass --scene to select" in captured.out


def test_package_errors_for_unsupported_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "invalid.provider",
            "-o",
            str(out_path),
        ],
    )

    assert cli.main() == 1
    captured = capsys.readouterr()
    assert "Unsupported provider: invalid.provider." in captured.out


def test_package_duration_override_applies_to_all_shots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--duration-s",
            "7",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    shot_rows = _csv_rows(contents["DEVELOPER_FILES/shot_list.csv"])
    assert shot_rows
    assert all(row["duration_hint"] == "7s" for row in shot_rows)


def test_dialogue_heavy_scene_uses_varied_end_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    shot_rows = _csv_rows(contents["DEVELOPER_FILES/shot_list.csv"])
    assert len(shot_rows) >= 8
    final_three = shot_rows[-3:]
    final_descriptions = [row["description"] for row in final_three]
    assert len(set(final_descriptions)) == len(final_descriptions)
    assert any("Reaction on" in description for description in final_descriptions)
    assert any("Two-shot coverage" in description for description in final_descriptions)
    assert final_three[0]["characters"] == "Alice"
    assert final_three[1]["characters"] == "Bob"
    assert final_three[2]["characters"] == "Alice;Bob"


def test_package_output_directory_auto_names_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_dir = tmp_path / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "--project",
            "pilot",
            "-o",
            str(out_dir),
        ],
    )
    assert cli.main() == 0
    outputs = sorted(out_dir.glob("*.zip"))
    assert len(outputs) == 1
    assert outputs[0].name.startswith("pilot_scene_001_runway_gen4_image_refs_renderpackage_v1")
    contents = _zip_contents(outputs[0])
    assert set(contents.keys()) == set(_required_paths(include_runway_prompts=True))


def test_package_output_directory_auto_names_zip_for_universal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_dir = tmp_path / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--project",
            "pilot",
            "-o",
            str(out_dir),
        ],
    )
    assert cli.main() == 0
    outputs = sorted(out_dir.glob("*.zip"))
    assert len(outputs) == 1
    assert outputs[0].name.startswith("pilot_scene_001_universal_renderpackage_v1")


def test_package_add_pack_grok_generates_grok_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "universal",
            "--add-pack",
            "grok.imagine",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    assert set(contents.keys()) == set(_required_paths(include_grok_prompts=True))
    assert "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md" in contents
    grok_prompt_text = contents["DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md"].decode("utf-8")
    assert "# Grok Imagine Prompts" in grok_prompt_text
    assert (
        "Grok Imagine video workflows typically start from a reference image. "
        "For best results, attach at least a style or character reference image before generating."
    ) in grok_prompt_text
    assert "How to apply refs:" in grok_prompt_text
    package_map = contents["DEVELOPER_FILES/package_map.md"].decode("utf-8")
    assert "Grok Imagine" in package_map
    assert "`DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md`" in package_map
    rpack = json.loads(contents["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    assert rpack["selected_providers"] == ["universal", "grok.imagine"]


def test_package_runway_provider_generates_runway_prompt_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    assert "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md" in contents
    assert "DEVELOPER_FILES/prompt_packs/shot_prompts.md" in contents
    assert "prompts/asset_prompts.md" not in contents
    runway_prompt_text = contents["DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md"].decode("utf-8")
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in runway_prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in runway_prompt_text
    rpack = json.loads(contents["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    provenance = json.loads(contents["DEVELOPER_FILES/provenance.json"].decode("utf-8"))
    assert rpack["target_provider"] == "runway.gen4_image_refs"
    assert rpack["debug"]["creator_guide"]["renderer_used"] == "html"
    assert runway_prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])
    runway_pdf_text = _pdf_text(contents["RENDERPACKAGE.pdf"])
    normalized_runway_pdf_text = _normalize_ws(runway_pdf_text)
    if _has_pypdf():
        assert "Shot Cards / Storyboard" in normalized_runway_pdf_text
        assert "Keeper Workflow" in normalized_runway_pdf_text
    assert provenance["creator_guide"]["engine"] == "playwright"


def test_package_golden_expected_paths_universal_scene_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/realistic.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--scene",
            "1",
            "--provider",
            "universal",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    expected_paths = {
        line.strip()
        for line in Path("tests/expected_package_paths.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    with ZipFile(out_path, "r") as zf:
        assert set(zf.namelist()) == expected_paths
        unpack_dir = tmp_path / "unpacked"
        zf.extractall(unpack_dir)
    assert (unpack_dir / "RENDERPACKAGE.pdf").stat().st_size > 0
    assert (unpack_dir / "realistic.fountain").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert (unpack_dir / "COPY_PASTE_PROMPTS.docx").stat().st_size > 0
    assert (unpack_dir / "KEEPER_SHEET.csv").read_text(encoding="utf-8").startswith("shot_id,keeper_take,usable,notes")
    assert (unpack_dir / "DEVELOPER_FILES/package_map.md").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "DEVELOPER_FILES/prompt_packs/shot_prompts.md").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md").read_text(
        encoding="utf-8"
    ).strip()
    assert (unpack_dir / "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md").read_text(encoding="utf-8").strip()
