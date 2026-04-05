# ZeroWatch

## Project Description
ZeroWatch is a real-time, AI-powered Zero Trust session monitoring platform that continuously evaluates user behavior to detect compromised sessions, insider threats, and token hijacking. It combines behavioral biometrics, ECDSA device binding, and LLM-driven risk scoring to enforce adaptive access control — going beyond traditional authentication by validating *who is using* the session, not just *who logged in*.

---

## Project Details

### Problem Statement
Traditional session security relies on static tokens (cookies, JWTs) that, once stolen, grant full access to an attacker. Insider threats and session hijacking go undetected until damage is done. ZeroWatch solves this by continuously scoring every active session against a behavioral baseline, detecting anomalies in real time, and automatically enforcing access decisions (allow, step-up MFA, or terminate).

### Architecture Overview
- **Behavioral Risk Engine:** Computes a 0–100 risk score per session using weighted z-score anomaly detection across 7 signal dimensions: IP geolocation, device fingerprint, data volume, API call rate, login hour, mouse velocity, and typing speed (WPM).
- **ECDSA Device Binding:** Each browser generates a non-extractable ECDSA P-256 key pair stored in IndexedDB. Every request is cryptographically signed, binding the session to the original device — stolen cookies alone are useless.
- **LLM Integration (Groq/Llama 3.3):** Generates role-based behavioral baselines for new users and produces plain-English incident narratives when sessions are terminated.
- **Real-Time Pipeline:** Signals are collected by the browser SDK every 2 seconds, queued in-memory (AsyncIO queue), scored by the risk engine, and broadcast to the dashboard via WebSocket.
- **Adaptive Middleware:** Enforces three tiers — score 0–30: allow, 31–70: require MFA for sensitive endpoints, 71+: terminate session immediately.

### Signal Dimensions & Weights
| Signal            | Weight | Detection                     |
|-------------------|--------|-------------------------------|
| IP Country        | 25%    | Unknown geolocation           |
| Device Fingerprint| 20%    | Unregistered device           |
| Data Volume (MB)  | 15%    | Abnormal data export          |
| API Call Rate     | 12%    | Excessive API usage           |
| Login Hour        | 10%    | Off-hours access              |
| Mouse Velocity    | 10%    | Bot-like or absent movement   |
| Typing Speed (WPM)| 8%    | Anomalous typing patterns     |

### Demo Scenarios
The platform includes built-in attack simulations:
- **Normal:** Baseline-consistent behavior (score 4–10)
- **Country Change:** Login from unexpected geolocation (score 25–40)
- **Stolen Token:** Unknown device + off-hours + zero biometrics (score 85+)
- **Rapid Export:** Massive data exfiltration attempt (score 60–80)
- **Full Attack:** Multi-step escalation from normal to full compromise

### Web Application
The React dashboard provides:
- Live risk score gauge with real-time WebSocket updates
- Signal heatmap showing per-dimension anomaly breakdown
- Active sessions list with risk scores
- Incident log with LLM-generated narratives
- Attack simulator panel to trigger demo scenarios

---

## Tech Stack
- **Backend:** Python 3.x, FastAPI, SQLModel (SQLite), Redis (async), Pydantic
- **Frontend:** React 19, Vite, Tailwind CSS 4, Recharts
- **AI/LLM:** Groq SDK, Llama 3.3 70B Versatile
- **Security:** Web Crypto API (ECDSA P-256), IndexedDB key storage
- **Infrastructure:** Docker Compose (Redis), uvicorn

---

## Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/DCode-v05/ZeroWatch.git
cd ZeroWatch
```

### 2. Start Redis
```bash
docker compose -f Code/docker-compose.yml up -d
```

### 3. Install backend dependencies
```bash
pip install fastapi uvicorn sqlmodel redis pydantic python-dotenv groq
```

### 4. Configure environment
Create a `Code/.env` file:
```
GROQ_API_KEY=your_groq_api_key_here
REDIS_URL=redis://localhost:6379
```
> Note: The LLM features (baseline generation, incident narration) require a valid Groq API key. The system falls back to defaults without one.

### 5. Run the backend
```bash
cd Code
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Run the frontend
```bash
cd Code/frontend
npm install
npm run dev
```
The dashboard will be available at `http://localhost:5173`.

---

## Usage
- Open the dashboard and use the **Attack Simulator** to trigger demo scenarios.
- Watch the **Risk Gauge** update in real time as signals are processed.
- Navigate to **Sessions** to see active sessions and their risk scores.
- Navigate to **Incidents** to view LLM-generated incident narratives.
- Use the API directly:
  - `POST /api/users` — Create a user with LLM-generated baseline
  - `POST /api/auth/login` — Start a session
  - `POST /api/demo/simulate/{scenario}` — Trigger attack simulations
  - `GET /ws/risk` — WebSocket for live risk updates

---

## Project Structure
```
ZeroWatch/
|
├── Code/
│   ├── docker-compose.yml          # Redis container
│   ├── backend/
│   │   ├── main.py                 # FastAPI app, routes, WebSocket, demo endpoints
│   │   ├── risk_engine.py          # Behavioral risk scoring (z-score based)
│   │   ├── signal_worker.py        # Background signal queue consumer
│   │   ├── middleware.py           # ECDSA verification + risk enforcement
│   │   ├── llm.py                  # Groq/Llama integration (baselines, narratives)
│   │   ├── models.py              # SQLModel database models
│   │   ├── session_store.py       # Redis session/score/pubkey operations
│   │   ├── config.py              # Environment config loader
│   │   ├── ecdsa_verify.py        # Server-side ECDSA signature verification
│   │   └── demo_app.py            # Demo application entry point
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── App.jsx            # Tab navigation (Dashboard, Sessions, Incidents)
│   │   │   ├── pages/
│   │   │   │   ├── Dashboard.jsx  # Main dashboard with risk gauge + simulator
│   │   │   │   ├── Sessions.jsx   # Active sessions list
│   │   │   │   └── Incidents.jsx  # Incident log viewer
│   │   │   ├── components/
│   │   │   │   ├── RiskGauge.jsx      # Animated risk score display
│   │   │   │   ├── SignalHeatmap.jsx  # Per-signal anomaly visualization
│   │   │   │   ├── IncidentCard.jsx   # Incident narrative card
│   │   │   │   └── AttackSimulator.jsx # Demo attack trigger panel
│   │   │   └── hooks/
│   │   │       └── useWebSocket.js    # WebSocket connection hook
│   │   ├── index.html
│   │   ├── package.json
│   │   └── vite.config.js
│   ├── sdk/
│   │   └── zw-sdk.js              # Browser SDK (ECDSA, fingerprint, signal collection)
│   └── scripts/
│       ├── seed_baseline.py       # Seed user baselines
│       ├── demo_attack.py         # Script-based attack simulation
│       └── train_model.py         # Model training utility
├── Docs/
│   ├── AlphaQ.pdf                 # Project documentation
│   ├── AlphaQ_HTF.pptx           # Hackathon presentation
│   ├── AlphaQ_HTF_Final.pptx     # Final presentation
│   ├── AlphaQ_v2.pdf             # Updated documentation
│   └── ZeroWatch_BuildPlan.pdf   # Build plan document
└── README.md                      # Project documentation
```

---

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository
2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add your feature"
   ```
4. Push to your branch:
   ```bash
   git push origin feature/your-feature
   ```
5. Open a pull request describing your changes.

---

## Contact
- **GitHub:** [DCode-v05](https://github.com/DCode-v05)
- **Email:** denistanb05@gmail.com
