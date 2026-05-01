# ---- builder: installs deps (may pull build tools) ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- final: clean slim image, no build artifacts ----
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

# Run Alembic migrations before starting the server.
# The retry loop handles the rare case where the DB isn't ready yet at container start.
# On Railway, the DB is guaranteed up before the service starts — the loop is just a safety net.
# Workers: 2 × vCPUs + 1 (Railway starter = 1 vCPU → 2 workers is safe for memory)
CMD ["sh", "-c", "until alembic upgrade head; do echo 'DB not ready, retrying in 3s...'; sleep 3; done && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --log-level info"]
