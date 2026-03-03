# Parcel Rate Finder

Multi-carrier shipping rate comparison — UPS · FedEx · DHL Express.

A FastAPI backend with a React frontend, containerized with Docker Compose.

---

## Quickstart

```bash
git clone <your-repo-url>
cd rate-finder
docker compose up --build
```

Open **http://localhost** in your browser. That's it.

> **Only requirement:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose).

```bash
docker compose down          # stop
docker compose up --build    # rebuild after code changes
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
│   ├── Dockerfile            ← Python 3.12-slim + Uvicorn (or Gunicorn for prod)
│   ├── main.py               ← FastAPI: UPS, FedEx, DHL integrations
│   └── requirements.txt
└── frontend/
    ├── Dockerfile            ← nginx:alpine serving static HTML
    ├── nginx.conf            ← Serves index.html + proxies /api/ → backend
    └── index.html            ← Single-file React app (no build step)
```

---

## Architecture

```
Browser :80  →  nginx (frontend container)
                  ├── /          → serves index.html
                  └── /api/...   → proxies to backend:8000 (internal Docker network)
                                        └── FastAPI fetches UPS / FedEx / DHL in parallel
```

The frontend uses relative URLs (`/api/rates`) — nginx routes internally by container
name, so no hardcoded IPs or ports are exposed to the browser.

The backend uses `asyncio.gather()` to call all three carriers simultaneously.
Total response time equals the slowest carrier (~1–3s), not the sum of all three.

---

## API Credentials

Entered directly in the UI — nothing stored server-side.

| Carrier   | Required                  | Where to get it                    |
|-----------|---------------------------|------------------------------------|
| **UPS**   | Client ID + Client Secret | https://developer.ups.com          |
| **FedEx** | Client ID + Client Secret | https://developer.fedex.com        |
| **DHL**   | API Key                   | https://developer.dhl.com          |

---

## Scaling to Production

The default `CMD` in `backend/Dockerfile` runs a single Uvicorn process — correct
for development and low traffic. For higher concurrency, swap to Gunicorn with
multiple Uvicorn workers by editing the `CMD` at the bottom of the Dockerfile:

```dockerfile
# Comment out the dev CMD:
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# Uncomment the production CMD:
CMD ["gunicorn", "main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

**Flag reference:**

| Flag / Arg                         | Belongs to | What it does                                                                                                              |
|------------------------------------|------------|---------------------------------------------------------------------------------------------------------------------------|
| `-w 4`                             | Gunicorn   | Spawn 4 worker processes. Rule of thumb: 2× CPU cores.                                                                    |
| `-k uvicorn.workers.UvicornWorker` | Gunicorn   | Worker *class* — use Uvicorn async workers instead of Gunicorn's default sync workers. Required for FastAPI/asyncio.      |
| `--bind 0.0.0.0:8000`              | Gunicorn   | Gunicorn binds the socket (host:port combined). Equivalent to Uvicorn's separate `--host` / `--port` flags.               |
| `--host 0.0.0.0 --port 8000`       | Uvicorn    | Uvicorn's equivalent of `--bind`. Use when running Uvicorn directly without Gunicorn.                                     |

> **Why `0.0.0.0`?** Binds to all network interfaces inside the container so nginx
> can reach the backend. Using `127.0.0.1` would restrict to loopback only and
> break the nginx proxy.

---

## Swagger UI (API Docs)

FastAPI auto-generates interactive API docs at:

```
http://localhost:8000/docs
```

Port 8000 is mapped to the host in `docker-compose.yml` for this purpose.
Remove the `ports` block from the `backend` service to restrict direct access in production.

---

## Running Without Docker

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2 — frontend
# Edit index.html: change  const API_BASE = "";
#                      to  const API_BASE = "http://localhost:8000";
open frontend/index.html
```
