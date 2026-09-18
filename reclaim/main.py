"""Retain the official API and add the Reclaim decision layer."""
from api.main import app
from .routes import router
from api.data_loader import store, snapshot_context
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool


@app.middleware("http")
async def pin_dataset(request, call_next):
    if request.url.path == "/api/reclaim/dataset/reload":
        return await call_next(request)
    try:
        snapshot = await run_in_threadpool(store)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return JSONResponse(status_code=422, content={"detail": "Dataset could not load: " + str(exc)})
    token = snapshot_context.set(snapshot)
    try:
        return await call_next(request)
    finally:
        snapshot_context.reset(token)

app.include_router(router)
