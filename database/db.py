from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DB_PATH = Path(__file__).resolve().parent.parent / "scalp_hunter.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        yield session


async def init_db():
    from database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
