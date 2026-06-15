# User-Scoped Audit Log Design

## Summary

Allow non-admin users to view audit events scoped to their own principal, claimed identities, vault, and credential activity. Keep the existing admin/global audit view separate by authorization behavior, not by duplicating audit storage.

## Goals

- Let non-admin dashboard users review their own account-security events.
- Keep `GET /api/audit/events` as the single role-aware audit read endpoint.
- Enforce all non-admin scoping on the server.
- Add routine filtering and cursor pagination.
- Preserve the Store-backed `audit_events` registry as the source of truth.
- Keep `audit/` storage-free and independent from server-owned persistence.

## Non-Goals

- Do not add a second user-only audit store.
- Do not add a separate `/api/audit/me/events` endpoint for this bug.
- Do not expose secret-bearing metadata or payload expansion in the user audit UI.
- Do not redesign the full dashboard information architecture.

## Architecture

`GET /api/audit/events` remains the single audit read API. The route authenticates through the existing PoP-or-browser dependency and derives an effective scope from the caller:

- Admin principals may query the global audit log, with optional filters.
- Non-admin principals are always scoped to `auth.principal_id`, regardless of query parameters.

`POST /api/audit/events` remains PoP-protected and continues enriching external proxy events with the caller's `identity` and `principal_id`.

The implementation should extend the current server-owned query surface:

- `routes/audit.py` parses filters and pagination, resolves the caller, and computes the effective scope.
- `ServerAuditLog.list_events(...)` accepts richer filter and pagination arguments.
- `AuditEventRegistry.list_recent(...)` builds a parameterized query over the existing `audit_events` table.
- The UI calls the same endpoint for both admin and non-admin users.

This preserves the current module boundaries: `audit/` emits structured events, while `server/` owns storage, authorization, and query behavior.

## API Behavior

`GET /api/audit/events` should support:

- `limit`: bounded result count, clamped to the existing maximum of 500.
- `cursor`: opaque or documented cursor for fetching the next newest-first page.
- `event`: exact event-name filter.
- `provider`: exact provider filter.
- `identity`: exact identity-handle filter.
- `from`: inclusive lower timestamp bound.
- `to`: exclusive upper timestamp bound.

Responses should remain newest-first and include pagination metadata:

```json
{
  "entries": [],
  "next_cursor": null,
  "scope": "principal"
}
```

`scope` is `global` for admin global queries and `principal` for user-scoped queries. The response may include the effective `principal_id` for debugging only if it is the caller's own principal; it must not reveal other principals in user-scoped responses.

## Authorization

Authorization must fail closed.

- Missing or invalid authentication returns `401`.
- Non-admin users cannot widen scope by passing `principal_id`, `vault_id`, or another identity in query parameters.
- If a non-admin passes an `identity` filter outside their own principal, the result is empty because the enforced `principal_id` condition still applies.
- Admin-only or global events without the caller's `principal_id` are never returned to non-admin callers.

The server should not rely on UI filtering for security.

## Data Flow

1. A caller requests `/api/audit/events?limit=50&event=login&provider=github`.
2. The route resolves auth with `get_daemon_or_browser_auth_service`.
3. The route derives effective scope:
   - admin: no forced `principal_id` for global results.
   - user: forced `principal_id = auth.principal_id`.
4. The repository applies the effective scope, filters, timestamp range, limit, cursor, and newest-first ordering.
5. The response returns entries and `next_cursor`.
6. The dashboard maps entries to the existing `AuditRow` display model and renders either the global admin view or the account-scoped user view.

## UI Design

The dashboard already has an Audit tab and table. It should become visible to all authenticated users:

- Sidebar shows `Audit Log` for all users.
- Dashboard home shows recent audit events for all users when available.
- `/audit` page renders for non-admin users instead of returning `null`.
- Admin copy remains: "Recent administrative and credential events."
- User copy becomes: "Recent account, identity, vault, and credential events for this principal."
- Filters cover event type, provider, identity, and time range.
- Pagination uses a "Load more" control backed by the server cursor.

Source changes belong in `ui/src/...`. After the UI source changes, rebuild/export the static dashboard and refresh `src/authsome/ui/web`.

## Error Handling

- Invalid timestamps or malformed cursors should return FastAPI validation errors.
- Empty result sets return `200` with `entries: []`.
- Oversized limits are clamped rather than rejected.
- Store query errors should propagate through the existing server error handling; do not leak raw SQL or storage details in response bodies.

## Testing

Add focused tests for:

- Two principals with overlapping providers where a non-admin only sees their own provider events.
- A non-admin cannot widen scope by passing another principal's ID or another identity.
- Admin callers still see global newest-first results.
- Filters narrow results within the effective scope.
- Cursor pagination returns newest-first pages without skipping or duplicating rows.
- UI source no longer hides the Audit Log navigation or `/audit` page from non-admin users.

The existing Store-backed audit registry tests should continue to pass.
