from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import os

DATABASE_URL = "sqlite+aiosqlite:///./audio_chat.db"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    from models import Project, Document, Fact, Script, Audio
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe schema migration: dynamically add new columns to audios table if they don't exist
        try:
            await conn.execute(text("ALTER TABLE audios ADD COLUMN model_name VARCHAR DEFAULT 'kokoro-82m';"))
        except Exception:
            pass # already exists
        try:
            await conn.execute(text("ALTER TABLE audios ADD COLUMN settings JSON;"))
        except Exception:
            pass # already exists
        try:
            await conn.execute(text("ALTER TABLE facts ADD COLUMN document_ids VARCHAR;"))
        except Exception:
            pass # already exists

