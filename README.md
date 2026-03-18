# UdensFiltri Backend (Django + DRF + PostgreSQL)

Production-oriented backend for authentication, catalog, cases, orders, and Stripe payments.

## What was optimized
- Consolidated duplicated verification-code creation and delivery flow in the accounts module.
- Removed unused code/imports and deleted obsolete duplicate Docker Compose file.
- Added Docker build optimizations (`.dockerignore`) and non-root runtime user.
- Added explicit shared Docker network so backend can communicate with frontend and PostgreSQL containers.

---

## Prerequisites
- Docker 24+
- Docker Compose v2+

---

## 1) Environment setup
From repository root:

```bash
cp .env.example .env
```

Update `.env` with production values, especially:
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `FRONTEND_ORIGINS`
- `DB_PASSWORD`
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`

---

## 2) Start backend + PostgreSQL in containers
From repository root:

```bash
docker compose up --build -d
```

This starts:
- `web` (Django app via Gunicorn on `:8000`)
- `db` (PostgreSQL 16 on `:5432`)

On startup, `web` automatically runs:
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`

---

## 3) Verify services

```bash
docker compose ps
docker compose logs -f web
```

API should be reachable at:
- `http://localhost:8000/`
- admin login health endpoint: `http://localhost:8000/admin/login/`

---

## 4) Connect frontend container to backend
Both services must share the same Docker network (`udensfiltri_net`).

### Option A (recommended): frontend in its own compose file
Attach frontend service to external network:

```yaml
networks:
  udensfiltri_net:
    external: true

services:
  frontend:
    # ...
    networks:
      - udensfiltri_net
```

Then frontend can call backend by service name:
- `http://web:8000` (container-to-container)

If frontend runs in browser, use host-mapped URL:
- `http://localhost:8000`

---

## 5) Connect external apps to PostgreSQL
Inside Docker network use:
- Host: `db`
- Port: `5432`
- Database/User/Password from `.env`

From host machine use:
- Host: `localhost`
- Port: `${DB_PORT}` (default `5432`)

---

## 6) Common operations

### Rebuild after dependency/code changes
```bash
docker compose up --build -d
```

### Run Django management command inside container
```bash
docker compose exec web python manage.py createsuperuser
```

### Stop stack
```bash
docker compose down
```

### Stop stack and remove DB volume (destructive)
```bash
docker compose down -v
```

---

## 7) Local run (without Docker)
From `udensfiltribackend/`:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

