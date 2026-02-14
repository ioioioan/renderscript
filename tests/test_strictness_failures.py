from __future__ import annotations

from pathlib import Path

import pytest

from renderscript import cli
from renderscript.compiler import compile_fountain_text
from renderscript.fountain_parser import ParsedScene, ParsedToken


def test_dialogue_without_character_cue_raises():
    with pytest.raises(ValueError):
        compile_fountain_text(
            """Title: Invalid Dialogue

INT. OFFICE - DAY
  This should be dialogue but has no cue.
"""
        )


def test_parenthetical_without_character_cue_raises():
    with pytest.raises(ValueError):
        compile_fountain_text(
            """Title: Invalid Parenthetical

INT. OFFICE - DAY
(whispering)
Move now.
"""
        )


def test_content_before_first_scene_heading_raises():
    with pytest.raises(ValueError):
        compile_fountain_text(
            """Title: Invalid Prelude
This content appears too early.

INT. OFFICE - DAY
Action line.
"""
        )


def test_scene_with_zero_beats_raises():
    with pytest.raises(ValueError):
        compile_fountain_text(
            """Title: Empty Scene

INT. OFFICE - DAY

EXT. STREET - NIGHT
Action line.
"""
        )


def test_dialogue_or_parenthetical_missing_speaker_raises(monkeypatch: pytest.MonkeyPatch):
    def fake_parse_fountain(_: str):
        return (
            "Invalid Speaker",
            [
                ParsedScene(
                    raw_heading="INT. OFFICE - DAY",
                    int_ext="INT",
                    location_name="OFFICE",
                    time_of_day="DAY",
                    tokens=[ParsedToken(token_type="dialogue", text="Hello.", speaker=None)],
                )
            ],
        )

    monkeypatch.setattr("renderscript.compiler.parse_fountain", fake_parse_fountain)
    with pytest.raises(ValueError):
        compile_fountain_text("INT. OFFICE - DAY\nALICE\nHello.\n")


def test_cli_compile_invalid_input_exits_non_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    src = tmp_path / "invalid.fountain"
    out = tmp_path / "invalid.rscript"
    src.write_text(
        """Title: Invalid CLI

INT. OFFICE - DAY
  Missing cue dialogue.
""",
        encoding="utf-8",
    )

    monkeypatch.setattr("sys.argv", ["renderscript", "compile", str(src), "-o", str(out)])
    assert cli.main() == 1
