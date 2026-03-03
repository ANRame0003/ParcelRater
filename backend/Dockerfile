FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so Docker can cache this layer separately.
# Rebuilds only re-run pip if requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY main.py .

EXPOSE 8000

# ── HOW TO CHOOSE A RUN MODE ──────────────────────────────────────────────────
#
# DEVELOPMENT (default) — single Uvicorn process, no multiprocessing overhead.
# Fine for local use and low traffic. --host 0.0.0.0 binds to all interfaces
# inside the container so nginx can reach it; 127.0.0.1 would block proxying.
#
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
#
# PRODUCTION — swap the CMD above for the one below when you need to scale.
# Gunicorn manages 4 worker processes (-w 4, tune to 2x CPU cores).
# -k tells Gunicorn to use Uvicorn async workers instead of its default sync
# workers — required for FastAPI/asyncio. --bind is Gunicorn's equivalent of
# Uvicorn's --host/--port; Gunicorn owns the socket and hands it to each worker.
#
# CMD ["gunicorn", "main:app", \
#      "-w", "4", \
#      "-k", "uvicorn.workers.UvicornWorker", \
#      "--bind", "0.0.0.0:8000"]
