---
title: PhantomWALL
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# PhantomWall

PhantomWall is a distributed browser privacy defense system built with a Chrome Manifest V3 extension and a FastAPI backend. This version supports hosted multi-user analytics: each browser install can register with your backend, send authenticated tracker events, and appear in a central admin dashboard with full script block history and threat intelligence.

## Features

- Chrome MV3 extension with `declarativeNetRequest` tracker blocking
- Local extension analytics for offline-first behavior
- Options page for remote backend setup and install registration
- Authenticated install telemetry via per-install API tokens (both **blocked** and **observed** requests)
- FastAPI backend with PostgreSQL and SQLite support
- ML-Based Tracker Classification using XGBoost (classifying events into Fingerprinting, Advertising, Analytics, Suspicious, or Safe based on entropy, URL patterns, frequency, and third-party behavior)
- **Script Block History** — full paginated, searchable, filterable log of every classified request with drill-down detail drawers
- **Threat Intelligence Dashboard** — interactive Chart.js visualizations (threat distribution, blocked over time, risk score distribution, top domains, request types)
- **Domain Reputation Engine** — aggregated per-domain risk scores, block counts, and classification tracking
- **Explainable AI (XAI)** — SHAP-based feature importance with rule-based heuristic fallback for human-readable model decision summaries
- **Dynamic Risk Scoring** — per-request risk scores (0–100) computed as `category_weight × confidence × 100`
- **Auto-Migration** — lightweight startup schema migration that adds missing columns to existing PostgreSQL tables without Alembic
- **30-Day Data Retention** — automatic cleanup of raw telemetry logs on startup, preserving domain reputation aggregates
- Multi-user dashboard with registration, per-user scoped data, and admin/user JWT roles
- Admin login for the hosted analytics dashboard with classification breakdowns
- Real-time dashboard refresh through WebSockets
- Dockerized backend and database stack
- Full GitHub Actions CI/CD Pipeline (Automated testing, GHCR build, and Hugging Face deployment)

## Project structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   `-- routes/
|   |   |       |-- analytics.py      # Stats, history, reputation, track-event endpoints
|   |   |       |-- auth.py           # Login, register, /auth/me
|   |   |       |-- installs.py       # Install registration and listing
|   |   |       `-- live.py           # WebSocket live stream
|   |   |-- core/
|   |   |   |-- config.py             # Pydantic settings
|   |   |   |-- dependencies.py       # FastAPI dependency injection
|   |   |   `-- security.py           # PBKDF2 password hashing
|   |   |-- models/
|   |   |   `-- analytics.py          # User, Install, TrackerEventRecord, BlockedRequest, DomainReputation
|   |   |-- schemas/
|   |   |-- services/
|   |   |   |-- analytics.py          # Core analytics queries and ingestion pipeline
|   |   |   |-- auto_migrate.py       # Startup schema migration utility
|   |   |   |-- classifier.py         # Legacy rule-based classifier
|   |   |   |-- explanation_service.py # SHAP / heuristic XAI explanations
|   |   |   |-- retention.py          # 30-day data retention cleanup
|   |   |   `-- websocket_manager.py  # WebSocket broadcast manager
|   |   `-- static/
|   |       |-- dashboard.html
|   |       |-- dashboard.js
|   |       `-- dashboard.css
|   |-- feature_engineering/          # URL feature extraction pipeline
|   |-- inference/                    # XGBoost model prediction service
|   |-- models/                       # Trained ML model artifacts (.pkl, .json)
|   |-- training/                     # Model training pipeline
|   |-- migrations/                   # Raw SQL migration scripts
|   |-- tests/                        # Pytest test suite
|   |-- Dockerfile
|   `-- requirements.txt
|-- extension/
|   |-- background.js                 # MV3 service worker with telemetry pipeline
|   |-- manifest.json
|   |-- options.html / options.js
|   |-- popup.html / popup.js
|   |-- rules.json                    # declarativeNetRequest tracker rules
|   `-- styles.css
`-- docker-compose.yml
```

## Architecture

### Extension

- Intercepts outgoing requests in `background.js`
- Detects third-party tracker requests against `rules.json`
- Blocks matching requests through `declarativeNetRequest`
- Captures metadata for both **blocked** and **observed** requests (URL, domain, request type, tab URL, referrer, third-party flag)
- Stores local counts in `chrome.storage.local`
- Lets each user register the install from `options.html`
- Sends authenticated tracker events with `X-PhantomWall-Install-Token`

### Backend

