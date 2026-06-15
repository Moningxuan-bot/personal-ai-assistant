import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://aitest:aitest@localhost:5432/aitest"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
