"""Generate 30 synthetic normal sessions to seed the baseline for demo users."""
import asyncio
import json
import random
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.session_store import get_redis, set_baseline
from backend.risk_engine import UserBaseline


async def seed():
    r = await get_redis()
    await r.ping()
    print("Connected to Redis. Seeding baselines...")

    demo_users = {
        "1": UserBaseline(
            login_hour_mean=9.5, login_hour_std=1.2,
            wpm_mean=48.0, wpm_std=10.0,
            data_mb_mean=4.5, data_mb_std=1.8,
            mouse_velocity_mean=310.0, mouse_velocity_std=75.0,
            api_calls_mean=12.0, api_calls_std=3.5,
            ip_countries={"US", "IN"},
            device_fps={"known-device", "office-laptop"},
        ),
        "2": UserBaseline(
            login_hour_mean=10.0, login_hour_std=1.0,
            wpm_mean=55.0, wpm_std=8.0,
            data_mb_mean=6.0, data_mb_std=2.0,
            mouse_velocity_mean=280.0, mouse_velocity_std=60.0,
            api_calls_mean=15.0, api_calls_std=5.0,
            ip_countries={"US"},
            device_fps={"dev-macbook"},
        ),
    }

    for user_id, baseline in demo_users.items():
        await set_baseline(user_id, baseline.to_dict())
        print(f"  User {user_id}: baseline saved to Redis")
        print(f"    Countries: {baseline.ip_countries}")
        print(f"    Login hour: {baseline.login_hour_mean} +/- {baseline.login_hour_std}")

    for i in range(30):
        snapshot = {
            "session_id": f"synthetic-{i}",
            "ip_country": random.choice(["US", "US", "US", "IN"]),
            "device_fp": random.choice(["known-device", "office-laptop"]),
            "data_mb": round(random.gauss(4.5, 1.8), 1),
            "api_calls": int(random.gauss(12, 3.5)),
            "login_hour": int(random.gauss(9.5, 1.2)),
            "mouse_velocity": round(random.gauss(310, 75), 0),
            "wpm": round(random.gauss(48, 10), 0),
        }
        await r.set(f"training:snapshot:{i}", json.dumps(snapshot), ex=86400)

    print(f"\n30 training snapshots saved.")
    print("Baseline seeding complete!")
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(seed())
