# ZeroWatch

**Zero Trust session monitoring that scores every active session in real time and decides whether to allow it, force step-up MFA, or kill it.**

![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![SQLModel](https://img.shields.io/badge/SQLModel-7E56C2?style=flat&logo=sqlite&logoColor=white) ![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat&logo=redis&logoColor=white) ![React](https://img.shields.io/badge/React_19-61DAFB?style=flat&logo=react&logoColor=black) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white) ![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS_4-06B6D4?style=flat&logo=tailwindcss&logoColor=white) ![Groq](https://img.shields.io/badge/Groq_Llama_3.3-F55036?style=flat&logo=meta&logoColor=white) ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)

## Overview

Most session security stops at the login screen. Once you have a valid cookie or JWT, the server trusts you for the rest of the session, which is why stolen tokens, hijacked cookies and insider misuse work so well. The login was legitimate, and what happened afterward isn't checked.

ZeroWatch checks what happens afterward. It's a Zero Trust session monitor that keeps scoring every active session against a behavioural baseline and asks a different question than the login form: not *who logged in*, but *who is using this session right now*. When the behaviour stops matching the person, the session is flagged, stepped up to MFA, or terminated automatically.

It has three main pieces: a behavioural risk engine that compares live signals to a per-user baseline, ECDSA P-256 device binding so a stolen cookie is useless from another machine, and a Groq/Llama 3.3 layer that writes the incident report when something goes wrong. It comes with a React dashboard and a built-in attack simulator, so you can watch a session escalate from "normal" to "terminated". I built it with my team (AlphaQ) for the HackToFuture hackathon. It's a prototype: the baselines are synthetic or LLM-generated rather than learned from real users, and the signal weights are hand-set.

## Key Features

- **Continuous session scoring**: every session gets a live 0–100 risk score, recomputed as new behavioural signals arrive (roughly every 2 seconds from the browser SDK).
- **Seven-signal behavioural engine**: weighted z-score anomaly detection across IP country, device fingerprint, data volume, API call rate, login hour, mouse velocity and typing speed (WPM).
- **ECDSA P-256 device binding**: the browser generates a non-extractable signing key, stored in IndexedDB, and signs every request. A cookie copied to a different browser carries a different public key, so the server rejects it as a hijack.
- **Adaptive three-tier enforcement**: score 0–30 allows the request, 31–70 forces MFA on sensitive endpoints, 71+ terminates the session.
- **Signature freshness window**: requests carry a timestamp, and anything more than 30 seconds off is rejected, which blocks replayed signatures.
- **LLM behavioural baselines**: when a user is created, Groq/Llama 3.3 generates a role- and department-aware baseline profile (expected hours, data ranges, API rates, device type).
- **LLM incident narratives**: when a session is terminated, the model writes a short plain-English report of what happened and why, instead of dumping raw z-scores.
- **LLM fallback**: with no Groq key, the system uses fixed baselines and template narratives, so the demo still runs.
- **Built-in attack simulator**: five scenarios (Normal, Country Change, Stolen Token, Rapid Export, and a multi-step Full Attack escalation) push synthetic signals through the real pipeline.
- **Real-time dashboard**: a React 19 + Recharts UI with a live risk gauge, per-signal anomaly heatmap, active sessions list and incident log, all driven over WebSocket.
- **Dependency-free browser SDK**: a single IIFE that handles key management, canvas device fingerprinting, keystroke and mouse capture, signal batching, and a fetch interceptor that signs outgoing requests.
- **Protected mock app**: `/app/*` endpoints (dashboard, transfer, admin, export) stand in for a banking-style application, so the enforcement tiers have something to protect.

## How It Works

The system is a FastAPI backend, a Redis-backed real-time pipeline, a React dashboard and a browser SDK that runs inside the protected app. The flow is below.

### 1. Device binding (the SDK)

On first load, `Code/sdk/zw-sdk.js` generates an ECDSA P-256 key pair with the Web Crypto API. The private key is marked **non-extractable** and kept in IndexedDB, so scripts can't read it out. The raw public key is exported and registered with the server against the session (`POST /api/auth/register-device`).

From then on the SDK installs a `fetch` interceptor. Every outgoing request is signed with the device key and carries three headers: `x-zw-signature`, `x-zw-timestamp` and `x-zw-pubkey`. The SDK also builds a device fingerprint (canvas rendering plus environment components) and tracks keystrokes and mouse movement to derive typing speed and pointer velocity.

### 2. Server-side signature verification

This part is easy to get wrong. Web Crypto emits ECDSA signatures in IEEE P1363 format, a raw 64-byte `r‖s` concatenation, but Python's `cryptography` library expects DER. `backend/ecdsa_verify.py` decodes the 65-byte uncompressed public point, splits the signature into two 32-byte halves, re-encodes them as a DER signature with `encode_dss_signature` and verifies against SHA-256.

The middleware (`backend/middleware.py`) enforces this on every protected route. Missing signature headers return `401 missing_signature` (a cookie alone is not enough), a timestamp outside the 30-second window returns `401 signature_expired`, and a public key that doesn't match the one registered at login returns `401 session_hijack`. That last check is the anti-hijack core: a stolen cookie used from a second browser presents a different device key, so it fails.

### 3. The behavioural risk engine

`backend/risk_engine.py` scores a session by comparing live signals to a `UserBaseline`. Each signal contributes an anomaly value:

- **Categorical signals** (IP country, device fingerprint) score `0.0` if the value is known or registered, and a maximum anomaly of `5.0` if it isn't.
- **Numerical signals** (data MB, API calls, login hour, mouse velocity, WPM) use the absolute z-score against the baseline mean and standard deviation.

The anomalies are combined with fixed weights, multiplied by 20 and clamped to 0–100:

| Signal | Weight | What it catches |
|---|---|---|
| IP country | 25% | Login from an unexpected geolocation |
| Device fingerprint | 20% | An unregistered device |
| Data volume (MB) | 15% | Abnormal data export / exfiltration |
| API call rate | 12% | Scripted or excessive API usage |
| Login hour | 10% | Off-hours access |
| Mouse velocity | 10% | Bot-like or absent pointer movement |
| Typing speed (WPM) | 8% | Anomalous or non-human typing |

### 4. The real-time pipeline

The SDK posts batched signals to `POST /api/signals`. There is no external broker: the backend uses an in-process `asyncio.Queue` as the signal bus. A background `signal_worker` task (started in the FastAPI lifespan) consumes the queue, runs each batch through the risk engine, writes the score to Redis and broadcasts the result to every connected dashboard over the `/ws/risk` WebSocket. Sessions, risk scores, registered public keys and baselines live in Redis (async client). Users, sessions, incidents and signal events are persisted in SQLite via SQLModel, in `~/zerowatch.db` (the path is hard-coded in `config.py`).

### 5. Enforcement

Enforcement happens in the same middleware, after the device check. It reads the current risk score from Redis and applies the tiers. At 71+ it deletes the session and starts an async task to narrate and broadcast the incident. At 31–70 it returns `202 mfa_required` for sensitive paths (`/app/transfer`, `/app/admin`, `/app/export`). At 0–30 it forwards the request and adds an `X-ZeroWatch-Score` header to the response.

### 6. The LLM layer (Groq / Llama 3.3 70B)

`backend/llm.py` uses the Groq async SDK with `llama-3.3-70b-versatile` for two jobs. On user creation it asks the model for a structured JSON baseline based on role, department and access (expected hours, data ranges, endpoints, device type, API rates), which seeds the scoring baseline. On termination it asks for a short incident report built from the z-scores, the baseline and the triggered flags. Both paths fall back to fixed defaults when no `GROQ_API_KEY` is set, so the project runs offline.

### 7. The dashboard and simulator

The React app (`Code/frontend/`) connects to the WebSocket through a `useWebSocket` hook and renders a live `RiskGauge`, a `SignalHeatmap` of per-signal anomalies, a sessions page and an incident log fed by the LLM narratives. The `AttackSimulator` panel calls `POST /api/demo/simulate/{scenario}` to push crafted signal sets through the real pipeline, including a `full_attack` scenario that escalates in steps with a few seconds between each, so you can watch the gauge climb and the session get terminated. There are also two plain static demo pages (`Code/static/login.html`, `Code/static/dashboard.html`) that need no build.

## Results / Highlights

- **Tiered enforcement end to end**: the simulator scenarios exercise the allow, MFA and terminate paths through the real middleware, Redis and WebSocket pipeline.
- **WebCrypto to DER ECDSA verification**: the P1363 `r‖s` to DER conversion is the non-trivial bit of browser-to-Python signing, and it is handled in `ecdsa_verify.py`.
- **Device-hijack rejection**: a copied cookie used from a second browser fails on a public-key mismatch, not just on the cookie value.
- Built with team **AlphaQ** for the **HackToFuture** hackathon. The slide decks and build plan are in `docs/`.
- The repo has no automated tests, and I haven't measured score ranges per scenario, so treat the simulator's expected scores as rough.

## Tech Stack

- **Language(s):** Python, JavaScript (JSX), HTML, CSS
- **Frameworks / libraries:** FastAPI, Starlette middleware, SQLModel, Pydantic, Uvicorn (backend); React 19, Vite, Tailwind CSS 4, Recharts, Heroicons (frontend)
- **Data / ML:** NumPy; a hand-written weighted z-score risk engine; Groq SDK with Llama 3.3 70B Versatile. scikit-learn is listed in `requirements.txt` only for `Code/scripts/train_model.py` (an Isolation Forest), which the scoring path doesn't use.
- **Security / crypto:** Web Crypto API (ECDSA P-256), IndexedDB key storage, Python `cryptography` (SHA-256 signature verification), canvas device fingerprinting
- **Infra / services:** Redis (async, sessions + scores + public keys), SQLite, Docker Compose (Redis container)

## Getting Started

### Prerequisites

- Python 3.10+ and `pip`
- Node.js 18+ and `npm` (for the dashboard)
- Docker (for the Redis container), or a local Redis on `localhost:6379`
- Optional: a Groq API key for the LLM baseline and narrative features

### Installation

```bash
git clone https://github.com/DCode-v05/ZeroWatch.git
cd ZeroWatch

# Start Redis
docker compose -f Code/docker-compose.yml up -d

# Backend dependencies
pip install -r Code/requirements.txt
```

Optionally create `Code/.env` (LLM features degrade gracefully without a key):

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

The dashboard runs at `http://localhost:5173` (Vite proxies `/api` and `/ws` to port 8000) and the API at `http://localhost:8000`, with interactive docs at `/docs`.

## Usage

1. Open the dashboard, then use the **Attack Simulator** panel to fire a scenario (Normal, Country Change, Stolen Token, Rapid Export or Full Attack).
2. Watch the **Risk Gauge** update live as the worker scores incoming signals, and the **Signal Heatmap** light up the anomalous signals.
3. Check the **Sessions** page for active sessions and their scores, and **Incidents** for the LLM-written report once a session is terminated.

`Code/scripts/seed_baseline.py` seeds demo baselines in Redis. To run a scenario from the command line instead, use `python Code/scripts/demo_attack.py --scenario stolen_token`.

You can also drive it straight from the API:

- `POST /api/users`: create a user (triggers LLM baseline generation)
- `POST /api/auth/login`, `POST /api/demo/login`: start a session
- `POST /api/auth/register-device`: register the browser's ECDSA public key
- `POST /api/signals`: submit a batch of behavioural signals
- `POST /api/demo/simulate/{scenario}`: trigger an attack scenario
- `GET /api/sessions` / `GET /api/incidents`: list sessions and incidents
- `GET /ws/risk`: WebSocket stream of live scores and incident events

The protected `/app/*` routes (dashboard, transfer, admin, export) require valid signature headers. Hit them without the SDK running and the middleware returns `missing_signature`.

Note that `Code/sdk/zw-sdk.js` and `Code/static/zw-sdk.js` are two copies of the SDK and they differ.

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
│   │   └── train_model.py     # Isolation Forest training utility (not used by scoring)
│   ├── static/                # No-build HTML demo pages + a separate SDK copy
│   ├── docker-compose.yml     # Redis container
│   └── requirements.txt
├── docs/                      # AlphaQ / HackToFuture slide decks + build plan (PDF/PPTX)
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
