from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection (models created in a later task)
    try:
        from app.models.database import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except ImportError:
        # Models not yet implemented — skip DB check
        pass
    except Exception:
        # DB not available — continue, app is still functional for development
        pass
    yield
    # Shutdown
    try:
        from app.models.database import engine
        await engine.dispose()
    except ImportError:
        pass


app = FastAPI(title="Personal AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes will be registered in later tasks
