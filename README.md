# Parcel Rate Finder

Multi-carrier shipping rate comparison — UPS · FedEx · DHL Express.

---

## Quickstart (Docker)

```bash
git clone <your-repo-url>
cd rate-finder
docker compose up --build
```

Then open **http://localhost** in your browser.

> **Requirements:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose). Nothing else needed.

To stop:
```bash
docker compose down
```

To rebuild after code changes:
```bash
docker compose up --build
```

---

## Project Structure

```
rate-finder/
├── docker-compose.yml        ← Orchestrates both containers
├── .dockerignore
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile            ← Python 3.12 + uvicorn
│   ├── main.py               ← FastAPI app (UPS, FedEx, DHL integrations)
│   └── requirements.txt
└── frontend/
    ├── Dockerfile            ← nginx:alpine serving static HTML
    ├── nginx.conf            ← Proxies /api/ → backend container
    └── index.html            ← Single-file React app (no build step)
```

---

## How it Works

```
Browser :80  →  nginx (frontend container)
                  ├── /          → serves index.html
                  └── /api/...   → proxies to backend:8000
                                        └── FastAPI fetches UPS / FedEx / DHL in parallel
```

The frontend uses relative URLs (`/api/rates`) so nginx handles routing internally — no hardcoded ports in the browser.

---

## API Credentials

Enter credentials directly in the UI — nothing is stored server-side.

| Carrier | What you need | Where to get it |
|---------|--------------|-----------------|
| **UPS**   | Client ID + Client Secret | https://developer.ups.com |
| **FedEx** | Client ID + Client Secret | https://developer.fedex.com |
| **DHL**   | API Key                   | https://developer.dhl.com |

---

## Optional: Swagger UI

The FastAPI backend exposes auto-generated API docs at:

```
http://localhost:8000/docs
```

Port 8000 is mapped to the host in `docker-compose.yml` for this purpose. Remove that `ports` block if you want to lock it down to internal traffic only.

---

## Running Without Docker (Development)

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — frontend
# Edit index.html: change API_BASE = "" to API_BASE = "http://localhost:8000"
open frontend/index.html
```
