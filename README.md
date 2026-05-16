# PhantomWall

PhantomWall is a distributed browser privacy defense system built with a Chrome Manifest V3 extension and a FastAPI backend. This version supports hosted multi-user analytics: each browser install can register with your backend, send authenticated tracker events, and appear in a central admin dashboard.

## Features

- Chrome MV3 extension with `declarativeNetRequest` tracker blocking
- Local extension analytics for offline-first behavior
- Options page for remote backend setup and install registration
- Authenticated install telemetry via per-install API tokens
- FastAPI backend with PostgreSQL persistence
- Admin login for the hosted analytics dashboard
- Real-time dashboard refresh through WebSockets
- Dockerized backend and database stack

## Project structure

```text
.
|-- backend/
|   |-- app/
|   |   |-- api/
|   |   |   `-- routes/
|   |   |-- core/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- services/
|   |   `-- static/
|   |-- Dockerfile
|   `-- requirements.txt
|-- extension/
|   |-- background.js
|   |-- manifest.json
|   |-- options.html
|   |-- options.js
|   |-- options.css
|   |-- popup.html
|   |-- popup.js
|   |-- rules.json
|   `-- styles.css
`-- docker-compose.yml
```

## Architecture

### Extension

- Intercepts outgoing requests in `background.js`
- Detects third-party tracker requests against `rules.json`
- Blocks matching requests through `declarativeNetRequest`
- Stores local counts in `chrome.storage.local`
- Lets each user register the install from `options.html`
- Sends authenticated tracker events with `X-PhantomWall-Install-Token`

### Backend

- `POST /installs/register` creates a new install identity from an invite code
- `POST /track-event` ingests telemetry from a registered extension
- `POST /auth/login` issues an admin dashboard token
- `GET /stats` returns aggregated or per-install analytics
- `GET /installs` lists all registered installs
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

## Production notes

- Replace sample tracker rules with a maintained tracker intelligence source
- Put the backend behind HTTPS before sharing it
- Rotate the invite code and admin secrets before public rollout
- Consider minimizing or anonymizing stored page-level data if privacy requirements tighten
- Add database migrations before long-term production use
