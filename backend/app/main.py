from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    from app.models.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(title="Personal AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes will be registered in later tasks
