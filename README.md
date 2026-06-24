# ZeroWatch

**Zero Trust session monitoring that scores every active session in real time and decides whether to allow it, force step-up MFA, or kill it.**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![SQLModel](https://img.shields.io/badge/SQLModel-7E56C2?style=flat&logo=sqlite&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white) ![React](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?style=flat&logo=tailwindcss&logoColor=white) ![Groq](https://img.shields.io/badge/Groq_Llama_3.3-F55036?style=flat&logo=meta&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

## Overview

Most session security stops at the login screen. Once you have a valid cookie or JWT, the server trusts you for the rest of the session — which is exactly why stolen tokens, hijacked cookies, and insider misuse work so well. The login was legitimate; what happened afterward isn't checked.

ZeroWatch checks what happens afterward. It's a Zero Trust session monitor that keeps scoring every active session against a behavioral baseline, second by second, and answers a different question than the login form does: not *who logged in*, but *who is using this session right now*. When the behavior stops matching the person, the session gets flagged, stepped up to MFA, or terminated — automatically.

It does this with three pieces working together: a behavioral risk engine that compares live signals to a per-user baseline, ECDSA P-256 device binding so a stolen cookie alone is useless from another machine, and a Groq/Llama 3.3 layer that writes the human-readable incident report when something goes wrong. The whole thing ships with a React dashboard and a built-in attack simulator so you can watch a session escalate from "normal" to "terminated" live. It was built as a hackathon project (the AlphaQ / HTF submission) and is a complete, working end-to-end build.

## Key Features

- **Continuous session scoring** — every session gets a live 0–100 risk score, recomputed as new behavioral signals arrive (roughly every 2 seconds from the browser SDK).
- **Seven-signal behavioral engine** — weighted z-score anomaly detection across IP country, device fingerprint, data volume, API call rate, login hour, mouse velocity, and typing speed (WPM).
- **ECDSA P-256 device binding** — the browser generates a non-extractable signing key, stored in IndexedDB, and signs every request. A cookie copied to a different browser carries a different public key, so the server rejects it as a hijack.
- **Adaptive three-tier enforcement** — score 0–30 allows the request, 31–70 forces MFA on sensitive endpoints, 71+ terminates the session immediately.
- **Signature freshness window** — requests carry a timestamp; anything older than 30 seconds is rejected, which blocks replayed signatures.
- **LLM behavioral baselines** — when a user is created, Groq/Llama 3.3 generates a role- and department-aware baseline profile (expected hours, data ranges, API rates, device type).
- **LLM incident narratives** — when a session is terminated, the model writes a short plain-English report of what happened and why, instead of dumping raw z-scores.
- **Graceful LLM fallback** — no Groq key, no problem: the system falls back to hardcoded baselines and template narratives so the demo still runs.
- **Built-in attack simulator** — five scenarios (Normal, Country Change, Stolen Token, Rapid Export, and a multi-step Full Attack escalation) push synthetic signals through the real pipeline.
- **Real-time dashboard** — React 19 + Recharts UI with a live risk gauge, per-signal anomaly heatmap, active sessions list, and an incident log, all driven over WebSocket.
- **Zero-dependency browser SDK** — a single IIFE that handles key management, canvas device fingerprinting, keystroke/mouse capture, signal batching, and a fetch interceptor that signs outgoing requests.
- **Protected mock app** — `/app/*` endpoints (dashboard, transfer, admin, export) stand in for a real banking-style application so the enforcement tiers have something to protect.

## How It Works

The system is a FastAPI backend, a Redis-backed real-time pipeline, a React dashboard, and a browser SDK that runs inside the protected app. Here's the flow.

### 1. Device binding (the SDK)

On first load, `sdk/zw-sdk.js` generates an ECDSA P-256 key pair with the Web Crypto API. The private key is marked **non-extractable** and persisted in IndexedDB, so it never leaves the browser and can't be read out by script. The raw public key is exported and registered with the server against the session (`POST /api/auth/register-device`).

From then on, the SDK installs a `fetch` interceptor: every outgoing request is signed with the device key and carries three headers — `x-zw-signature`, `x-zw-timestamp`, and `x-zw-pubkey`. The SDK also builds a device fingerprint (canvas rendering plus environment components) and quietly tracks keystrokes and mouse movement to derive typing speed and pointer velocity.

### 2. Server-side signature verification

This is the part that's easy to get wrong. WebCrypto emits ECDSA signatures in IEEE P1363 format — a raw 64-byte `r‖s` concatenation — but Python's `cryptography` library expects DER. `backend/ecdsa_verify.py` decodes the 65-byte uncompressed public point, splits the 64-byte signature into its two 32-byte halves, re-encodes them as a DER `DSS` signature with `encode_dss_signature`, and verifies against SHA-256. Getting this conversion right is what makes the device binding actually work end to end.

The middleware (`backend/middleware.py`) enforces it on every protected route: missing signature headers → `401 missing_signature` (a cookie on its own is explicitly not enough), a timestamp outside the 30-second window → `401 signature_expired`, and a public key that doesn't match the one registered at login → `401 session_hijack`. That last check is the anti-hijack core: a stolen cookie used from a second browser presents a *different* device key, so it fails.

### 3. The behavioral risk engine

`backend/risk_engine.py` scores a session by comparing live signals to a `UserBaseline`. Each signal contributes an anomaly value:

- **Categorical signals** (IP country, device fingerprint) score `0.0` if the value is known/registered, or a max anomaly of `5.0` if it isn't.
- **Numerical signals** (data MB, API calls, login hour, mouse velocity, WPM) use the absolute z-score against the baseline mean and standard deviation.

The anomalies are combined with fixed weights, then scaled by ×20 and clamped to 0–100:

| Signal | Weight | What it catches |
|---|---|---|
| IP country | 25% | Login from an unexpected geolocation |
| Device fingerprint | 20% | An unregistered device |
| Data volume (MB) | 15% | Abnormal data export / exfiltration |
| API call rate | 12% | Scripted or excessive API usage |
| Login hour | 10% | Off-hours access |
| Mouse velocity | 10% | Bot-like or absent pointer movement |
| Typing speed (WPM) | 8% | Anomalous or non-human typing |

A weighted z-sum near the per-feature max maps to a score near 100, so a fully anomalous session (unknown country + unknown device + heavy export + 3 a.m. + zero biometrics) lands in the 85+ range.

### 4. The real-time pipeline

The SDK posts batched signals to `POST /api/signals`. Instead of a heavyweight broker, the backend uses an in-process `asyncio.Queue` as the signal bus. A background `signal_worker` task (started in the FastAPI lifespan) consumes the queue, runs each batch through the risk engine, writes the score to Redis, and broadcasts the result to every connected dashboard over the `/ws/risk` WebSocket. Sessions, risk scores, and registered public keys all live in Redis (async client); users, sessions, incidents, and signal events are persisted in SQLite via SQLModel.

### 5. Enforcement

Enforcement happens in the same middleware, after the device check. It reads the current risk score from Redis and applies the tiers: 71+ deletes the session and kicks off an async task to narrate and broadcast the incident; 31–70 returns `202 mfa_required` for sensitive paths (`/app/transfer`, `/app/admin`, `/app/export`); 0–30 forwards the request and stamps the response with an `X-ZeroWatch-Score` header.

### 6. The LLM layer (Groq / Llama 3.3 70B)

`backend/llm.py` uses the Groq async SDK with `llama-3.3-70b-versatile` for two jobs. On user creation it asks the model for a structured JSON baseline based on role/department/access (expected hours, data ranges, endpoints, device type, API rates), which seeds the scoring baseline. On termination it asks the model for a sub-150-word incident report built from the z-scores, the baseline, and the triggered flags. Both paths fall back to deterministic defaults when no `GROQ_API_KEY` is set, so the project runs offline.

### 7. The dashboard and simulator

The React app (`frontend/`) connects to the WebSocket via a `useWebSocket` hook and renders a live `RiskGauge`, a `SignalHeatmap` of per-dimension anomalies, a sessions page, and an incident log fed by the LLM narratives. The `AttackSimulator` panel hits `POST /api/demo/simulate/{scenario}` to push crafted signal sets through the real pipeline — including a `full_attack` scenario that escalates across five steps with a few seconds between each, so you can watch the gauge climb and the session get terminated in real time. There are also standalone static demo pages (`static/login.html`, `static/dashboard.html`) for a no-build walkthrough.

## Results / Highlights

- **Scoring calibrated against scripted scenarios** — Normal lands at ~4–10, Country Change ~25–40, Rapid Export ~60–80, and Stolen Token 85+, mapping cleanly onto the allow / MFA / terminate tiers.
- **Correct WebCrypto → DER ECDSA verification** — the P1363 `r‖s` to DER conversion is the non-trivial bit that most browser-to-Python signing implementations get wrong; this one handles it.
- **Real device-hijack rejection** — a copied cookie used from a second browser fails on a public-key mismatch, not just on the cookie value.
- **Roughly 1,200 LOC of Python backend + scripts and ~720 LOC of frontend, plus a 262-LOC zero-dependency browser SDK.**
- Built and documented as the **AlphaQ / HTF hackathon** submission (slide decks and build plan included in `Docs/`).

## Tech Stack

- **Language(s):** Python, JavaScript (JSX), HTML, CSS
- **Frameworks / libraries:** FastAPI, Starlette middleware, SQLModel, Pydantic, Uvicorn (backend); React 19, Vite, Tailwind CSS 4, Recharts, Heroicons (frontend)
- **Data / ML:** scikit-learn, NumPy; custom weighted z-score risk engine; Groq SDK with Llama 3.3 70B Versatile
- **Security / crypto:** Web Crypto API (ECDSA P-256), IndexedDB key storage, Python `cryptography` (SHA-256 signature verification), canvas device fingerprinting
- **Infra / services:** Redis (async, sessions + scores + pubkeys), SQLite, Docker Compose (Redis container)

## Getting Started

### Prerequisites

- Python 3.10+ and `pip`
- Node.js 18+ and `npm` (for the dashboard)
- Docker (for the Redis container) — or a local Redis on `localhost:6379`
- Optional: a Groq API key for the LLM baseline/narrative features

### Installation

```bash
git clone https://github.com/DCode-v05/ZeroWatch.git
cd ZeroWatch

# Start Redis
docker compose -f Code/docker-compose.yml up -d

# Backend dependencies
pip install -r Code/requirements.txt
```

Create `Code/.env` (LLM features are optional and degrade gracefully without a key):

```
GROQ_API_KEY=your_groq_api_key_here
REDIS_URL=redis://localhost:6379
```

### Running

```bash
# Backend (from the Code/ directory)
cd Code
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (in a second terminal)
cd Code/frontend
npm install
npm run dev
```

The dashboard runs at `http://localhost:5173` and the API at `http://localhost:8000` (interactive docs at `/docs`).

## Usage

1. Open the dashboard, then use the **Attack Simulator** panel to fire a scenario (Normal, Country Change, Stolen Token, Rapid Export, or Full Attack).
2. Watch the **Risk Gauge** update live as the worker scores incoming signals, and the **Signal Heatmap** light up the dimensions that are anomalous.
3. Check the **Sessions** page for active sessions and their scores, and **Incidents** for the LLM-written report once a session is terminated.

You can also drive it straight from the API:

- `POST /api/users` — create a user (triggers LLM baseline generation)
- `POST /api/auth/login` — start a session
- `POST /api/auth/register-device` — register the browser's ECDSA public key
- `POST /api/signals` — submit a batch of behavioral signals
- `POST /api/demo/simulate/{scenario}` — trigger an attack scenario
- `GET /api/sessions` / `GET /api/incidents` — list sessions and incidents
- `GET /ws/risk` — WebSocket stream of live scores and incident events

The protected `/app/*` routes (dashboard, transfer, admin, export) require valid signature headers — hit them without the SDK running and the middleware returns `missing_signature`.

## Project Structure

```
ZeroWatch/
├── Code/
│   ├── backend/
│   │   ├── main.py            # FastAPI app: routes, WebSocket, demo endpoints, lifespan
│   │   ├── risk_engine.py     # Weighted z-score scoring + UserBaseline
│   │   ├── middleware.py      # ECDSA device-binding + tiered risk enforcement
│   │   ├── ecdsa_verify.py    # WebCrypto P1363 -> DER signature verification
│   │   ├── signal_worker.py   # Background asyncio queue consumer
│   │   ├── session_store.py   # Redis ops (sessions, scores, pubkeys, baselines)
│   │   ├── llm.py             # Groq/Llama baseline synthesis + incident narration
│   │   ├── models.py          # SQLModel tables (User, Session, Incident, SignalEvent)
│   │   ├── config.py          # Env/config loader
│   │   └── demo_app.py        # Demo app entry point
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── pages/         # Dashboard, Sessions, Incidents
│   │   │   ├── components/    # RiskGauge, SignalHeatmap, IncidentCard, AttackSimulator
│   │   │   └── hooks/         # useWebSocket
│   │   ├── package.json       # React 19, Vite, Tailwind 4, Recharts
│   │   └── vite.config.js
│   ├── sdk/
│   │   └── zw-sdk.js          # Browser SDK: ECDSA keys, fingerprint, fetch signing
│   ├── scripts/
│   │   ├── seed_baseline.py   # Seed user baselines
│   │   ├── demo_attack.py     # Script-based attack run
│   │   └── train_model.py     # Model training utility
│   ├── static/                # No-build HTML demo pages + SDK copy
│   ├── docker-compose.yml     # Redis container
│   └── requirements.txt
├── Docs/                      # AlphaQ / HTF slide decks + build plan (PDF/PPTX)
└── README.md
```

---

## Contact

<table>
  <tr><td><b>Portfolio:</b> <a href="https://www.denistan.me">Denistan</a></td><td><b>LinkedIn:</b> <a href="https://www.linkedin.com/in/denistanb">denistanb</a></td></tr>
  <tr><td><b>GitHub:</b> <a href="https://github.com/DCode-v05">DCode-v05</a></td><td><b>LeetCode:</b> <a href="https://leetcode.com/u/Denistan_B">Denistan_B</a></td></tr>
  <tr><td colspan="2" align="center"><b>Email:</b> <a href="mailto:denistanb05@gmail.com">denistanb05@gmail.com</a></td></tr>
</table>

Made with ❤️ by **Denistan B**
