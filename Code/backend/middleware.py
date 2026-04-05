import asyncio
import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.session_store import get_pubkey, get_risk_score, delete_session, get_session
from backend.llm import narrate_incident

SKIP_PATHS = [
    "/health", "/docs", "/openapi.json", "/redoc",
    "/api/auth/login", "/api/auth/register-device", "/api/signals",
    "/api/users", "/api/demo/",
    "/ws/",
    "/static/",
]

SENSITIVE_PATHS = ["/app/transfer", "/app/admin", "/app/export"]


class ZeroWatchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-protected paths
        for skip in SKIP_PATHS:
            if path.startswith(skip):
                return await call_next(request)

        # Extract session_id from cookie
        session_id = request.cookies.get("session_id")
        if not session_id:
            return await call_next(request)

        # ─── Device Binding Check ───
        signature = request.headers.get("x-zw-signature")
        timestamp = request.headers.get("x-zw-timestamp")
        request_pubkey = request.headers.get("x-zw-pubkey")

        # Must have signature + timestamp + pubkey headers (proves SDK is running)
        if not signature or not timestamp or not request_pubkey:
            return JSONResponse(
                status_code=401,
                content={"error": "missing_signature", "detail": "Device signature headers not present. Cookie alone is not enough."}
            )

        # Timestamp freshness check (30 second window)
        try:
            ts = int(timestamp)
            if abs(time.time() * 1000 - ts) > 30000:
                return JSONResponse(
                    status_code=401,
                    content={"error": "signature_expired"}
                )
        except ValueError:
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_timestamp"}
            )

        # Verify device binding: the pubkey in the request must match the
        # pubkey that was registered during login on the original device.
        # Browser B has a DIFFERENT key pair → different pubkey → mismatch → rejected.
        registered_pubkey = await get_pubkey(session_id)
        if registered_pubkey and request_pubkey != registered_pubkey:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "session_hijack",
                    "detail": "Device public key does not match the registered device. Session cookie was used from an unauthorized device.",
                }
            )

        # ─── Risk Score Enforcement ───
        score = await get_risk_score(session_id)

        if score >= 71:
            await delete_session(session_id)
            session_data = await get_session(session_id) or {}
            asyncio.create_task(
                _narrate_and_broadcast(session_id, session_data, score)
            )
            return JSONResponse(
                status_code=401,
                content={"error": "session_terminated", "score": score}
            )

        if 31 <= score <= 70 and path in SENSITIVE_PATHS:
            return JSONResponse(
                status_code=202,
                content={"action": "mfa_required", "score": score}
            )

        # Score 0-30: forward with header
        response = await call_next(request)
        response.headers["X-ZeroWatch-Score"] = str(score)
        return response


async def _narrate_and_broadcast(session_id: str, session_data: dict, score: float):
    """Generate incident narrative and broadcast to WebSocket clients."""
    try:
        from backend.main import broadcast_risk
        user_id = str(session_data.get("user_id", "unknown"))
        narrative = await narrate_incident(
            user_id=user_id,
            z_scores=session_data.get("z_scores", {}),
            baseline=session_data.get("baseline", {}),
            flags=session_data.get("flags", []),
        )

        await broadcast_risk({
            "type": "incident",
            "session_id": session_id,
            "user": session_data.get("username", "unknown"),
            "score": score,
            "narrative": narrative,
            "action": "session_terminated",
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        })
    except Exception as e:
        print(f"Narration broadcast error: {e}")
