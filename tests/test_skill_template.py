from __future__ import annotations

from pathlib import Path


SKILL_ROOT = Path("skills/renderscript-openclaw-handoff")


def test_package_handoff_skill_template_is_inspectable() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\n")
    assert "name: renderscript-openclaw-handoff" in skill
    assert "RenderPackage.zip or Project Bundle.zip" in skill
    assert "Do not download third-party skills" in skill
    assert "spend credits" in skill
    assert "optional RenderScript handoff skill for OpenClaw" in skill

    references = SKILL_ROOT / "references"
    assert (references / "safety.md").exists()
    assert (references / "handoff-template.md").exists()
    assert (references / "target-workflows.md").exists()
    assert not (SKILL_ROOT / "scripts").exists()


def test_package_handoff_skill_safety_boundary() -> None:
    safety = (SKILL_ROOT / "references" / "safety.md").read_text(encoding="utf-8")
    targets = (SKILL_ROOT / "references" / "target-workflows.md").read_text(encoding="utf-8")

    assert "upload assets without approval" in safety
    assert "submit generation jobs without approval" in safety
    assert "request or reveal credentials" in safety
    assert "optional OpenClaw skill is one example" in targets
    assert "Do not advertise support for any named agent, provider, or workflow" in targets
