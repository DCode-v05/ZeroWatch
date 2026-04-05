import json
import redis.asyncio as aioredis
from backend.config import REDIS_URL

_redis = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def set_session(session_id: str, data: dict, ttl: int = 3600):
    r = await get_redis()
    await r.set(f"session:{session_id}", json.dumps(data), ex=ttl)


async def get_session(session_id: str) -> dict | None:
    r = await get_redis()
    raw = await r.get(f"session:{session_id}")
    return json.loads(raw) if raw else None


async def delete_session(session_id: str):
    r = await get_redis()
    await r.delete(f"session:{session_id}")


async def set_risk_score(session_id: str, score: float, ttl: int = 30):
    r = await get_redis()
    await r.set(f"session:{session_id}:risk_score", str(score), ex=ttl)


async def get_risk_score(session_id: str) -> float:
    r = await get_redis()
    raw = await r.get(f"session:{session_id}:risk_score")
    return float(raw) if raw else 0.0


async def set_pubkey(session_id: str, pubkey: str, ttl: int = 86400):
    r = await get_redis()
    await r.set(f"session:{session_id}:pubkey", pubkey, ex=ttl)


async def get_pubkey(session_id: str) -> str | None:
    r = await get_redis()
    return await r.get(f"session:{session_id}:pubkey")


async def set_baseline(user_id: str, baseline: dict):
    r = await get_redis()
    await r.set(f"user:{user_id}:baseline", json.dumps(baseline))


async def get_baseline(user_id: str) -> dict | None:
    r = await get_redis()
    raw = await r.get(f"user:{user_id}:baseline")
    return json.loads(raw) if raw else None
