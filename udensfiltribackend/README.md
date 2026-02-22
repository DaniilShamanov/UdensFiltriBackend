# Plumbing Backend (Django + DRF + Postgres)

Includes: auth with email verification codes, JWT cookies, Stripe + webhook, optional email receipts,
catalog, cases (equipment + chat), blog, admin panel, and unit tests.

## Local setup (without Docker)
Run these commands from `udensfiltribackend/`:

1) `cp ../.env.example ../.env` and edit values
2) `pip install -r requirements.txt`
3) `python manage.py migrate`
4) `python manage.py createsuperuser`
5) `python manage.py runserver`

## Docker setup (production-ready baseline)
Run these commands from the repository root:

1) `cp .env.example .env`
2) Edit `.env` for production (especially `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, TLS/cookie settings)
3) `docker compose up --build -d`

Services included:
- `web`: Django app served via Gunicorn (`0.0.0.0:8000`)
- `db`: PostgreSQL 16 with persistent volume `postgres_data`

The `web` container waits for PostgreSQL, then runs:
- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`

before starting Gunicorn.

## Tests
`python manage.py test`

## Deployment notes (Latvia / areait.lv)

This project is tailored for Latvia by default:
- `TIME_ZONE = Europe/Riga`
- Phone normalization uses region `LV` (Latvian numbers) and stores phones in E.164 (`+371...`).

Typical deployment on areait.lv (VPS-style hosting) is:
1. Run the app with Gunicorn (or uWSGI) behind Nginx.
2. Configure Nginx to pass `X-Forwarded-Proto` so Django can detect HTTPS.
3. Set these environment variables in production:
   - `DJANGO_DEBUG=0`
   - `DJANGO_ALLOWED_HOSTS=your-api-domain`
   - `DJANGO_SECURE_SSL_REDIRECT=1`
   - `DJANGO_SESSION_COOKIE_SECURE=1`
   - `DJANGO_CSRF_COOKIE_SECURE=1`
   - `AUTH_COOKIE_SECURE=1`
   - `FRONTEND_ORIGINS=https://your-frontend-domain`
   - `STRIPE_SECRET_KEY=...`, `STRIPE_WEBHOOK_SECRET=...`

### Gunicorn example
```bash
pip install -r requirements.txt gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

### Nginx proxy header
Ensure your Nginx config sets:
- `proxy_set_header X-Forwarded-Proto $scheme;`
- `proxy_set_header Host $host;`