- `POST /installs/register` creates a new install identity from an invite code
- `POST /track-event` ingests telemetry, runs ML classification, computes risk scores, generates XAI explanations, and updates domain reputation
- `POST /auth/login` issues a JWT dashboard token (admin or user scope)
- `POST /auth/register` creates a new dashboard user account
- `GET /stats` returns aggregated or per-install analytics (scoped by user for non-admins)
- `GET /installs` lists registered installs
- `GET /history` returns paginated, filterable script block history with classification, confidence, and risk scores
- `GET /history/stats` returns aggregated threat distribution, timeline series, request type breakdown, and risk distribution
- `GET /history/top-domains` returns top blocked domains by count
- `GET /reputation` returns domain reputation records
- `GET /reputation/top-risk` returns highest-risk domains
- `POST /admin/cleanup` triggers manual 30-day retention cleanup (admin-only)
- `GET /dashboard` serves the protected admin dashboard shell
- `WS /ws/live` streams authenticated dashboard update signals

## Quick start

### 1. Start the backend and database

```bash
docker compose up --build
```

Services:

- API: `http://localhost:8000`
- Dashboard: `http://localhost:8000/dashboard`
- PostgreSQL: `localhost:5432`

### 2. Load the extension

1. Open `chrome://extensions`
2. Enable `Developer mode`
3. Click `Load unpacked`
4. Select the [extension](/d:/PhantomWALL/extension:1) folder

### 3. Configure the extension

The options page opens automatically on first install. If needed, reopen it from the popup.

Use these local values:

- Backend URL: `http://localhost:8000`
- Install name: anything descriptive, like `Tanmay Laptop`
- Invite code: `phantomwall-invite`

Click `Register install`.

### 4. Open the admin dashboard

Visit `http://localhost:8000/dashboard`

Default local admin credentials:

- Username: `admin`
- Password: `change-this-password`

### 5. Generate telemetry

- Visit websites that load common trackers
- Click the PhantomWall popup to confirm the install is linked
- Watch the hosted dashboard update with blocked domains and recent events

## Environment variables

See [backend/.env.example](/d:/PhantomWALL/backend/.env.example:1).

Most important values:

- `PHANTOMWALL_DATABASE_URL`
- `PHANTOMWALL_PUBLIC_BACKEND_URL`
- `PHANTOMWALL_ADMIN_USERNAME`
- `PHANTOMWALL_ADMIN_PASSWORD`
- `PHANTOMWALL_JWT_SECRET_KEY`
- `PHANTOMWALL_REGISTRATION_INVITE_CODE`

## Local backend without Docker

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You will also need a running PostgreSQL instance and a valid `PHANTOMWALL_DATABASE_URL`.

## API reference

### `POST /installs/register`

Public endpoint used by the extension setup page.

Example body:

```json
{
  "display_name": "Tanmay Laptop",
  "invite_code": "phantomwall-invite",
  "extension_version": "1.0.0",
  "browser_name": "Chrome"
}
```

### `POST /track-event`

Requires:

- header: `X-PhantomWall-Install-Token`

Example body:

```json
{
  "tracker_domain": "google-analytics.com",
  "url": "https://www.google-analytics.com/g/collect?v=2",
  "page_origin": "https://example.com",
  "request_type": "xmlhttprequest",
  "source": "extension",
  "blocked": true,
  "third_party": true
}
```

### `POST /auth/login`

Admin login for the dashboard.

```json
{
  "username": "admin",
  "password": "change-this-password"
}
```

### `GET /stats`

Requires:

- header: `Authorization: Bearer <admin-token>`

Optional query params:

- `install_id`
- `recent_limit`

### `GET /installs`

Returns registered installs for the dashboard filter and install cards.

### `GET /dashboard`

Serves the browser dashboard UI. The page itself is public, but the analytics data inside it requires admin login.

### `WS /ws/live`

Requires:

- query param: `token=<admin-jwt>`

The dashboard uses this to refresh live when new telemetry arrives.

## Sharing with friends

To share PhantomWall beyond local testing:

1. Deploy the backend to a public HTTPS domain
2. Set `PHANTOMWALL_PUBLIC_BACKEND_URL=https://your-domain`
3. Change the default admin password, JWT secret, and invite code
4. Publish the extension through the Chrome Web Store
5. Ask each friend to open the options page and register their install

For remote deployment, friends should use:

- Backend URL: your hosted HTTPS API URL
- Invite code: the one you configured on the server

## Sample tracker coverage

The extension ships with sample rules for:

- `google-analytics.com`
- `doubleclick.net`
- `googletagmanager.com`
- `facebook.com/tr`
- `connect.facebook.net`
- `ads-twitter.com`
- `bat.bing.com`
- `snap.licdn.com`

## ML-Based Tracker Classification

