import json
import math
from dataclasses import dataclass, field, asdict
from backend.session_store import get_redis, set_risk_score, get_baseline

WEIGHTS = {
    "ip_country": 0.25,
    "device_fp": 0.20,
    "data_mb": 0.15,
    "api_calls": 0.12,
    "login_hour": 0.10,
    "mouse_velocity": 0.10,
    "wpm": 0.08,
}


@dataclass
class UserBaseline:
    login_hour_mean: float = 9.0
    login_hour_std: float = 1.5
    wpm_mean: float = 45.0
    wpm_std: float = 12.0
    data_mb_mean: float = 5.0
    data_mb_std: float = 2.0
    mouse_velocity_mean: float = 300.0
    mouse_velocity_std: float = 80.0
    api_calls_mean: float = 10.0
    api_calls_std: float = 4.0
    ip_countries: set = field(default_factory=lambda: {"US"})
    device_fps: set = field(default_factory=lambda: set())

    def to_dict(self):
        d = asdict(self)
        d["ip_countries"] = list(self.ip_countries)
        d["device_fps"] = list(self.device_fps)
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d = dict(d)
        d["ip_countries"] = set(d.get("ip_countries", ["US"]))
        d["device_fps"] = set(d.get("device_fps", []))
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def z_score(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0 if value == mean else 5.0
    return abs((value - mean) / std)


def score_session(baseline: UserBaseline, signals: dict) -> tuple[float, dict]:
    """Score a session against the baseline. Returns (score 0-100, z_scores dict)."""
    z_scores = {}

    ip = signals.get("ip_country", "US")
    z_scores["ip_country"] = 0.0 if ip in baseline.ip_countries else 5.0

    device_fp = signals.get("device_fp", "")
    if baseline.device_fps and device_fp:
        z_scores["device_fp"] = 0.0 if device_fp in baseline.device_fps else 5.0
    else:
        z_scores["device_fp"] = 0.0

    z_scores["data_mb"] = z_score(
        signals.get("data_mb", baseline.data_mb_mean),
        baseline.data_mb_mean, baseline.data_mb_std
    )
    z_scores["api_calls"] = z_score(
        signals.get("api_calls", baseline.api_calls_mean),
        baseline.api_calls_mean, baseline.api_calls_std
    )
    z_scores["login_hour"] = z_score(
        signals.get("login_hour", baseline.login_hour_mean),
        baseline.login_hour_mean, baseline.login_hour_std
    )
    z_scores["mouse_velocity"] = z_score(
        signals.get("mouse_velocity", baseline.mouse_velocity_mean),
        baseline.mouse_velocity_mean, baseline.mouse_velocity_std
    )
    z_scores["wpm"] = z_score(
        signals.get("wpm", baseline.wpm_mean),
        baseline.wpm_mean, baseline.wpm_std
    )

    raw = sum(z_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    score = min(100.0, max(0.0, raw * 20.0))

    return round(score, 1), z_scores


async def load_baseline(user_id: str) -> UserBaseline:
    data = await get_baseline(user_id)
    if data:
        return UserBaseline.from_dict(data)
    return UserBaseline()


async def save_baseline(user_id: str, baseline: UserBaseline):
    from backend.session_store import set_baseline
    await set_baseline(user_id, baseline.to_dict())
