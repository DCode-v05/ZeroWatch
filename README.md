# ZeroWatch

A Zero Trust session monitor. It keeps scoring every active session against a per-user behavioural baseline and, depending on the score, lets requests through, forces MFA, or kills the session. Requests are also bound to the browser that logged in, so a stolen cookie is useless from another machine.

Most session security stops at login. After that a valid cookie or JWT is trusted until it expires, which is why stolen tokens and hijacked sessions work. ZeroWatch asks who is using the session right now. I built it with my team (AlphaQ) for the HackToFuture hackathon.

## How it works

**Device binding.** `Code/sdk/zw-sdk.js` generates an ECDSA P-256 key pair with Web Crypto. The private key is non-extractable and kept in IndexedDB. The public key is registered with the server for the session (`POST /api/auth/register-device`). A `fetch` interceptor then signs every request and sends `x-zw-signature`, `x-zw-timestamp` and `x-zw-pubkey`. The SDK also builds a canvas-based device fingerprint and measures typing speed and mouse velocity.

**Signature check.** Web Crypto produces raw 64-byte `r||s` (P1363) signatures and Python's `cryptography` wants DER, so `backend/ecdsa_verify.py` converts between them before verifying SHA-256. `backend/middleware.py` rejects a request with `missing_signature` if the headers are absent, `signature_expired` if the timestamp is more than 30 seconds off, and `session_hijack` if the public key differs from the one registered at login.

**Risk engine.** `backend/risk_engine.py` compares seven live signals with the user's baseline. Categorical signals (IP country, device fingerprint) score 0 if known and 5 if not. Numerical signals use the absolute z-score. The anomalies are weighted, multiplied by 20 and clamped to 0 to 100.

| Signal | Weight |
|---|---|
| IP country | 25% |
| Device fingerprint | 20% |
| Data volume (MB) | 15% |
| API call rate | 12% |
| Login hour | 10% |
| Mouse velocity | 10% |
| Typing speed (WPM) | 8% |

**Pipeline.** The SDK posts batched signals to `POST /api/signals`. They go onto an in-process `asyncio.Queue`, and a background worker (`signal_worker.py`) scores each batch, stores the score in Redis and broadcasts it to dashboards on the `/ws/risk` WebSocket. Sessions, scores, public keys and baselines are in Redis. Users, sessions, incidents and signal events are in SQLite through SQLModel (`~/zerowatch.db`).

**Enforcement.** After the device check, the middleware reads the session's score. 71 or more deletes the session and starts an async task that writes and broadcasts an incident. 31 to 70 returns `202 mfa_required` on `/app/transfer`, `/app/admin` and `/app/export`. 30 or less passes the request through with an `X-ZeroWatch-Score` header.

**LLM layer.** `backend/llm.py` uses Groq (`llama-3.3-70b-versatile`) for two things: generating a baseline profile from a user's role and department when the user is created, and writing a short incident report when a session is terminated. Without `GROQ_API_KEY` it uses fixed baselines and template text.

**Dashboard and simulator.** The React 19 app shows a risk gauge, a per-signal heatmap, active sessions and incidents. The Attack Simulator calls `POST /api/demo/simulate/{scenario}` with one of five scenarios (normal, country change, stolen token, rapid export, full attack) and runs them through the real pipeline. `/app/*` are mock protected endpoints for the enforcement tiers to guard. `Code/static/` has two plain HTML pages (`login.html`, `dashboard.html`) that need no build.

## Tech stack

- Backend: Python, FastAPI, SQLModel, Redis, `cryptography`, Groq SDK
- Frontend: React 19, Vite, Tailwind CSS 4, Recharts
- Browser: Web Crypto (ECDSA P-256), IndexedDB, vanilla JS SDK
- Infra: Docker Compose (Redis only), SQLite

## Setup

Requirements: Python 3.10+, Node 18+, Docker (or a local Redis on port 6379).

```bash
docker compose -f Code/docker-compose.yml up -d
pip install -r Code/requirements.txt
```

Optionally create `Code/.env`:

```
GROQ_API_KEY=your_groq_api_key_here
REDIS_URL=redis://localhost:6379
```

Run the backend from `Code/`, then the dashboard in a second terminal:

```bash
cd Code
uvicorn backend.main:app --reload --port 8000

cd Code/frontend
npm install
npm run dev     # http://localhost:5173, proxies /api and /ws to :8000
```

API docs are at http://localhost:8000/docs. `Code/scripts/seed_baseline.py` seeds demo baselines in Redis and `python Code/scripts/demo_attack.py --scenario stolen_token` runs a scenario from the command line.

## API

- `POST /api/users`: create a user (generates the baseline)
- `POST /api/auth/login`, `POST /api/demo/login`: start a session
- `POST /api/auth/register-device`: register the browser's public key
- `POST /api/signals`: submit behavioural signals
- `POST /api/demo/simulate/{scenario}`: run an attack scenario
- `GET /api/sessions`, `GET /api/incidents`
- `GET /ws/risk`: live scores and incidents
- `GET /app/dashboard|transfer|admin|export`: protected mock endpoints

## Project structure

```
Code/
  backend/     FastAPI app, risk engine, middleware, ECDSA verification, signal worker, Redis store, LLM
  frontend/    React dashboard (pages, components, useWebSocket hook)
  sdk/         browser SDK (zw-sdk.js)
  scripts/     seed_baseline.py, demo_attack.py, train_model.py
  static/      plain HTML demo pages and an SDK copy
  docker-compose.yml
docs/          hackathon slide decks (AlphaQ) and the build plan
```

## Limitations

- It is a hackathon prototype. Baselines are synthetic or LLM-generated, not learned from real users, and the weights are hand-set.
- `scikit-learn` is in `requirements.txt` for `scripts/train_model.py`, which trains an Isolation Forest, but the scoring path does not use it.
- The SDK exists twice (`Code/sdk/zw-sdk.js` and `Code/static/zw-sdk.js`) and the two copies differ.
- No automated tests.
