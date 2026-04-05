"""Deterministic demo attack script. Run from the zerowatch/ directory.

Usage:
    python scripts/demo_attack.py --scenario stolen_token
    python scripts/demo_attack.py --scenario full_attack
"""
import argparse
import asyncio
import aiohttp
import sys

BASE_URL = "http://localhost:8000"


async def run_scenario(scenario: str):
    async with aiohttp.ClientSession() as session:
        # 1. Create demo user
        print("[1/4] Creating demo user Sneha...")
        async with session.post(f"{BASE_URL}/api/users", json={
            "username": "Sneha",
            "role": "Junior Analyst",
            "department": "Retail Banking",
            "access_permissions": "read,reports",
        }) as resp:
            data = await resp.json()
            print(f"  User: {data}")

        # 2. Login
        print("[2/4] Logging in...")
        async with session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "Sneha",
        }) as resp:
            data = await resp.json()
            session_id = data.get("session_id", "")
            print(f"  Session: {session_id}")

        # 3. Normal activity
        print("[3/4] Sending normal activity...")
        async with session.post(f"{BASE_URL}/api/demo/simulate/normal") as resp:
            data = await resp.json()
            print(f"  Normal: {data}")

        await asyncio.sleep(4)

        # 4. Run attack scenario
        print(f"[4/4] Running attack: {scenario}")
        async with session.post(f"{BASE_URL}/api/demo/simulate/{scenario}") as resp:
            data = await resp.json()
            print(f"  Attack: {data}")

        if scenario == "full_attack":
            print("\nWatching score escalation (press Ctrl+C to stop)...")
            for i in range(20):
                await asyncio.sleep(3)
                try:
                    async with session.get(f"{BASE_URL}/api/sessions") as resp:
                        data = await resp.json()
                        for s in data.get("sessions", []):
                            if s.get("username") == "Sneha":
                                print(f"  t={i*3}s  Score: {s.get('risk_score', 0)}")
                except Exception:
                    pass

        print("\nDemo complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ZeroWatch Demo Attack Script")
    parser.add_argument("--scenario", default="full_attack",
                        choices=["normal", "change_country", "stolen_token", "rapid_export", "full_attack"])
    args = parser.parse_args()
    asyncio.run(run_scenario(args.scenario))
