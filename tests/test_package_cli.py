from __future__ import annotations

import json
import re
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from renderscript import cli
from renderscript.providers import (
    GROK_PROVIDER,
    PROVIDER_REGISTRY,
    get_execution_template,
    optional_execution_templates,
)
from renderscript.renderpackage import package_fountain_file
from renderscript.validate import validate_package


BASE_REQUIRED_PATHS = [
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
    "DEVELOPER_FILES/action_plan.json",
    "DEVELOPER_FILES/execution_contract.json",
    "DEVELOPER_FILES/approval_checkpoints.json",
    "DEVELOPER_FILES/take_log.csv",
    "DEVELOPER_FILES/keeper_decisions.csv",
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
    character_note_paths: list[str] | None = None,
    voice_ref_paths: list[str] | None = None,
    include_runway_prompts: bool = False,
    include_grok_prompts: bool = False,
) -> list[str]:
    refs = reference_paths or [
        "refs/01_style_reference/",
        "refs/02_location_reference/",
        "refs/03_character_reference_alice/",
        "refs/04_character_reference_bob/",
        "refs/05_lighting_reference_night_lighting/",
    ]
    character_notes = character_note_paths or [
        "assets/refs/characters/alice_character_reference.md",
        "assets/refs/characters/bob_character_reference.md",
    ]
    voice_refs = voice_ref_paths or [
        "audio/character_voice_refs/alice_voice_reference.md",
        "audio/character_voice_refs/bob_voice_reference.md",
    ]
    return [
        "RENDERPACKAGE.pdf",
        "COPY_PASTE_PROMPTS.docx",
        "KEEPER_SHEET.csv",
        source_filename,
        *refs,
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
        *character_notes,
        "audio/",
        "audio/voice_bible.md",
        "audio/character_voice_refs/",
        *voice_refs,
        "audio/voice_samples/",
        "generated_shots/takes/",
        "generated_shots/keepers/",
        *BASE_REQUIRED_PATHS[BASE_REQUIRED_PATHS.index("DEVELOPER_FILES/") :],
    ]


