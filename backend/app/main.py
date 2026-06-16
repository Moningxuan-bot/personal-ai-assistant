from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.auth import AuthMiddleware
from app.routes import chat, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    try:
        from app.models.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except ImportError:
        pass
    except Exception:
        pass

    # Preload embedding model so first request doesn't block on download
    try:
        from app.providers.embedding import embed_provider
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, embed_provider._load_model)
    except Exception:
        pass  # App still works for basic chat without embeddings

    yield
    # Shutdown
    try:
        from app.models.database import engine
        await engine.dispose()
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api")
