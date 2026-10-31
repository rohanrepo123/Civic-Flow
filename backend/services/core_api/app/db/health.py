from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from redis.asyncio import Redis
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)

async def dependency_health() -> dict[str, str]:
    if settings.LOCAL_DEMO_MODE:
        return {"postgres": "not_required", "redis": "not_required"}
    result = {"postgres": "unavailable", "redis": "unavailable"}
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        result["postgres"] = "ready"
    except Exception:
        pass
    try:
        await redis_client.ping()
        result["redis"] = "ready"
    except Exception:
        pass
    return result

async def close_connections():
    await engine.dispose()
    await redis_client.aclose()
