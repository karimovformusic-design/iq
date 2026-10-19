from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mindora.settings import settings


engine_options = {"pool_pre_ping": True}
if settings.database_url.startswith("postgresql+"):
    engine_options.update({"pool_size": 5, "max_overflow": 10})
engine = create_async_engine(settings.database_url, **engine_options)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def dispose_engine() -> None:
    await engine.dispose()
