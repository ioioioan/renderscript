from __future__ import annotations

from pathlib import Path

from renderscript import cli


def _run_prompt(
    input_file: Path,
    mode: str,
    output_file: Path,
    monkeypatch,
) -> int:
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            mode,
            "-o",
            str(output_file),
        ],
    )
    return cli.main()


def test_realistic_structured_prompt_golden_and_deterministic(tmp_path: Path, monkeypatch):
    source = Path("examples/realistic.fountain")
    expected = Path("examples/expected/realistic.structured.txt")
    out1 = tmp_path / "realistic.structured.one.txt"
    out2 = tmp_path / "realistic.structured.two.txt"

    assert _run_prompt(source, "structured", out1, monkeypatch) == 0
    assert _run_prompt(source, "structured", out2, monkeypatch) == 0

    text1 = out1.read_text(encoding="utf-8")
    text2 = out2.read_text(encoding="utf-8")
    expected_text = expected.read_text(encoding="utf-8")

    assert text1 == text2
    assert text1 == expected_text


def test_realistic_natural_prompt_golden_and_deterministic(tmp_path: Path, monkeypatch):
    source = Path("examples/realistic.fountain")
    expected = Path("examples/expected/realistic.natural.txt")
    out1 = tmp_path / "realistic.natural.one.txt"
    out2 = tmp_path / "realistic.natural.two.txt"

    assert _run_prompt(source, "natural", out1, monkeypatch) == 0
    assert _run_prompt(source, "natural", out2, monkeypatch) == 0

    text1 = out1.read_text(encoding="utf-8")
    text2 = out2.read_text(encoding="utf-8")
    expected_text = expected.read_text(encoding="utf-8")

    assert text1 == text2
    assert text1 == expected_text
