import asyncio
from datetime import datetime
from backend.risk_engine import load_baseline, score_session
from backend.session_store import set_risk_score, get_session


async def signal_worker(signal_queue: asyncio.Queue, broadcast_fn):
    """Background worker: consume signal queue, compute risk scores, broadcast via WebSocket."""
    session_signals: dict[str, dict] = {}

    while True:
        batch = []
        try:
            while True:
                sig = signal_queue.get_nowait()
                batch.append(sig)
        except asyncio.QueueEmpty:
            pass

        for sig in batch:
            sid = sig.get("session_id", "")
            if not sid:
                continue
            if sid not in session_signals:
                session_signals[sid] = {}
            sig_type = sig.get("signal_type", sig.get("type", ""))
            value = sig.get("value", 0)
            if sig_type:
                session_signals[sid][sig_type] = value
            for key in ["ip_country", "device_fp", "data_mb", "api_calls",
                        "login_hour", "mouse_velocity", "wpm"]:
                if key in sig:
                    session_signals[sid][key] = sig[key]

        for sid, signals in list(session_signals.items()):
            session_data = await get_session(sid)
            if not session_data:
                session_signals.pop(sid, None)
                continue

            user_id = str(session_data.get("user_id", "1"))
            baseline = await load_baseline(user_id)
            score, z_scores = score_session(baseline, signals)

            await set_risk_score(sid, score)

            await broadcast_fn({
                "type": "risk_update",
                "session_id": sid,
                "user": session_data.get("username", "unknown"),
                "score": score,
                "delta": score - signals.get("_prev_score", 0),
                "z_scores": {k: round(v, 2) for k, v in z_scores.items()},
                "flags": [k for k, v in z_scores.items() if v > 2.0],
                "timestamp": datetime.utcnow().isoformat(),
            })
            signals["_prev_score"] = score

        await asyncio.sleep(3)
