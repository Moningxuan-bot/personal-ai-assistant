import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.logging_config import setup_logging
from app.routes import chat, health, goals, spendings, memes


# ---- 日志初始化（必须最先，确保所有模块的 logger 都生效）----
setup_logging()
logger = logging.getLogger("ajiur.lifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection + auto-create tables
    try:
        from app.models.database import engine, Base
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB connection verified + tables created")
    except ImportError:
        logger.info("DB not configured, skipping (import error)")
    except Exception:
        logger.warning("DB startup check failed", exc_info=True)

    # Preload embedding model so first request doesn't block on download
    try:
        from app.providers.embedding import embed_provider
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, embed_provider._load_model)
        logger.info("Embedding model preloaded")
    except Exception:
        logger.warning("Embedding preload failed, chat still works without it", exc_info=True)

    yield
    # Shutdown
    try:
        from app.models.database import engine
        await engine.dispose()
        logger.info("DB engine disposed")
    except ImportError:
        pass


app = FastAPI(title="Personal AI Assistant", version="0.1.0", lifespan=lifespan)


@app.get("/")
async def root():
    return {
        "name": "Personal AI Assistant API",
        "version": "0.1.0",
        "docs": "/docs",
    }


app.add_middleware(AuthMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
app.include_router(spendings.router, prefix="/api")
app.include_router(memes.router, prefix="/api")
