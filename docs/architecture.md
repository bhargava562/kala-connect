# Architecture

```mermaid
flowchart TD
  UI["React + TypeScript / Tamil + English"] --> API["FastAPI / role and ownership checks"]
  UI --> Speech["Optional browser Tamil speech"]
  Speech --> Review["Transcript and field confirmation"]
  Review --> API
  API --> DB["PostgreSQL / persisted records"]
  API --> Workflow["Explicit booking case state machine"]
  Workflow --> Gate["Artist quote approval + customer acceptance"]
  Gate --> DB
  API --> PDF["Paginated bilingual PDF"]
  API --> Demo["Simulated milestones and in-app reminders"]
```

The same SQLAlchemy persistence layer supports an explicit SQLite local demo.
No external LLM is required. `/plan` persists matching and constraint results and a draft quote, never approvals or reservations. Declines persist alternatives. Selection always starts a new customer request.

```mermaid
stateDiagram-v2
  [*] --> requested
  requested --> reviewing: Artist opens request
  requested --> customer_reviewing: Artist approves quote
  reviewing --> customer_reviewing: Artist approves quote
  customer_reviewing --> counteroffer: Customer requests revision
  counteroffer --> customer_reviewing: Artist approves revised quote
  customer_reviewing --> confirmed: Customer accepts / dates checked
  confirmed --> completed: Artist marks ended event complete
  requested --> cancelled: Decline / cancel
  reviewing --> cancelled: Decline / cancel
  customer_reviewing --> cancelled: Cancel
  counteroffer --> cancelled: Cancel
  confirmed --> cancelled: Cancel
  confirmed --> disputed: Report reason
  completed --> disputed: Report reason
```

Confirmation locks the artist database row on PostgreSQL, rechecks collisions, writes approval and both simulated milestones in one transaction. A process lock also serializes SQLite local writes. Audit and notification records are committed with the booking. SQLite is for a single local API process; use PostgreSQL for multiple workers.

Records store JSON documents as TEXT to keep the first migration small and portable. This trades query efficiency for a straightforward demo. Add relational constraints, indexed time ranges and a PostgreSQL exclusion constraint before scaling. API users never receive database credentials; Supabase REST access must stay disabled for these private tables.
