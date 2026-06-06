from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from ..odysseus import schemas, service


router = APIRouter(prefix="/api/odysseus")


@router.get("/status")
async def status() -> dict:
    return await run_in_threadpool(service.odysseus_status)


async def _run_action(action: str, payload: schemas.AnalyzeRequest) -> dict:
    return await run_in_threadpool(
        service.analyze,
        payload.message,
        payload.upload_path,
        payload.model,
        payload.options,
        action,
    )


@router.post("/analyze")
async def analyze(payload: schemas.AnalyzeRequest) -> dict:
    return await _run_action("analyze", payload)


@router.post("/code")
async def code_action(payload: schemas.AnalyzeRequest) -> dict:
    return await _run_action("code", payload)


@router.post("/debug")
async def debug_action(payload: schemas.AnalyzeRequest) -> dict:
    return await _run_action("debug", payload)


@router.post("/plan")
async def plan_action(payload: schemas.AnalyzeRequest) -> dict:
    return await _run_action("plan", payload)


@router.post("/files/upload")
async def files_upload(request: Request, file: UploadFile = File(...)) -> dict:
    session_id = request.headers.get("x-session-id") or "guest"
    content = await file.read()
    result = await run_in_threadpool(service.save_uploaded, file.filename, content, session_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "Upload rechazado.")
    return result


@router.post("/files/inspect-zip")
async def files_inspect_zip(payload: schemas.ZipInspectRequest) -> dict:
    try:
        return await run_in_threadpool(service.inspect_zip, payload.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files")
@router.get("/files/list")
async def files(session_id: str | None = None) -> dict:
    return await run_in_threadpool(service.list_files, session_id)


@router.post("/files/search")
async def files_search(payload: schemas.FileSearchRequest) -> dict:
    return await run_in_threadpool(service.search_files, payload.query, payload.session_id, payload.max_results)


@router.post("/files/read")
async def files_read(payload: schemas.FileReadRequest) -> dict:
    try:
        return await run_in_threadpool(service.read_file, payload.path, payload.max_chars)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tools/run")
async def tools_run(payload: schemas.ToolRunRequest) -> dict:
    return await run_in_threadpool(service.run_tool, payload.tool, payload.args)
