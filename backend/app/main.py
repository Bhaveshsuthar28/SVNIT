import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.analytics import router as analytics_router
from app.api.health import router as health_router
from app.api.metadata import router as metadata_router
from app.api.summary import router as summary_router
from app.api.trajectories import router as trajectories_router
from app.api.websocket import router as websocket_router
from app.config import get_settings
from app.database import SessionLocal
from app.services.playback_service import playback_cache
from app.services.trajectory_service import load_all_records_for_cache

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def load_playback_cache() -> None:
    db: Session = SessionLocal()
    try:
        records = load_all_records_for_cache(db)
        playback_cache.load(records)
        logger.info("Database connection established and playback cache initialized.")
    except Exception:
        logger.exception("Could not load playback cache from PostgreSQL")
        playback_cache.clear()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    logger.info("Starting Traffic Analytics backend")
    load_playback_cache()
    yield
    logger.info("Shutting down Traffic Analytics backend")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="SVNIT Traffic Analytics Dashboard",
        description=(
            "Backend for the SVNIT Surat traffic analytics assignment. "
            "Serves the recorded trajectories67.csv dataset through REST APIs "
            "and a real-time-style trajectory replay WebSocket. "
            "This is not a live CCTV feed."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, __: SQLAlchemyError) -> JSONResponse:
        """Keep database failures from leaking driver details through the API."""
        logger.exception("Database request failed")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable or not initialized."},
        )

    application.include_router(health_router, prefix="/api")
    application.include_router(metadata_router, prefix="/api")
    application.include_router(summary_router, prefix="/api")
    application.include_router(analytics_router, prefix="/api")
    application.include_router(trajectories_router, prefix="/api")
    application.include_router(websocket_router)

    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    application.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    return application


app = create_app()
