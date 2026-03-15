import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://legaldb_user:password@localhost:5432/legaldb")

# Convert postgres:// to postgresql+asyncpg:// if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create tables and enable pgvector + unaccent extensions."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
        from models import Base as ModelBase  # noqa: F811
        await conn.run_sync(ModelBase.metadata.create_all)
        # FTS indexes for Vietnamese diacritic-insensitive search
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_documents_fts
            ON documents USING GIN (
                to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || coalesce(ten,'') || ' ' || coalesce(tom_tat,'')))
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_cong_van_fts
            ON cong_van USING GIN (
                to_tsvector('simple', unaccent(coalesce(so_hieu,'') || ' ' || ten))
            )
        """))
