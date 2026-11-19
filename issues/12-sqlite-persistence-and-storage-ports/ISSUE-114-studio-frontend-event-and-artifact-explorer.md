# [ISSUE-114] Studio Frontend Historical Event Explorer, SSE Cursor Handoff & Paginated Artifact Views

| Metadata | Details |
| :--- | :--- |
| **Issue ID** | `ISSUE-114` |
| **Domain / Category** | `12-SQLite Persistence & Storage Ports` (Studio Frontend, Virtualized Log Explorer, Paginated Artifacts) |
| **Target Package(s)** | `packages/episteme-studio/frontend` (`src/api/`, `src/store/`, `src/console/`, `src/panels/`) |
| **Depends On** | `ISSUE-113` |
| **Complexity** | **MEDIUM** |
| **Recommended Model** | **Neon** |
| **Reasoning Effort** | **MEDIUM** |
| **Priority** | **High** |
| **Status** | `Open` |
| **ADR Reference** | [ADR-0025](../../docs/adr/0025-embedded-sqlite-persistence-and-storage-ports.md) |

---

## 1. Problem & Architectural Context

Currently, the Episteme Studio frontend relies solely on live SSE streaming into an unbounded client array inside [`runsStore.ts`](../../packages/episteme-studio/frontend/src/store/runsStore.ts) and filters logs purely in React memory inside [`LogConsole.tsx`](../../packages/episteme-studio/frontend/src/console/LogConsole.tsx):
- Selecting any completed or failed historical run after a backend restart shows an empty telemetry console.
- A 100–500 page monograph emits 50,000–200,000+ events and tens of thousands of artifacts; loading every event and artifact into browser Zustand state at once freezes the UI and exhausts tab memory.
- [`StageArtifactsView.tsx`](../../packages/episteme-studio/frontend/src/panels/StageArtifactsView.tsx) and artifact drawers assume full unpaginated artifact arrays.

---

## 2. Architectural Upgrades Included (`[NO LEGACY]`)

- **Server-Driven Filtering & Cursor Windowing**: Move historical event filtering (`level`, `phase`, `kind`, full-text `q`) and artifact filtering (`kind`, `phase`, `search`) from client-side array scans to debounced backend queries powered by SQLite indexes and FTS5 (`ISSUE-113`).
- **Unified Historical-to-Live Telemetry Timeline**: Replace ad-hoc in-memory log reset logic in `runsStore.ts` with an explicit cursor-based state machine (`loadEventPage`, `loadOlderEvents`, `connectLiveStream(sinceSeq)`), deduplicating strictly on monotonic `seq`.

---

## 3. Detailed Design & Implementation Specification

### 3.1 API Client & Wire Contracts (`frontend/src/api/`)

- Update `types.ts` (or regenerate `generated.d.ts`) with `EventPageResponse`, `EventSummaryResponse`, and `ArtifactPageResponse`.
- Extend `client.ts` with:
  - `getRunEventsHistory(runId, { phase, kind, level, q, afterSeq, beforeSeq, limit })`
  - `getRunEventsSummary(runId)`
  - `getRunArtifacts(runId, { kind, phase, search, latestOnly, cursor, limit })`

### 3.2 `runsStore.ts` & `LogConsole.tsx` Upgrades

1. **Historical Hydration on Run Selection**:
   - When `selectRun(runId)` selects a completed/failed/aborted run, immediately fetch `/events/summary` (populating phase/level badge counts without fetching all rows) and the latest page of `/events/history` (`limit=500`).
   - When selecting an active `RUNNING` run, hydrate historical rows up to `newest_seq` first, then open SSE `streamRunEvents(runId, since=newest_seq)` so zero early-phase events are lost even if opened mid-run.
2. **Debounced Server-Side FTS5 Search & Filter Controls**:
   - Wire `logFilterLevel`, `logFilterPhase`, kind selector, and `logSearch` (250 ms debounce) to query `/events/history` directly for historical runs (and filter live + reload tail cleanly for active runs).
3. **Windowed Virtual Scroll (`@tanstack/react-virtual`)**:
   - Support "Load earlier events (`before_seq`)" upward pagination inside `LogConsole.tsx`, bounding active browser RAM (e.g., sliding window or explicit chunked paging) while showing exact server totals from `EventSummaryResponse`.

### 3.3 Paginated Artifact Panels (`StageArtifactsView.tsx`)

- Update artifact table/list consumers to request `/api/runs/{runId}/artifacts?kind=...&limit=200&cursor=...`, displaying total server count per kind and loading subsequent pages on scroll or button click.

---

## 4. Testing & Verification Strategy

- Frontend Vitest suites (`packages/episteme-studio/frontend/src/`):
  - `runsStore.test.ts`: test historical event hydration, `before_seq` pagination deduplication, and seamless SSE handoff without duplicate `seq` entries.
  - Component tests for `LogConsole.tsx` verifying debounced FTS5 filter requests, summary count badges, and empty/error states.
  - Run `npm test` and `npm run build` in `packages/episteme-studio/frontend` confirming zero TypeScript errors.

---

## 5. Acceptance Criteria

- [ ] Historical run logs, errors, and telemetry appear immediately in `LogConsole.tsx` even after Studio server restarts.
- [ ] Phase, level, kind, and FTS5 full-text queries execute server-side with debounced pagination; 100k-event runs stay responsive in the browser.
- [ ] Live running pipelines hand off smoothly from SQLite history to live SSE at `lastSeq` without duplicate or dropped rows.
- [ ] Artifact views use paginated `/artifacts` responses; frontend typecheck, Vitest suite, and Vite build pass cleanly.
