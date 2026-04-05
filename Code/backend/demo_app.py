"""Demo target app routes — these are the "protected" endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/app", tags=["demo-app"])


@router.get("/dashboard")
async def dashboard():
    return {"page": "dashboard", "data": "Welcome to ZeroWatch protected app"}


@router.get("/transfer")
async def transfer():
    return {"page": "transfer", "status": "sensitive_endpoint", "amount": 50000}


@router.get("/admin")
async def admin():
    return {"page": "admin", "status": "sensitive_endpoint", "users": 142}


@router.get("/export")
async def export():
    return {"page": "export", "status": "sensitive_endpoint", "records": 10000}
