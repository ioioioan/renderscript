from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from renderscript.compiler import compile_fountain_text
from renderscript.providers import (
    DEFAULT_PROVIDER,
    PROVIDER_REGISTRY,
    SUPPORTED_PROVIDERS,
    optional_provider_adapters,
)
from renderscript.renderpackage import package_fountain_file


MAX_UPLOAD_BYTES = 1_000_000
ALLOWED_SUFFIXES = {".fountain", ".fnt"}
DEFAULT_PROJECT = "project"
APP_DIR = Path(__file__).resolve().parent
STYLES_PATH = APP_DIR / "static" / "styles.css"
BRANDING_DIR = Path(__file__).resolve().parent.parent / "renderscript" / "assets" / "branding"
ASSETS_DIR = Path(__file__).resolve().parent.parent / "renderscript" / "assets"
BRANDING_UI_LOGO_PATH = BRANDING_DIR / "renderscript_logo_horizontal_mark_left_text_right_pad5_v3.png"
BRANDING_MARK_LOGO_PATH = BRANDING_DIR / "renderscript_logo_mark_blue_pad5.png"
EXAMPLE_PACKAGE_PATH = ASSETS_DIR / "Example_scene_1_universal_renderpackage_v1.zip"

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
    if message.startswith("Content appears before first scene heading:"):
        return "Unsupported file type. Upload a .fountain or .fnt screenplay file."
    return message


def _read_logo_png(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError("Logo file not found.")
    return path.read_bytes()


def _read_asset_file(path: Path) -> bytes:
    if not path.exists():
        raise FileNotFoundError(f"Asset file not found: {path.name}")
    return path.read_bytes()


def _render_index(
    request: Request,
    *,
    error: str = "",
    provider: str = DEFAULT_PROVIDER,
    project: str = DEFAULT_PROJECT,
    scene: int = 1,
    scene_options: list[dict[str, str]] | None = None,
) -> Any:
    version_paths = [p for p in (BRANDING_UI_LOGO_PATH, BRANDING_MARK_LOGO_PATH) if p.exists()]
    logo_version = "0"
    if version_paths:
        logo_version = str(max(p.stat().st_mtime_ns for p in version_paths))
    options = scene_options or []
    styles_version = str(STYLES_PATH.stat().st_mtime_ns) if STYLES_PATH.exists() else "0"
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "error": error,
            "provider": provider,
            "project": project,
            "scene": scene,
            "logo_version": logo_version,
            "scene_options": options,
            "show_scene_dropdown": len(options) > 1,
            "providers": optional_provider_adapters(),
            "provider_registry": PROVIDER_REGISTRY,
            "styles_version": styles_version,
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
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Unsupported file type. Upload a .fountain or .fnt screenplay file.")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Could not decode upload as UTF-8 text.") from exc


@app.get("/")
async def index(request: Request) -> Any:
    return _render_index(request)


@app.get("/brand/logo.png")
async def brand_logo() -> Response:
    logo_bytes = await run_in_threadpool(_read_logo_png, BRANDING_UI_LOGO_PATH)
    etag = hashlib.sha256(logo_bytes).hexdigest()
    return Response(
        content=logo_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "ETag": etag},
    )


@app.get("/brand/favicon.png")
async def brand_favicon() -> Response:
    favicon_bytes = await run_in_threadpool(_read_logo_png, BRANDING_MARK_LOGO_PATH)
    etag = hashlib.sha256(favicon_bytes).hexdigest()
    return Response(
        content=favicon_bytes,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0", "ETag": etag},
    )


@app.get("/example-renderpackage.zip")
async def example_renderpackage() -> Response:
    package_bytes = await run_in_threadpool(_read_asset_file, EXAMPLE_PACKAGE_PATH)
    return Response(
        content=package_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{EXAMPLE_PACKAGE_PATH.name}"',
            "Cache-Control": "no-store, max-age=0",
        },
    )


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
    include_provider_prompts: list[str] = Form(default=[]),
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

            await run_in_threadpool(
                package_fountain_file,
                input_path=source_path,
                output_path=output_path,
                provider=provider_value,
                include_provider_prompts=include_provider_prompts,
                scene_ordinal=scene,
                project=project_safe,
            )
            zip_bytes = output_path.read_bytes()
            with ZipFile(BytesIO(zip_bytes), "r") as zf:
                renderer_used = ""
                if "dev/provenance.json" in zf.namelist():
                    provenance = json.loads(zf.read("dev/provenance.json").decode("utf-8", errors="replace"))
                    creator_guide = provenance.get("creator_guide", {}) if isinstance(provenance, dict) else {}
                    if isinstance(creator_guide, dict):
                        renderer_used = str(creator_guide.get("renderer_used", ""))
                elif "debug/creator_guide_debug.txt" in zf.namelist():
                    debug_text = zf.read("debug/creator_guide_debug.txt").decode("utf-8", errors="replace")
                    if "renderer_used=fallback" in debug_text:
                        renderer_used = "fallback"
            if renderer_used == "fallback":
                raise ValueError("Creator Guide PDF failed to generate via HTML renderer. Check Playwright/Chromium.")

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
