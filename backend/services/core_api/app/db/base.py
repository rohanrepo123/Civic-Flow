"""Shared SQLAlchemy metadata for the Core API persistence boundary."""
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from app.db.health import engine

class Base(MappedAsDataclass, DeclarativeBase):
    pass

SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session():
    async with SessionFactory() as session:
        yield session
