# Three-minute judge walkthrough

Prepare: copy `.env.example` to `.env`, set a demo password, enable seed data and start both services. Keep two browsers or sign out to switch roles. Use a future event date. Run `python demo_overdue.py` from `backend` once for case C.

**0:00–0:25 — Problem and discovery.** “KALA CONNECT helps folk artists find paid opportunities while keeping control of their fees. These are three fictional sample profiles; payments are simulations.” Show the landing page, search Karakattam, select a date and view Kaveri’s conditions.

**0:25–0:55 — Artist onboarding.** Sign in as artist1. In Artist studio select Tamil. Use the explicitly labeled sample transcript or browser Tamil speech if available. Extract the draft, inspect and correct every field, confirm it, then save a draft and approve publication. Explain that an operator can only draft for an existing artist account.

**0:55–1:45 — Booking and approval.** Sign in as customer1, request Kaveri for a future college event. Switch to artist1. Prepare all four quote components and approve them. Switch to customer1; inspect totals and cancellation conditions, then approve and confirm. Download the bilingual PDF and simulate the 30% advance. “No real UPI transfer or escrow happens.” Show approval history.

**1:45–2:15 — Decline recovery.** Request a different date from Kaveri, switch to artist1 and decline. Show Thendral as an available alternative within budget. “The coordinator persists the recovery state and makes no unauthorized reservation.” Open the alternative; submitting a new request is a separate customer action.

**2:15–2:45 — Overdue final milestone.** Open `demo-overdue-case`, a labeled historical fixture. The 70% balance is overdue and unpaid. As artist1 approve an in-app reminder, then submit a dispute with a reason. Open Admin to show the dispute and audit event. Reminders are in-app only.

**2:45–3:00 — Integrity.** Show test results and architecture. Explain that PostgreSQL hosting, a public frontend deployment and live speech-provider behavior require target-environment verification. No claim of production readiness or official artist verification.