def test_execution_template_registry_includes_grok_imagine() -> None:
    grok = PROVIDER_REGISTRY[GROK_PROVIDER]
    assert grok.id == "grok.imagine"
    assert grok.label == "Grok Imagine"
    assert grok.prompt_filename == "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md"
    assert grok.supported is True
    assert grok.requires_reference_image is True
    assert get_execution_template(GROK_PROVIDER) == grok
    assert GROK_PROVIDER in {template.id for template in optional_execution_templates()}


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
    assert rpack["execution_profile"] == "universal"
    assert rpack["selected_execution_profiles"] == ["universal"]
    assert rpack["generator"]["name"] == "RenderScript AI"
    assert "version" in rpack["generator"]
    assert isinstance(rpack["generated_at"], str)
    assert rpack["generated_at"].endswith("Z")
    assert rpack["references"]["characters"]
    assert rpack["references"]["lighting"][0]["approval_status"] == "pending_creator_approval"
    assert rpack["references"]["characters"][0]["continuity_anchor"] is False
    assert rpack["voice_references"]["characters"]
    assert rpack["voice_references"]["characters"][0]["approval_status"] == "pending_creator_approval"
    assert rpack["asset_sources"] == {"uploaded_images": [], "uploaded_voice_samples": []}
    assert rpack["approval_status"]["prompts_approved"] is False
    assert rpack["approval_status"]["approved_shot_count"] == 0
    assert rpack["approval_status"]["total_shot_count"] == len(rpack["shots"])
    assert rpack["approval_status"]["references_approved"] is False
    assert rpack["approval_status"]["voice_refs_approved"] is False
    assert rpack["continuity_anchors"] == {"visual_references": [], "voice_references": []}
    assert 8 <= len(rpack["shots"]) <= 12
    assert rpack["shots"][0]["approval_required"] is True
    assert rpack["shots"][0]["approved"] is False
    assert rpack["shots"][0]["approval_status"] == "pending_creator_approval"
    assert rpack["debug"]["creator_guide"]["renderer_used"] == "html"
    assert isinstance(rpack["debug"]["creator_guide"]["error"], str)
    agent_contract = rpack["agent_orchestration"]
    assert agent_contract["source_of_truth"] == "DEVELOPER_FILES/rpack.json"
    assert agent_contract["agent_contract"] == "DEVELOPER_FILES/AGENT_ORCHESTRATION.md"
    assert agent_contract["provider_capabilities_example"] == "DEVELOPER_FILES/provider_capabilities.example.json"
    assert agent_contract["action_plan_path"] == "DEVELOPER_FILES/action_plan.json"
    assert agent_contract["execution_contract_path"] == "DEVELOPER_FILES/execution_contract.json"
    assert agent_contract["approval_checkpoints_path"] == "DEVELOPER_FILES/approval_checkpoints.json"
    assert agent_contract["take_log_path"] == "DEVELOPER_FILES/take_log.csv"
    assert agent_contract["keeper_decisions_path"] == "DEVELOPER_FILES/keeper_decisions.csv"
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
    rpack_shot_ids = {shot["shot_id"] for shot in rpack["shots"]}
    assert {row["shot_id"] for row in shot_rows} == rpack_shot_ids
    assert {row["shot_id"] for row in bindings_rows} == rpack_shot_ids
    rubric_ids = {row["shot_id"] for row in rubric_rows}
    for row in bindings_rows:
        assert row["location_refs"] == "loc_01_ref_01"
        assert row["style_refs"] == "style_01_ref_01"
        if row["shot_id"] in shot_beats and ": " in shot_beats[row["shot_id"]]:
            assert row["character_refs"], f"dialogue shot missing character refs: {row['shot_id']}"
    assert rubric_ids == {shot["shot_id"] for shot in rpack["shots"]}

    for prompt_path in [
        "DEVELOPER_FILES/prompt_packs/shot_prompts.md",
        "DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md",
        "DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md",
    ]:
        pack_text = contents_one[prompt_path].decode("utf-8")
        for shot_id in rpack_shot_ids:
            assert shot_id in pack_text
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
    assert "prompts/reference_prompts.md" in package_map
    assert "audio/voice_bible.md" in package_map
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
    allowed_root_markdown = {
        "prompts/reference_prompts.md",
        "assets/refs/characters/alice_character_reference.md",
        "assets/refs/characters/bob_character_reference.md",
        "audio/voice_bible.md",
        "audio/character_voice_refs/alice_voice_reference.md",
        "audio/character_voice_refs/bob_voice_reference.md",
    }
    assert not any(
        name.endswith(".md")
        and not name.startswith("DEVELOPER_FILES/")
        and name not in allowed_root_markdown
        for name in contents_one
    )
    agent_orchestration = contents_one["DEVELOPER_FILES/AGENT_ORCHESTRATION.md"].decode("utf-8")
    assert "# Agent Orchestration" in agent_orchestration
    assert "An agent should not recreate the package." in agent_orchestration
    assert "RenderPackage is agent-actionable, not auto-executable" in agent_orchestration
    assert "Submit generation jobs only when the user has configured external access" in agent_orchestration
    assert "not runnable workflow code" in agent_orchestration
    assert "run this package" not in agent_orchestration.lower()
    assert "generated_shots/takes/" in agent_orchestration
    assert "generated_shots/keepers/" in agent_orchestration
    assert "Do not place generated media inside DEVELOPER_FILES." in agent_orchestration
    assert "Use approved references only as continuity anchors." in agent_orchestration
    assert "Treat Voice Bible entries as speech-performance continuity anchors only after creator approval." in agent_orchestration
    reference_prompts = contents_one["prompts/reference_prompts.md"].decode("utf-8")
    assert "# Reference Prompts" in reference_prompts
    assert "nothing becomes a continuity anchor until the creator approves it" in reference_prompts
    assert "CHARACTER REFERENCE SHEET" in reference_prompts
    voice_bible = contents_one["audio/voice_bible.md"].decode("utf-8")
    assert "# Voice Bible" in voice_bible
    assert "Voice continuity rule" in voice_bible
    provider_capabilities = json.loads(
        contents_one["DEVELOPER_FILES/provider_capabilities.example.json"].decode("utf-8")
    )
    assert provider_capabilities == {
        "adapter_id": "example.provider",
        "duration_control": "provider_setting",
        "execution_template_id": "example.provider",
        "max_reference_images_per_generation": 3,
        "notes": "Example capability hint only. Real execution templates must verify workflow behaviour.",
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
    action_plan = json.loads(contents_one["DEVELOPER_FILES/action_plan.json"].decode("utf-8"))
    assert action_plan["non_executable"] is True
    assert action_plan["canonical_prompt_pack"] == "DEVELOPER_FILES/prompt_packs/shot_prompts.md"
    assert {step["step"] for step in action_plan["steps"]} >= {"approve_prompts", "approve_references", "generate_takes", "select_keepers"}
    execution_contract = json.loads(contents_one["DEVELOPER_FILES/execution_contract.json"].decode("utf-8"))
    assert execution_contract["non_executable"] is True
    assert execution_contract["renderpackage_is"] == "agent-actionable, not auto-executable"
    approval_checkpoints = json.loads(contents_one["DEVELOPER_FILES/approval_checkpoints.json"].decode("utf-8"))
    assert {item["id"] for item in approval_checkpoints["checkpoints"]} == {
        "prompt_approval",
        "reference_approval",
        "take_review",
        "keeper_selection",
        "revision_decisions",
    }
    assert contents_one["DEVELOPER_FILES/take_log.csv"].decode("utf-8").startswith("shot_id,take_id,filename")
    assert contents_one["DEVELOPER_FILES/keeper_decisions.csv"].decode("utf-8").startswith("shot_id,keeper_take,filename")
    executable_suffixes = (".py", ".sh", ".bat", ".exe", ".command", ".ps1")
    assert not any(path.endswith(executable_suffixes) for path in contents_one)
    ok, message = validate_package(out_one)
    assert ok, message


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
    assert "Example execution template only" in grok_prompt_text
    assert "not the RenderScript product target" in grok_prompt_text
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
    assert rpack["execution_profile"] == "runway.gen4_image_refs"
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


def test_package_uses_prompt_tuner_edits_in_exports(tmp_path: Path):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "edited.zip"
    edited_reference = "Edited style reference prompt with clean practical lighting and no text."
    edited_shot = (
        "Edited shot prompt for Alice holding the permit form in the server room. "
        "No subtitles, captions, logos, watermarks, or on-screen text."
    )

    package_fountain_file(
        input_path=source,
        output_path=out_path,
        prompt_edits={
            "reference_prompts": {"refs/01_style_reference/": edited_reference},
            "shot_prompts": {"shot_001": edited_shot},
            "reference_approvals": {"refs/01_style_reference/": True},
            "shot_approvals": {"shot_001": True},
            "voice_approvals": {"alice": True},
            "voice_bible": {
                "alice": {
                    "accent": "soft Cardiff",
                    "pace": "quick but controlled",
                    "tone": "dry and practical",
                }
            },
            "continuity": {
                "refs/01_style_reference/": {
                    "locked_visual_anchors": "cool practical light\nserver LEDs",
                    "avoid_rules": "no warm cosy office look",
                }
            },
            "prompt_assist": {
                "prompt_assist_used": True,
                "reference_prompts_improved": True,
                "shot_prompts_anchored": True,
                "provider": "azure_openai",
                "deployment": "rs-prompt-assist",
            },
        },
    )

    contents = _zip_contents(out_path)
    rpack = json.loads(contents["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    provenance = json.loads(contents["DEVELOPER_FILES/provenance.json"].decode("utf-8"))
    prompt_text = contents["DEVELOPER_FILES/prompt_packs/shot_prompts.md"].decode("utf-8")
    copy_doc = _docx_text(contents["COPY_PASTE_PROMPTS.docx"])

    assert rpack["renderscript_studio_version"] == "0.1.0"
    assert rpack["prompt_tuner_version"] == "0.1.0"
    assert rpack["renderpackage_spec_version"] == "0.2.0"
    assert rpack["rscript_schema_version"] == "0.1.0"
    assert rpack["prompt_tuner"]["edited"] is True
    assert rpack["prompt_tuner"]["edited_reference_prompts"] == ["refs/01_style_reference/"]
    assert rpack["prompt_tuner"]["edited_shot_prompts"] == ["shot_001"]
    assert rpack["prompt_tuner"]["prompt_assist_used"] is True
    assert rpack["prompt_tuner"]["reference_prompts_improved"] is True
    assert rpack["prompt_tuner"]["shot_prompts_anchored"] is True
    assert rpack["prompt_tuner"]["provider"] == "azure_openai"
    assert rpack["prompt_tuner"]["deployment"] == "rs-prompt-assist"
    assert rpack["prompt_tuner"]["approved_reference_prompts"] == ["refs/01_style_reference/"]
    assert rpack["prompt_tuner"]["approved_shot_prompts"] == ["shot_001"]
    assert rpack["prompt_tuner"]["approved_voice_references"] == ["alice"]
    assert provenance["prompt_tuner"]["edited"] is True
    assert provenance["prompt_tuner"]["prompt_assist_used"] is True
    assert provenance["versions"]["renderpackage_spec_version"] == "0.2.0"
    assert rpack["agent_orchestration"]["reference_folders"][0]["base_prompt"] == edited_reference
    assert rpack["agent_orchestration"]["reference_folders"][0]["approved"] is True
    assert rpack["agent_orchestration"]["reference_folders"][0]["continuity_anchor"] is True
    assert rpack["agent_orchestration"]["reference_folders"][0]["locked_visual_anchors"] == [
        "cool practical light",
        "server LEDs",
    ]
    assert rpack["agent_orchestration"]["reference_folders"][0]["avoid_rules"] == ["no warm cosy office look"]
    assert rpack["references"]["style"][0]["approved"] is True
    assert rpack["continuity_anchors"]["visual_references"][0]["path"] == "refs/01_style_reference/"
    alice_voice = next(item for item in rpack["voice_references"]["characters"] if item["character_id"] == "alice")
    assert alice_voice["approved"] is True
    assert alice_voice["accent"] == "soft Cardiff"
    assert rpack["continuity_anchors"]["voice_references"][0]["character_id"] == "alice"
    assert rpack["agent_orchestration"]["shots"][0]["base_prompt"] == edited_shot
    assert rpack["agent_orchestration"]["shots"][0]["approved"] is True
    assert rpack["agent_orchestration"]["shots"][0]["approval_status"] == "approved"
    assert rpack["shots"][0]["approved"] is True
    assert edited_shot in prompt_text
    assert edited_shot in contents["DEVELOPER_FILES/prompt_packs/runway.gen4_image_refs_prompts.md"].decode("utf-8")
    assert edited_shot in contents["DEVELOPER_FILES/prompt_packs/grok.imagine_prompts.md"].decode("utf-8")
    assert edited_reference in copy_doc
    assert edited_shot in copy_doc


def test_package_exports_user_reference_assets_into_matching_refs_folder(tmp_path: Path):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "reference_assets.zip"

    package_fountain_file(
        input_path=source,
        output_path=out_path,
        reference_assets=[
            {
                "reference_path": "refs/01_style_reference/",
                "filename": "approved style.png",
                "content": b"fake image bytes",
            }
        ],
    )

    contents = _zip_contents(out_path)
    rpack = json.loads(contents["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    asset_path = "refs/01_style_reference/approved_style.png"

    assert contents[asset_path] == b"fake image bytes"
    assert rpack["prompt_tuner"]["reference_assets_attached"] is True
    assert rpack["prompt_tuner"]["attached_reference_files"] == [asset_path]
    assert rpack["asset_sources"]["uploaded_images"] == [
        {
            "filename": "approved_style.png",
            "path": asset_path,
            "source": "user_upload",
        }
    ]
    assert rpack["agent_orchestration"]["reference_folders"][0]["attached_reference_files"] == [
        {
            "filename": "approved_style.png",
            "path": asset_path,
            "source": "user_upload",
        }
    ]


def test_package_exports_user_voice_assets_into_audio_folder(tmp_path: Path):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "voice_assets.zip"

    package_fountain_file(
        input_path=source,
        output_path=out_path,
        voice_assets=[
            {
                "character_id": "alice",
                "filename": "sample 01.wav",
                "content": b"fake voice bytes",
            }
        ],
    )

    contents = _zip_contents(out_path)
    rpack = json.loads(contents["DEVELOPER_FILES/rpack.json"].decode("utf-8"))
    asset_path = "audio/voice_samples/alice_sample_01.wav"

    assert contents[asset_path] == b"fake voice bytes"
    assert rpack["prompt_tuner"]["voice_assets_attached"] is True
    assert rpack["prompt_tuner"]["attached_voice_files"] == [asset_path]
    assert rpack["asset_sources"]["uploaded_voice_samples"] == [
        {
            "filename": "alice_sample_01.wav",
            "path": asset_path,
            "character_id": "alice",
            "character_name": "Alice",
            "source": "user_upload",
        }
    ]
