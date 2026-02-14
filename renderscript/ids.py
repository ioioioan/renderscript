from __future__ import annotations

import hashlib


def _stable_hex(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def doc_id_from_text(text: str) -> str:
    return f"doc_{_stable_hex(text)}"


def location_id(name: str) -> str:
    return f"loc_{_stable_hex(name.lower())}"


def scene_id(ordinal: int, heading_raw: str) -> str:
    return f"scn_{_stable_hex(f'{ordinal}:{heading_raw.strip()}')}"


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
