from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from src.config import Settings, get_abs_path, setup_logger, shutdown_logger
from src.helpers import (
    kill_pid,
    register_cors,
    register_error_handlers,
    register_middleware,
)
from src.routers import transcription_router
from src.schema.transcription import HealthResponse
from src.services.transcriber import transcriber_service

logger = setup_logger(
    Settings.LOG_DIR / "app.log",
    name="whisper.main",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Whisper STT application...")
    try:
        await transcriber_service.ensure_model_loaded(Settings.DEFAULT_MODEL)
        logger.info(f"Preloaded default model: {Settings.DEFAULT_MODEL}")
    except Exception as e:
        logger.error(f"Failed to preload model {Settings.DEFAULT_MODEL}: {e}")

    yield

    logger.info("Shutting down Whisper STT application...")
    shutdown_logger()


app = FastAPI(
    title=Settings.PROJECT_NAME,
    version=Settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if not Settings.is_production else None,
    redoc_url=None,
)

register_cors(app, Settings)
register_middleware(app, logger, Settings)
register_error_handlers(app, logger)

app.mount("/static", StaticFiles(directory=get_abs_path("static")), name="static")

app.include_router(transcription_router)


@app.get("/", tags=["UI"])
async def root():
    return FileResponse(get_abs_path("static/index.html"))


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        project=Settings.PROJECT_NAME,
        environment=Settings.ENV,
        version=Settings.VERSION,
        loaded_model=transcriber_service.loaded_model_name,
        device=transcriber_service.device_name,
    )


if __name__ == "__main__":
    host = Settings.API_HOST
    api_port = Settings.API_PORT

    kill_pid(api_port)

    logger.info(f"Starting Whisper STT API on http://{host}:{api_port}")
    uvicorn.run(
        "main:app",
        host=host,
        port=api_port,
        reload=False,
    )
