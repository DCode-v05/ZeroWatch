from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    role: str = ""
    department: str = ""
    access_permissions: str = ""
    baseline_json: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Session(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True, unique=True)
    user_id: int = Field(foreign_key="user.id")
    device_fp: str = ""
    ip_address: str = ""
    ip_country: str = ""
    risk_score: float = 0.0
    status: str = "active"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Incident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = ""
    user_id: int = 0
    score: float = 0.0
    narrative: str = ""
    action_taken: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SignalEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    signal_type: str = ""
    value: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
