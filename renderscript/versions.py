from __future__ import annotations

RENDERSCRIPT_STUDIO_VERSION = "0.1.0"
PROMPT_TUNER_VERSION = "0.1.0"
RENDERPACKAGE_SPEC_VERSION = "0.2.0"
RSCRIPT_SCHEMA_VERSION = "0.1.0"


def version_payload() -> dict[str, str]:
    return {
        "renderscriptStudio": RENDERSCRIPT_STUDIO_VERSION,
        "promptTuner": PROMPT_TUNER_VERSION,
        "renderPackageSpec": RENDERPACKAGE_SPEC_VERSION,
        "rscriptSchema": RSCRIPT_SCHEMA_VERSION,
    }
