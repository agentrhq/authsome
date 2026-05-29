# Audit events use OTel Logs API with a SQLite exporter owned by the server

The proxy runs on the client machine and the server runs remotely, so writing audit events to a local file produces two disjoint logs that an IT admin cannot view in one place. We need a single server-owned audit store that both the proxy and the server write into.

**Decision:** `audit/` is a pure leaf that imports only `opentelemetry-api`. It defines `AuditEvent`, translates it to an OTel `LogRecord`, and emits via the globally registered `LoggerProvider` — with no knowledge of where events go. `server/` owns a custom `SQLiteLogExporter` (implementing the OTel `LogExporter` interface), registers a `LoggerProvider` with a `BatchLogRecordProcessor` at daemon startup, and exposes `GET /audit/events` for admin queries. The proxy ships External AuditEvents to the server fire-and-forget via `POST /audit/events` rather than writing to a local file; the server enriches each inbound event with `principal_id` resolved from the PoP JWT.

**Considered alternatives:**

- *Flat JSON-lines file per process* — the current approach. Rejected because it produces two disjoint audit logs in the client/server topology, with no queryable interface for the admin view.
- *Proxy hosted on server* — rejected because it routes all agent traffic through the server machine, adding a network round-trip to every API call and making the server a traffic bottleneck.
- *Pure OTLP to an external collector* — rejected as the primary store because it requires operator-provisioned infrastructure. OTLP remains a valid future second exporter on the same `LoggerProvider` for teams that already run Grafana or Datadog.
- *SQLite owned by `audit/`* — rejected to preserve `audit/` as a dependency-free leaf. Storage decisions belong to `server/`, consistent with how all other server-owned state is managed.

**Not considered:** replacing loguru with OTel for operational logging. Loguru (68 call sites) serves developers debugging live systems — free-form, level-filtered, short-retention. Audit serves IT admins answering compliance questions — structured, required fields, long-retention, queryable. Routing loguru through the SQLite exporter would fill the admin view with operational noise. They are different things with different audiences and must stay separate.

**Consequences:**

- `audit/` gains `opentelemetry-api` as a dependency; `server/` gains `opentelemetry-sdk` and `aiosqlite` (or `sqlite3`).
- `audit.setup()` / `audit.clear()` are removed; `server/app.py` lifespan manages the `LoggerProvider`.
- The proxy's two existing direct `audit.log()` calls (`proxy_no_credentials`, `proxy_deny`) move to fire-and-forget HTTP posts to the server.
- A second OTLP exporter can be added to the `LoggerProvider` at any time without touching `audit/` or `proxy/`.
- All audit events — Internal (server) and External (proxy) — are queryable from a single `GET /audit/events` endpoint.
