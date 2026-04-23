"""FastAPI application entry point with lifespan management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import APISettings
from core import AsyncRedisClient, get_logger, instrument_fastapi_app
from ingestion.supabase_client import create_supabase_client

load_dotenv()

logger = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage shared resources across the app lifetime."""
    settings: APISettings = app.state.settings
    app.state.supabase = await create_supabase_client(
        url=settings.supabase_url,
        key=settings.supabase_key.get_secret_value(),
    )

    if settings.cache_enabled:
        redis = AsyncRedisClient(
            url=settings.redis_url.get_secret_value(),
            key_prefix="aw:",
            default_ttl=settings.cache_ttl,
        )
        try:
            async with redis:
                app.state.redis_client = redis
                logger.info("api_started", app_name=settings.app_name, cache="enabled")
                yield
        except Exception:
            logger.warning("redis_unavailable", msg="falling back to no cache")
            app.state.redis_client = None
            logger.info("api_started", app_name=settings.app_name, cache="disabled")
            yield
    else:
        app.state.redis_client = None
        logger.info("api_started", app_name=settings.app_name, cache="disabled")
        yield

    logger.info("api_shutdown")


def create_app() -> FastAPI:
    """Application factory."""
    settings = APISettings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api.routes import router

    app.include_router(router)
    instrumented = instrument_fastapi_app(app, service_name="alpha-whale-api")
    logger.info(
        "fastapi_instrumentation",
        service_name="alpha-whale-api",
        instrumented=instrumented,
    )

    return app
