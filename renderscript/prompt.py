from __future__ import annotations


def _character_lookup(doc: dict[str, object]) -> dict[str, str]:
    entities = doc.get("entities", {})
    if not isinstance(entities, dict):
        return {}
    raw_characters = entities.get("characters", [])
    if not isinstance(raw_characters, list):
        return {}
    mapping: dict[str, str] = {}
    for character in raw_characters:
        if not isinstance(character, dict):
            continue
        cid = character.get("id")
        name = character.get("name")
        if isinstance(cid, str) and isinstance(name, str):
            mapping[cid] = name
    return mapping


def _scene_character_names(scene: dict[str, object], id_to_name: dict[str, str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    presence = scene.get("presence", {})
    if isinstance(presence, dict):
        present_ids = presence.get("characters", [])
        if isinstance(present_ids, list):
            for cid in present_ids:
                if isinstance(cid, str) and cid in id_to_name:
                    name = id_to_name[cid]
                    if name not in seen:
                        seen.add(name)
                        names.append(name)

    if names:
        return names

    beats = scene.get("beats", [])
    if not isinstance(beats, list):
        return names
    for beat in beats:
        if not isinstance(beat, dict):
            continue
        cid = beat.get("speaker_id")
        if isinstance(cid, str) and cid in id_to_name:
            name = id_to_name[cid]
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _format_beat(beat: dict[str, object], id_to_name: dict[str, str]) -> str:
    beat_type = beat.get("type")
    text = beat.get("text")
    if not isinstance(beat_type, str) or not isinstance(text, str):
        raise ValueError("Invalid beat entry")

    if beat_type == "action":
        return f"Action: {text}"
    if beat_type == "transition":
        return f"Transition: {text}"

    if beat_type in {"dialogue", "parenthetical"}:
        speaker_id = beat.get("speaker_id")
        if not isinstance(speaker_id, str):
            raise ValueError(f"{beat_type} beat missing speaker_id")
        speaker_name = id_to_name.get(speaker_id)
        if speaker_name is None:
            raise ValueError(f"Unknown speaker_id: {speaker_id}")
        if beat_type == "dialogue":
            return f"{speaker_name}: {text}"
        return f"{speaker_name} {text}"

    raise ValueError(f"Unsupported beat type: {beat_type}")


def render_structured_sora_prompt(doc: dict[str, object]) -> str:
    id_to_name = _character_lookup(doc)
    raw_scenes = doc.get("scenes", [])
    if not isinstance(raw_scenes, list):
        raise ValueError("Document scenes must be a list")
    scenes = [scene for scene in raw_scenes if isinstance(scene, dict)]
    scenes.sort(key=lambda s: int(s.get("ordinal", 0)))

    lines = [
        "Create a short cinematic video that strictly follows the structured screenplay below.",
        "",
        "Constraints:",
        "- Follow the events in order scene-by-scene.",
        "",
        "- Do not invent new characters, locations, or props.",
        "",
        "- Only use the characters listed for each scene.",
        "",
        "- Keep the location consistent within each scene.",
        "",
        "- Include all dialogue lines exactly as written.",
        "",
        "- If something is unclear, keep it minimal rather than inventing.",
        "",
    ]

    for idx, scene in enumerate(scenes):
        ordinal = scene.get("ordinal")
        heading = scene.get("heading", {})
        heading_raw = ""
        if isinstance(heading, dict):
            raw = heading.get("raw")
            if isinstance(raw, str):
                heading_raw = raw

        character_names = _scene_character_names(scene, id_to_name)
        lines.append(f"Scene {ordinal}")
        lines.append(f"Location: {heading_raw}")
        lines.append(f"Characters present: {', '.join(character_names)}")
        lines.append("")

        beats = scene.get("beats", [])
        if not isinstance(beats, list):
            raise ValueError("Scene beats must be a list")
        for beat in beats:
            if not isinstance(beat, dict):
                raise ValueError("Invalid beat entry")
            lines.append(_format_beat(beat, id_to_name))

        if idx != len(scenes) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"


def render_natural_prompt(doc: dict[str, object]) -> str:
    id_to_name = _character_lookup(doc)
    raw_scenes = doc.get("scenes", [])
    if not isinstance(raw_scenes, list):
        raise ValueError("Document scenes must be a list")
    scenes = [scene for scene in raw_scenes if isinstance(scene, dict)]
    scenes.sort(key=lambda s: int(s.get("ordinal", 0)))

    lines = [
        "Create a short cinematic video that follows the screenplay faithfully.",
        "",
        "Constraints:",
        "- Follow events in order.",
        "- Do not invent new characters, locations, or props.",
        "- Keep characters consistent.",
        "- Keep each scene’s location consistent.",
        "- If dialogue cannot be spoken, render the exact lines as subtitles.",
        "",
    ]

    paragraphs: list[str] = []
    for scene in scenes:
        ordinal = scene.get("ordinal")
        heading = scene.get("heading", {})
        heading_raw = ""
        if isinstance(heading, dict):
            raw = heading.get("raw")
            if isinstance(raw, str):
                heading_raw = raw

        character_names = _scene_character_names(scene, id_to_name)

        beats = scene.get("beats", [])
        if not isinstance(beats, list):
            raise ValueError("Scene beats must be a list")

        action_texts: list[str] = []
        dialogue_lines: list[str] = []
        for beat in beats:
            if not isinstance(beat, dict):
                raise ValueError("Invalid beat entry")
            beat_type = beat.get("type")
            text = beat.get("text")
            if not isinstance(beat_type, str) or not isinstance(text, str):
                raise ValueError("Invalid beat entry")
            if beat_type == "action":
                action_texts.append(text)
            elif beat_type == "dialogue":
                speaker_id = beat.get("speaker_id")
                if not isinstance(speaker_id, str):
                    raise ValueError("dialogue beat missing speaker_id")
                speaker_name = id_to_name.get(speaker_id)
                if speaker_name is None:
                    raise ValueError(f"Unknown speaker_id: {speaker_id}")
                dialogue_lines.append(f'{speaker_name}: "{text}"')
            elif beat_type == "parenthetical":
                speaker_id = beat.get("speaker_id")
                if not isinstance(speaker_id, str):
                    raise ValueError("parenthetical beat missing speaker_id")
                speaker_name = id_to_name.get(speaker_id)
                if speaker_name is None:
                    raise ValueError(f"Unknown speaker_id: {speaker_id}")
                dialogue_lines.append(f"{speaker_name} {text}")

        action_summary = "; ".join(action_texts) if action_texts else "none"
        dialogue_summary = " | ".join(dialogue_lines) if dialogue_lines else "none"
        paragraph = (
            f"Scene {ordinal}. Location: {heading_raw}. Characters present: "
            f"{', '.join(character_names)}. Action summary: {action_summary}. "
            f"Dialogue lines: {dialogue_summary}."
        )
        paragraphs.append(paragraph)

    lines.append("\n\n".join(paragraphs))
    return "\n".join(lines) + "\n"


def render_prompt(doc: dict[str, object], mode: str) -> str:
    if mode == "structured":
        return render_structured_sora_prompt(doc)
    if mode == "natural":
        return render_natural_prompt(doc)
    raise ValueError("Unsupported mode. Only 'structured' and 'natural' are supported.")
