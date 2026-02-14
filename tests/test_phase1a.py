from __future__ import annotations

import json

from renderscript.compiler import compile_file, compile_fountain_text
from renderscript.validate import validate_document, validate_file


def test_compile_and_validate_deterministic(tmp_path):
    src = tmp_path / "tiny.fountain"
    out1 = tmp_path / "one.rscript"
    out2 = tmp_path / "two.rscript"

    src.write_text(
        """Title: Tiny Test

INT. OFFICE - DAY
Alice enters.

EXT. STREET - NIGHT
She leaves.
""",
        encoding="utf-8",
    )

    compile_file(src, out1)
    ok, message = validate_file(out1)
    assert ok, message

    compile_file(src, out2)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")

    compiled = json.loads(out1.read_text(encoding="utf-8"))
    assert compiled["rscript_version"] == "0.1"
    assert compiled["meta"]["source"]["format"] == "fountain"
    assert len(compiled["scenes"]) == 2


def test_dialogue_attribution_two_characters():
    compiled = compile_fountain_text(
        """Title: Dialogue Attribution

INT. OFFICE - DAY
ALICE
We should move.
BOB
Now?
""",
        source_name="dialogue.fountain",
    )
    ok, message = validate_document(compiled)
    assert ok, message

    characters = compiled["entities"]["characters"]
    assert [c["id"] for c in characters] == ["char_001", "char_002"]
    assert [c["name"] for c in characters] == ["ALICE", "BOB"]

    beats = compiled["scenes"][0]["beats"]
    assert beats[0] == {"type": "dialogue", "speaker_id": "char_001", "text": "We should move."}
    assert beats[1] == {"type": "dialogue", "speaker_id": "char_002", "text": "Now?"}


def test_parenthetical_after_character_cue():
    compiled = compile_fountain_text(
        """Title: Parenthetical

INT. SAFE HOUSE - NIGHT
ALICE
(whispering)
Keep quiet.
""",
        source_name="parenthetical.fountain",
    )
    ok, message = validate_document(compiled)
    assert ok, message

    beats = compiled["scenes"][0]["beats"]
    assert beats[0] == {"type": "parenthetical", "speaker_id": "char_001", "text": "(whispering)"}
    assert beats[1] == {"type": "dialogue", "speaker_id": "char_001", "text": "Keep quiet."}


def test_transition_handling():
    compiled = compile_fountain_text(
        """Title: Transition

INT. OFFICE - DAY
Papers scatter.
CUT TO:

EXT. STREET - NIGHT
FADE OUT.
""",
        source_name="transition.fountain",
    )
    ok, message = validate_document(compiled)
    assert ok, message

    first_scene_beats = compiled["scenes"][0]["beats"]
    second_scene_beats = compiled["scenes"][1]["beats"]

    assert first_scene_beats[-1] == {"type": "transition", "text": "CUT TO:"}
    assert second_scene_beats[0] == {"type": "transition", "text": "FADE OUT."}
