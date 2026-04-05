import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, create_engine, Session as DBSession, select
from pydantic import BaseModel

from backend.config import DATABASE_URL
from backend.session_store import (
    get_redis, set_session, get_session, delete_session,
    set_risk_score, get_risk_score, set_pubkey, set_baseline, get_baseline,
)
from backend.risk_engine import UserBaseline, score_session, load_baseline, save_baseline
from backend.models import User, Session as SessionModel, Incident, SignalEvent  # noqa: F401 — ensure tables registered

engine = create_engine(DATABASE_URL, echo=False)

# Global signal queue (replaces Kafka)
signal_queue: asyncio.Queue = asyncio.Queue()

# Connected WebSocket clients
ws_clients: list[WebSocket] = []

# Active demo session tracking
demo_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create DB tables + verify Redis
    SQLModel.metadata.create_all(engine)
    r = await get_redis()
    await r.ping()
    print("Redis connected, SQLite tables created.")

    # Start signal worker background task
    from backend.signal_worker import signal_worker
    worker_task = asyncio.create_task(signal_worker(signal_queue, broadcast_risk))

    yield

    # Shutdown
    worker_task.cancel()
    r = await get_redis()
    await r.aclose()


app = FastAPI(title="ZeroWatch", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    with DBSession(engine) as session:
        yield session


# ─── Health ───
@app.get("/health")
async def health():
    try:
        r = await get_redis()
        await r.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
    return {"status": "ok", "redis": redis_status}


# ─── WebSocket for live risk scores ───
@app.websocket("/ws/risk")
async def ws_risk(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


async def broadcast_risk(data: dict):
    dead = []
    for ws in ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_clients:
            ws_clients.remove(ws)


# ─── Auth ───
class LoginRequest(BaseModel):
    username: str
    password: str = "demo"


@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    session_id = str(uuid.uuid4())
    with DBSession(engine) as db:
        user = db.exec(select(User).where(User.username == req.username)).first()
        if not user:
            return {"error": "User not found. Create user first via POST /api/users"}
        user_id = user.id
        username = user.username
        db_session = SessionModel(
            session_id=session_id,
            user_id=user_id,
            status="active",
        )
        db.add(db_session)
        db.commit()

    await set_session(session_id, {
        "user_id": user_id,
        "username": username,
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    })
    response.set_cookie("session_id", session_id, httponly=True, samesite="lax")
    demo_state["active_session"] = session_id
    demo_state["active_user_id"] = user_id
    demo_state["active_username"] = username
    return {"session_id": session_id, "user_id": user_id, "username": username}


# ─── Demo Login (email/password for static demo pages) ───
class DemoLoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/demo/login")
async def demo_login(req: DemoLoginRequest, response: Response):
    if req.email != "admin@gmail.com" or req.password != "admin":
        return Response(
            content=json.dumps({"error": "Invalid credentials"}),
            status_code=401,
            media_type="application/json",
        )

    # Create or get the admin user
    with DBSession(engine) as db:
        user = db.exec(select(User).where(User.username == "admin")).first()
        if not user:
            user = User(username="admin", role="Admin", department="Security", access_permissions="admin,read,write")
            db.add(user)
            db.commit()
            db.refresh(user)
        user_id = user.id

    session_id = str(uuid.uuid4())
    await set_session(session_id, {
        "user_id": user_id,
        "username": "admin",
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    })

    with DBSession(engine) as db:
        db_session = SessionModel(session_id=session_id, user_id=user_id, status="active")
        db.add(db_session)
        db.commit()

    response.set_cookie("session_id", session_id, httponly=False, samesite="lax")
    demo_state["active_session"] = session_id
    demo_state["active_user_id"] = user_id
    demo_state["active_username"] = "admin"
    return {"session_id": session_id, "user_id": user_id, "username": "admin"}


# ─── Session verification (protected by middleware — requires valid ECDSA sig) ───
@app.get("/api/session/verify")
async def verify_session(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return Response(content=json.dumps({"error": "no_session"}), status_code=401, media_type="application/json")
    session_data = await get_session(session_id)
    if not session_data:
        return Response(content=json.dumps({"error": "session_expired"}), status_code=401, media_type="application/json")
    return {"status": "valid", "username": session_data.get("username"), "session_id": session_id}


@app.post("/api/auth/register-device")
async def register_device(request: Request):
    body = await request.json()
    session_id = request.cookies.get("session_id") or body.get("session_id", "")
    pubkey = body.get("pubkey", "")
    if session_id and pubkey:
        await set_pubkey(session_id, pubkey)
        return {"status": "registered"}
    return {"error": "Missing session_id or pubkey"}


# ─── Signals ───
@app.post("/api/signals")
async def receive_signals(request: Request):
    body = await request.json()
    session_id = request.cookies.get("session_id") or body.get("session_id", "")
    signals = body.get("signals", [])
    for sig in signals:
        sig["session_id"] = session_id
        await signal_queue.put(sig)
    return {"queued": len(signals)}


# ─── Users ───
class CreateUserRequest(BaseModel):
    username: str
    role: str = "Analyst"
    department: str = "General"
    access_permissions: str = "read"


@app.post("/api/users")
async def create_user(req: CreateUserRequest):

    with DBSession(engine) as db:
        existing = db.exec(select(User).where(User.username == req.username)).first()
        if existing:
            return {
                "user_id": existing.id,
                "username": existing.username,
                "baseline": json.loads(existing.baseline_json) if existing.baseline_json else {},
            }

        user = User(
            username=req.username,
            role=req.role,
            department=req.department,
            access_permissions=req.access_permissions,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # LLM baseline generation
    try:
        from backend.llm import synthesise_baseline
        baseline = await synthesise_baseline(req.role, req.department, req.access_permissions)
        with DBSession(engine) as db:
            u = db.get(User, user.id)
            u.baseline_json = json.dumps(baseline)
            db.add(u)
            db.commit()
        await set_baseline(str(user.id), baseline)

        # Also create a behavioral baseline for scoring
        behavioral = UserBaseline(
            login_hour_mean=baseline.get("expected_hours_start", 9),
            login_hour_std=1.5,
            wpm_mean=45.0, wpm_std=12.0,
            data_mb_mean=sum(baseline.get("data_mb_range", [1, 10])) / 2,
            data_mb_std=2.0,
            api_calls_mean=sum(baseline.get("api_calls_per_min_range", [5, 15])) / 2,
            api_calls_std=4.0,
            ip_countries={"US", "IN"},
            device_fps=set(),
        )
        await save_baseline(str(user.id), behavioral)

        return {"user_id": user.id, "username": user.username, "baseline": baseline}
    except Exception as e:
        import traceback
        print(f"LLM baseline skipped: {e}")
        traceback.print_exc()
        # Save default behavioral baseline anyway
        await save_baseline(str(user.id), UserBaseline())
        return {"user_id": user.id, "username": user.username, "baseline": {}, "note": "LLM not configured yet"}


# ─── Demo Simulation ───
@app.post("/api/demo/simulate/{scenario}")
async def simulate(scenario: str):
    """Simulate attack scenarios for the demo. Each pushes signals into the queue."""
    session_id = demo_state.get("active_session", "demo-session")
    user_id = demo_state.get("active_user_id", 1)
    username = demo_state.get("active_username", "demo")

    # Ensure session exists in Redis
    existing = await get_session(session_id)
    if not existing:
        await set_session(session_id, {
            "user_id": user_id,
            "username": username,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
        })

    if scenario == "normal":
        signals = {
            "session_id": session_id,
            "ip_country": "US",
            "device_fp": "known-device",
            "data_mb": 3.0,
            "api_calls": 8,
            "login_hour": 10,
            "mouse_velocity": 280,
            "wpm": 42,
        }
        await signal_queue.put(signals)
        return {"scenario": "normal", "status": "signals_sent", "expected_score": "4-10"}

    elif scenario == "change_country":
        signals = {
            "session_id": session_id,
            "ip_country": "RU",
            "device_fp": "known-device",
            "data_mb": 4.0,
            "api_calls": 12,
            "login_hour": 10,
            "mouse_velocity": 300,
            "wpm": 44,
        }
        await signal_queue.put(signals)
        return {"scenario": "change_country", "status": "signals_sent", "expected_score": "25-40"}

    elif scenario == "stolen_token":
        # No ECDSA signature — this is handled by the middleware
        # Push signals with unknown device
        signals = {
            "session_id": session_id,
            "ip_country": "CN",
            "device_fp": "unknown-device-xyz",
            "data_mb": 50.0,
            "api_calls": 45,
            "login_hour": 3,
            "mouse_velocity": 0,
            "wpm": 0,
        }
        await signal_queue.put(signals)
        return {"scenario": "stolen_token", "status": "signals_sent", "expected_score": "85+"}

    elif scenario == "rapid_export":
        signals = {
            "session_id": session_id,
            "ip_country": "US",
            "device_fp": "known-device",
            "data_mb": 150.0,
            "api_calls": 80,
            "login_hour": 2,
            "mouse_velocity": 50,
            "wpm": 120,
        }
        await signal_queue.put(signals)
        return {"scenario": "rapid_export", "status": "signals_sent", "expected_score": "60-80"}

    elif scenario == "full_attack":
        # Multi-step escalating attack
        steps = [
            {"ip_country": "US", "device_fp": "known-device", "data_mb": 5, "api_calls": 10, "login_hour": 10, "mouse_velocity": 280, "wpm": 42},
            {"ip_country": "RU", "device_fp": "known-device", "data_mb": 8, "api_calls": 15, "login_hour": 10, "mouse_velocity": 200, "wpm": 35},
            {"ip_country": "RU", "device_fp": "unknown-abc", "data_mb": 30, "api_calls": 35, "login_hour": 3, "mouse_velocity": 100, "wpm": 10},
            {"ip_country": "CN", "device_fp": "unknown-xyz", "data_mb": 80, "api_calls": 60, "login_hour": 3, "mouse_velocity": 20, "wpm": 0},
            {"ip_country": "CN", "device_fp": "unknown-xyz", "data_mb": 200, "api_calls": 100, "login_hour": 3, "mouse_velocity": 0, "wpm": 0},
        ]

        async def escalate():
            for i, step in enumerate(steps):
                step["session_id"] = session_id
                await signal_queue.put(step)
                await asyncio.sleep(3)  # Wait for worker to process

        asyncio.create_task(escalate())
        return {"scenario": "full_attack", "status": "escalation_started", "steps": len(steps)}

    return {"error": f"Unknown scenario: {scenario}"}


# ─── Active sessions list ───
@app.get("/api/sessions")
async def list_sessions():
    r = await get_redis()
    keys = []
    async for key in r.scan_iter("session:*"):
        if ":risk_score" not in key and ":pubkey" not in key:
            keys.append(key)
    sessions = []
    for key in keys[:20]:
        data = await r.get(key)
        if data:
            sid = key.replace("session:", "")
            d = json.loads(data)
            score = await get_risk_score(sid)
            sessions.append({**d, "session_id": sid, "risk_score": score})
    return {"sessions": sessions}


# ─── Incidents list ───
@app.get("/api/incidents")
async def list_incidents():

    with DBSession(engine) as db:
        incidents = db.exec(select(Incident).order_by(Incident.id.desc()).limit(20)).all()
        return {"incidents": [
            {"id": i.id, "session_id": i.session_id, "user_id": i.user_id,
             "score": i.score, "narrative": i.narrative, "action": i.action_taken,
             "created_at": i.created_at}
            for i in incidents
        ]}


# ─── Protected app routes (these require ECDSA device binding) ───
@app.get("/app/dashboard")
async def app_dashboard():
    return {"page": "dashboard", "data": "Account Balance: $48,239.00", "status": "authenticated"}

@app.get("/app/transfer")
async def app_transfer():
    return {"page": "transfer", "data": "Recent transfers: 3 pending", "status": "sensitive_endpoint"}

@app.get("/app/admin")
async def app_admin():
    return {"page": "admin", "data": "Users: 142, Active sessions: 38", "status": "sensitive_endpoint"}

@app.get("/app/export")
async def app_export():
    return {"page": "export", "data": "10,000 records available", "status": "sensitive_endpoint"}


# ─── Serve static files (demo app HTML pages) ───
_static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ─── Add middleware (must be after route registration) ───
from backend.middleware import ZeroWatchMiddleware
app.add_middleware(ZeroWatchMiddleware)
