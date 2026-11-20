# KALA CONNECT

Tech4Bharat Hackathon 2026 · Problem 7.2: folk artists, performers and heritage hosts struggle to obtain regular, paid bookings.

Mobile-first cultural booking application using React, TypeScript, Tailwind CSS, FastAPI and SQLAlchemy. PostgreSQL (including a Supabase direct database connection) is the hosted target. SQLite is an explicitly supported single-process local demo option.

## Features

- Artist/customer registration and password login; server-side roles and ownership checks. Operator/admin accounts are provisioned rather than self-selected.
- Artist profile drafts, consent, media links, travel conditions and artist-only publication. Assisted operators prepare drafts for existing artist accounts.
- English/Tamil primary interface, Tamil browser speech when supported, typed/sample transcript fallback and editable extraction confirmation. The extraction service is a limited offline parser, not an LLM.
- Discovery filters, availability blocking, event requests, artist-approved itemized quotes, counteroffers, customer acceptance and conflict prevention.
- Persisted state machine, deterministic matching/constraint/draft proposal endpoint and decline recovery. No automatic artist commitments.
- Dashboards, status history, in-app notifications, reports/admin review, unpaid/overdue milestones and artist-approved in-app reminders.
- Paginated bilingual PDF agreements after both approvals; approved artist name and conditions are snapshotted with the quote.
- Explicitly simulated payments only. Configurable advance percentage (30/70 default). No payment gateway, escrow, UPI integration, guarantees or money movement.

## Local setup

Requires Python 3.12+ and Node 20.19+ (or Node 22+).

```powershell
Copy-Item .env.example .env
# Edit .env: choose DEMO_PASSWORD and configure a Tamil font path.
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite proxy sends `/api` to port 8000. API docs: http://localhost:8000/docs. Environment is loaded from the root `.env`.

On Windows, `.env.example` references the system Nirmala Tamil-capable font. On Linux use `NotoSansTamil-Regular.ttf` and set `TAMIL_FONT_PATH`. PDF generation fails with a helpful error if the configured font is missing instead of silently dropping Tamil text.

### Sample accounts

Set `SEED_DEMO=true` and `DEMO_PASSWORD` before first startup. The seed is idempotent on a populated user table. All seeded users share your chosen demo password; disable seeding on real deployments. No password is hardcoded into frontend code.

| Role | Email |
| --- | --- |
| Kaveri Karakattam | artist1@demo.example.com |
| Thendral Folk Arts | artist2@demo.example.com |
| Marabu Heritage | artist3@demo.example.com |
| Organizer 1 | customer1@demo.example.com |
| Organizer 2 | customer2@demo.example.com |
| Assisted operator | operator@demo.example.com |
| Admin | admin@demo.example.com |

All profiles and users are fictional. Admin review is a moderation event, not identity verification. Real users can self-register only as artists or customers. For a fresh non-demo installation provision trusted operator/admin users through a controlled administrative database process, never a public endpoint.

### Case C fixture

From `backend`, after demo seeding: `python demo_overdue.py`. This creates `demo-overdue-case`, a completed historical fictional booking with unpaid balance. It is labeled as a fixture in its audit log. Public APIs disallow requesting past events and completing future events.

## PostgreSQL / Supabase

Set `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE` with URL-encoded credentials. Use the provider’s required SSL parameters (`?sslmode=require` for Supabase). Apply `backend/migrations/001_initial.sql` using a migration-capable database role. Startup also creates missing schema for local convenience.

The API owns database access. Keep these tables private and do not grant anonymous/authenticated Supabase REST roles access. This application uses its own hashed-password/session login, not Supabase Auth. No Supabase service key belongs in `VITE_*` variables.

Alternatively set `POSTGRES_PASSWORD` in `.env` and run `docker compose up --build`. The Docker API includes a Tamil font. Start the React frontend separately.

## Validation

```powershell
cd backend
python -m unittest discover -s tests -v
cd ../frontend
npm run build
```

The API suite covers role restrictions, registration consent, ownership, approval gates, quotation revisions, conflicting confirmations, blocked dates, decline recovery, simulated-payment authorization, operator publication restrictions, overdue reminders, disputes and PDF output. Tests use an isolated temporary SQLite database. They do not establish PostgreSQL concurrency correctness or production readiness.

See [docs/verification.md](docs/verification.md) for actual results and environment limitations. A labeled offline Vite config can run the same React screens and authored CSS using locally available dependencies if npm is unavailable: `npx vite --config vite.offline.config.ts`. It skips Tailwind’s reset/utilities and is not the standard deployment build.

## Deployment

Frontend: import this repository into Vercel with root `frontend`, command `npm run build`, output `dist`. Set `VITE_API_URL` to your HTTPS Python backend URL before building.

Backend: deploy `backend/Dockerfile` on a Python/Docker-capable host such as Render, Railway or Fly. Set `DATABASE_URL`, `CORS_ORIGINS` to the exact frontend origin, `SEED_DEMO=false`, and `TAMIL_FONT_PATH`. Configure HTTPS and a private PostgreSQL database. `/api/health` is a readiness endpoint. No public deployment is created by these files alone.

## Security and limits

Passwords use scrypt with independent salts; only hashes of random 12-hour session tokens are stored. Sessions use browser sessionStorage; use hardened HttpOnly cookies and CSRF controls for a production deployment. Inputs have type/range checks; no Aadhaar field exists. TLS, rate limits, password reset, email verification, retention/deletion flows, content scanning, production monitoring and professional agreement review remain deployment work.

Profile photos/clips use artist-supplied HTTPS URLs and consent, not managed uploads. Default visuals are original CSS illustrations with no external image requests. Browser speech may use a third-party browser speech provider and is optional; the sample is text, not prerecorded audio. Reminder delivery is in-app and approval-triggered, not email/SMS or scheduled background delivery. Localization covers primary navigation and booking controls; some secondary forms/admin descriptions remain English.

The coordinator is explicit deterministic code, independent of external LLM services. `/api/bookings/{id}/plan` persists an unapproved proposal and constraint results; quote publication still requires the artist endpoint and confirmation requires the customer endpoint. Alternatives are not reservations. Single-process SQLite serializes writes with an in-process lock. PostgreSQL confirmations lock the artist row; hosted concurrency must be tested against the actual database. Current JSON document queries scan records and are intended for demo scale.

## Repository delivery

Target supplied by the user: https://github.com/Deekshitha-Warrior/GVAS-HACKTHON-ARTS

If remote access is blocked, use the included archive. To avoid overwriting existing repository history, clone the target into a new directory, copy this project’s contents into it (excluding `.env`, database files and `node_modules`), review changes, then:

```powershell
git status
git add .
git commit -m "Build KALA CONNECT cultural booking platform"
git push origin HEAD
```

If the target is empty, this checkout can be initialized directly:

```powershell
git init -b main
git remote add origin https://github.com/Deekshitha-Warrior/GVAS-HACKTHON-ARTS.git
git add .
git commit -m "Build KALA CONNECT cultural booking platform"
git push -u origin main
```

Never force-push. Authenticate through Git Credential Manager or a GitHub connection; do not paste access tokens into source files.

See [architecture](docs/architecture.md) and the [three-minute judge walkthrough](docs/judge-demo.md).
