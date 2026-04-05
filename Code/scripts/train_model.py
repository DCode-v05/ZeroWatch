"""Train Isolation Forest on baseline data. Saves .pkl per user."""
import asyncio
import json
import pickle
import os
import sys
import numpy as np
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.session_store import get_redis


async def train():
    r = await get_redis()
    print("Loading training snapshots from Redis...")

    samples = []
    for i in range(30):
        raw = await r.get(f"training:snapshot:{i}")
        if raw:
            snap = json.loads(raw)
            samples.append([
                snap.get("data_mb", 5),
                snap.get("api_calls", 10),
                snap.get("login_hour", 10),
                snap.get("mouse_velocity", 300),
                snap.get("wpm", 45),
            ])

    if len(samples) < 5:
        print("Not enough training data. Run seed_baseline.py first.")
        await r.aclose()
        return

    X = np.array(samples)
    print(f"Training on {len(X)} samples...")

    model = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
    model.fit(X)

    os.makedirs("models", exist_ok=True)
    with open("models/isolation_forest_user1.pkl", "wb") as f:
        pickle.dump(model, f)

    print("Model saved to models/isolation_forest_user1.pkl")
    print(f"Sample prediction: {model.predict(X[:3])}")
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(train())