PhantomWall features a production **XGBoost Gradient Boosted Tree Classifier** (with Logistic Regression and Random Forest fallbacks) that runs on each incoming telemetry event. The classifier scores events using 9 extracted features:

1.  **Domain Entropy:** Shannon entropy of the domain name to detect random/algorithmically generated tracking subdomains.
2.  **URL Length:** Length of the request URL (scaled).
3.  **Parameter Count:** The number of query parameters passed in the request (scaled).
4.  **Request Frequency:** Live request rate (requests to the same domain by the same install in the last 5 minutes).
5.  **Third-Party Behavior:** Whether the request originates from a third-party context.
6.  **Fingerprinting Keywords:** Presence of fingerprinting vectors (e.g. `canvas`, `webgl`, `navigator`).
7.  **Advertising Keywords:** Presence of ad indicators (e.g. `ad`, `doubleclick`, `pixel`).
8.  **Analytics Keywords:** Presence of analytics vectors (e.g. `telemetry`, `ga.js`, `stats`).
9.  **General Tracker Keywords:** Presence of general tracking terms (e.g. `track`, `collect`, `log`).

Classification outputs one of: `Fingerprinting` (Orange), `Advertising` (Red), `Analytics` (Blue), `Suspicious` (Purple), or `Safe` (Green), rendered with high-contrast pills in the admin dashboard.

### Dynamic Risk Scoring

Each classified request receives a risk score (0–100) calculated as:

```
risk_score = category_weight × confidence × 100
```

Category weights: Safe (0.1), Analytics (0.4), Advertising (0.6), Fingerprinting (0.85), Suspicious (1.0).

### Explainable AI (XAI)

Every prediction includes a human-readable explanation generated by:
1.  **SHAP TreeExplainer** (when the `shap` package is available)
2.  **Rule-based heuristic fallback** that inspects feature values and identifies the top contributing indicators

Explanations are visible in the Threat Intelligence Detail drawer on the dashboard.

### Domain Reputation Engine

The backend maintains a `domain_reputation` table that aggregates per-domain statistics across all telemetry:
- Total times seen, times blocked
- Running average risk score
- Current classification and first/last seen timestamps

---

## Continuous Integration & Deployment (CI/CD)

The project includes a **GitHub Actions CI/CD Pipeline** defined in `.github/workflows/docker-publish.yml` with the following automated jobs:

1.  **Test Job (CI):** Installs Python dependencies and runs the workspace tests (`backend/tests/test_classifier.py` and `backend/tests/test_db_analytics.py`) using an in-memory SQLite database.
2.  **Build Job:** Compiles and publishes the backend Docker image to GitHub Container Registry (`ghcr.io`).
3.  **Deploy Job (CD):** Automatically deploys the backend codebase to Hugging Face Spaces.

### Deploying to Hugging Face Spaces via GitHub CD

1.  Create a **Docker** space on Hugging Face (choose the blank Docker SDK).
2.  In your GitHub repository, go to **Settings** -> **Secrets and variables** -> **Actions** and add these Secrets:
    *   `HF_TOKEN`: A Hugging Face write access token.
    *   `HF_SPACE_NAME`: Your Space name formatted as `username/space-name` (e.g. `tanzzz07/phantomwall`).
3.  In your Hugging Face Space settings, add your app environment variables:
    *   `PHANTOMWALL_DATABASE_URL`: `sqlite+aiosqlite:////app/data/phantomwall.db`
    *   `PHANTOMWALL_ADMIN_USERNAME`: (your dashboard username)
    *   `PHANTOMWALL_ADMIN_PASSWORD`: (your dashboard password)
    *   `PHANTOMWALL_JWT_SECRET_KEY`: (a secure random string)
    *   `PHANTOMWALL_REGISTRATION_INVITE_CODE`: (the code used by extensions to connect)
    *   `PHANTOMWALL_PUBLIC_BACKEND_URL`: `https://<your-username>-<your-space-name>.hf.space`

Whenever you push code changes to the `main` branch on GitHub, the pipeline runs the test suite, builds the container image, and pushes the code to Hugging Face, where it is instantly redeployed.

---

## Production notes

- Replace sample tracker rules with a maintained tracker intelligence source
- Put the backend behind HTTPS before sharing it
- Rotate the invite code and admin secrets before public rollout
- Consider minimizing or anonymizing stored page-level data if privacy requirements tighten
- The auto-migration utility handles column additions automatically; for destructive schema changes, use manual SQL migrations in `backend/migrations/`
- Raw telemetry is automatically purged after 30 days; domain reputation aggregates are preserved indefinitely
- The ML model artifacts in `backend/models/` are required for inference; retrain with the training pipeline if the feature schema changes
