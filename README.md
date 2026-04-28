# BMW Marketplace

BMW Marketplace is a hybrid automotive marketplace for dealerships and individual sellers to list, discover, and transact on vehicles.

## Project Docs

- [Product Spec](docs/Product_Spec.md)
- [One-Pager](docs/BMW_Marketplace_OnePager.md)
- [UX Model](docs/UX_Model.md)
- [Data Model](docs/Data_Model.md)
- [Script Architecture and Modules Guide](docs/Script_Architecture_And_Modules_Guide.md)

## Product Summary

The platform is designed to bring dealer inventory and private listings into one trusted marketplace. Buyers can search, compare, save, and inquire about vehicles, while sellers can publish listings, manage leads, and complete transactions in a focused automotive environment.

## Script Starter

Use these scripts to generate local test data and a basic KPI snapshot while you start building Phase 1.

1. Generate seed data:

```bash
python3 scripts/seed_data.py
```

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

1. View KPI snapshot:

```bash
python3 scripts/kpi_report.py
```

1. Run local FastAPI app with listings (requires PostgreSQL):

```bash
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/bmw_marketplace
export BMW_MARKETPLACE_DATA_DIR=data
./.venv/bin/python -m uvicorn scripts.home_page:app --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000` in your browser.

## Docker Quick Start

Run the app and PostgreSQL together with Docker Compose:

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

Notes:

- App service uses `DATABASE_URL=postgresql://postgres:postgres@db:5432/bmw_marketplace`
- Database data is persisted in a named Docker volume: `pg_data`

## Default Admin Access

The app seeds a default site admin automatically if one does not exist yet. This is intended so anyone cloning the repo can immediately use the admin controls without manual setup.

Default credentials:

- Email: `admin@bmw-marketplace.local`
- Password: `ChangeMe123!`
- Name: `Site Admin`

Environment overrides:

- `BMW_MARKETPLACE_DEFAULT_ADMIN_EMAIL`
- `BMW_MARKETPLACE_DEFAULT_ADMIN_PASSWORD`
- `BMW_MARKETPLACE_DEFAULT_ADMIN_NAME`

If you change these values in your environment, the seeded admin account will use the new values on startup.

## Easiest Way To Run (Beginner)

Use the one-command launcher:

```bash
python3 scripts/easy_start.py
```

What it does automatically:

- Installs Python dependencies if needed
- Starts PostgreSQL with Docker (`docker compose up -d db`) if DB is not already running
- Migrates old SQLite data one time (if `data/marketplace.db` exists)
- Starts the FastAPI app through Uvicorn at `http://127.0.0.1:8000`

## Migrate Old SQLite Data

If you already have local SQLite data in `data/marketplace.db`, run:

```bash
python3 scripts/migrate_sqlite_to_postgres.py
```

This copies data from SQLite to PostgreSQL for these tables:

- `app_users`
- `app_sessions`
- `user_listings`

## Code Layout (Smaller Files)

The homepage server was split into smaller files to make edits easier:

- `scripts/home_page.py`: FastAPI routes, ASGI app export (`app`), and request handling
- `scripts/marketplace_core.py`: database, auth, and core helpers
- `scripts/marketplace_render.py`: HTML/template rendering functions
