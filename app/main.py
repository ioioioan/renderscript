from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from renderscript.compiler import compile_fountain_text
from renderscript.renderpackage import SUPPORTED_PROVIDERS, package_fountain_file


MAX_UPLOAD_BYTES = 1_000_000
ALLOWED_SUFFIXES = {".fountain", ".fnt"}
DEFAULT_PROVIDER = "universal"
DEFAULT_PROJECT = "project"
APP_DIR = Path(__file__).resolve().parent

app = FastAPI(title="RenderScript Studio UI")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def _safe_project_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return safe or DEFAULT_PROJECT


def _scene_options_from_text(text: str, source_name: str = "upload.fountain") -> list[dict[str, str]]:
    doc = compile_fountain_text(text, source_name=source_name)
    scenes = doc.get("scenes", [])
    if not isinstance(scenes, list):
        return []
    options: list[dict[str, str]] = []
    for i, scene in enumerate(scenes, start=1):
        heading_raw = ""
        if isinstance(scene, dict):
            heading = scene.get("heading")
            if isinstance(heading, dict):
                heading_raw = str(heading.get("raw", ""))
        options.append({"ordinal": str(i), "label": heading_raw})
    return options


def _friendly_error_message(message: str) -> str:
    if "v1 supports one scene; pass --scene to select" in message:
        return "v1 supports one scene: choose a scene ordinal"
    return message


def _render_index(
    request: Request,
    *,
    error: str = "",
    provider: str = DEFAULT_PROVIDER,
    project: str = DEFAULT_PROJECT,
    scene: int = 1,
    scene_options: list[dict[str, str]] | None = None,
) -> Any:
    options = scene_options or []
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "error": error,
            "provider": provider,
            "project": project,
            "scene": scene,
            "scene_options": options,
            "show_scene_dropdown": len(options) > 1,
            "providers": list(SUPPORTED_PROVIDERS),
        },
        status_code=400 if error else 200,
    )


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload too large (max 1MB).")
    return data


def _validate_upload_type(upload: UploadFile, data: bytes) -> str:
    filename = upload.filename or "upload.fountain"
    suffix = Path(filename).suffix.lower()
    text_content_type = (upload.content_type or "").startswith("text/")
    if suffix not in ALLOWED_SUFFIXES and not text_content_type and suffix != "":
        raise ValueError("Unsupported file type. Use .fountain, .fnt, or plain text.")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Could not decode upload as UTF-8 text.") from exc


@app.get("/")
async def index(request: Request) -> Any:
    return _render_index(request)


@app.post("/scenes")
async def scenes(screenplay_file: UploadFile = File(...)) -> JSONResponse:
    try:
        data = await _read_upload(screenplay_file)
        text = _validate_upload_type(screenplay_file, data)
        options = _scene_options_from_text(text, source_name=screenplay_file.filename or "upload.fountain")
        if not options:
            raise ValueError("No scenes found in screenplay.")
        payload = {
            "scene_count": len(options),
            "default_scene": 1,
            "options": options,
        }
        return JSONResponse(payload)
    except Exception as exc:
        return JSONResponse({"error": _friendly_error_message(str(exc))}, status_code=400)


@app.post("/build")
async def build(
    request: Request,
    screenplay_file: UploadFile = File(...),
    provider: str = Form(DEFAULT_PROVIDER),
    scene: int = Form(1),
    project: str = Form(DEFAULT_PROJECT),
) -> Any:
    project_safe = _safe_project_name(project)
    provider_value = provider.strip() if provider else DEFAULT_PROVIDER
    try:
        if provider_value not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider: {provider_value}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
            )

        data = await _read_upload(screenplay_file)
        text = _validate_upload_type(screenplay_file, data)
        scene_options = _scene_options_from_text(text, source_name=screenplay_file.filename or "upload.fountain")
        if not scene_options:
            raise ValueError("No scenes found in screenplay.")
        if len(scene_options) == 1:
            scene = 1
        elif scene < 1 or scene > len(scene_options):
            raise ValueError("v1 supports one scene: choose a scene ordinal")

        source_suffix = Path(screenplay_file.filename or "upload.fountain").suffix or ".fountain"
        with TemporaryDirectory(prefix="renderscript_ui_") as tmp:
            tmp_dir = Path(tmp)
            source_path = tmp_dir / f"upload{source_suffix}"
            source_path.write_text(text, encoding="utf-8")
            output_path = tmp_dir / "renderpackage.zip"

            package_fountain_file(
                input_path=source_path,
                output_path=output_path,
                provider=provider_value,
                scene_ordinal=scene,
                project=project_safe,
            )
            zip_bytes = output_path.read_bytes()

        filename = f"{project_safe}_scene_{scene}_{provider_value.replace('.', '_')}_renderpackage_v1.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        return _render_index(
            request,
            error=_friendly_error_message(str(exc)),
            provider=provider_value,
            project=project_safe,
            scene=scene,
        )
