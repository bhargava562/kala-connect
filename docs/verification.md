# Verification record

Environment: Windows, Python 3.14.6, Node 26.5.0. Tested on 20 November 2026.

| Check | Result |
| --- | --- |
| Isolated SQLite API tests | 14 tests passing (see `backend/tests/test_api.py`) |
| TypeScript app and offline Vite config | `tsc -p tsconfig.offline.json` passed |
| React build with offline authored CSS | `vite build --config vite.offline.config.ts` passed; 28 modules, about 80 kB gzipped JavaScript |
| Bilingual PDF | API test generated a valid PDF using Windows Nirmala font |
| API startup | Uvicorn reported application startup complete on port 8000 |
| Frontend startup | Vite reported ready on port 5173 |
| Network readiness / browser walkthrough | Blocked: local loopback connections timed out across tool surfaces; Windows browser controller stopped due to URL detection failure |
| Screenshots | Not captured; no screenshot is presented as verified |
| Standard Tailwind build | Not verified: npm registry DNS resolution failed; no Tailwind package was available locally |
| PostgreSQL / Supabase | Configuration, migration and Docker Compose provided; not run against a live PostgreSQL instance |
| GitHub publication | Blocked: github.com DNS resolution failed; GitHub connector not installed |
| External speech | Not tested; browser-dependent, with explicit typed/sample text fallback |

The offline build used existing local React/Vite dependencies; it does not fake a Tailwind installation. The standard config and package manifest retain the requested Tailwind integration. No screenshots, hosted deployment, successful push or production readiness are claimed.

The test suite checks API behavior through FastAPI TestClient, not a browser. Case C uses a labeled historical seed fixture to demonstrate an overdue final milestone without weakening date validation. Notifications/reminders are in-app; payments are simulated; artist identity is unverified; secondary interface text is partly English.
