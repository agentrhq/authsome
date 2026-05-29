# Principal roles: admin / user, first-created principal is admin

Principals need an authorization tier to gate deployment-level operations (audit log access, provider registration/deletion, cross-vault credential revocation) from per-principal operations (own connections, claim accept/reject). We store a `role` column (`admin` | `user`) directly on the `principals` table. The first Principal created on a server is assigned `admin`; all subsequent Principals receive `user`. Role assignment is immutable at creation time (mutation is deferred to a future milestone).

## Considered options

**Environment variable (`AUTHSOME_ADMIN_PRINCIPALS`)** — the prior approach. Rejected because it requires knowing the PrincipalId before the server starts, cannot be changed without a restart, and is invisible to the UI and route layer.

**Separate `principal_roles` table** — considered for future extensibility (multiple roles per principal). Rejected as premature: the role model is binary and a join adds complexity without benefit today.

**Default admin account created at server init** — would require deciding on credentials before any real user exists. Rejected in favour of first-user-becomes-admin: the first principal to register is admin, all subsequent principals are users. (Originally justified as "zero-config" for an implicit local principal; that implicit-principal path was later removed when local and hosted were unified into a single registration + claim flow — see ADR 0007. First-principal-is-admin remains the rule, now reached the same way in every deployment.)

## Consequences

- `AUTHSOME_ADMIN_PRINCIPALS` env var and `is_admin_principal()` are removed entirely.
- Admin enforcement at the route level uses a `get_admin_auth_service` FastAPI dependency (parallel to `get_protected_auth_service`) that raises `HTTP 403` for non-admin principals.
- Admin-only routes: `GET /audit/events`, `POST /providers`, `DELETE /providers/{provider}`, `POST /connections/{provider}/revoke`.
- Schema migration: `ALTER TABLE principals ADD COLUMN role TEXT NOT NULL DEFAULT 'user'`, followed by setting the earliest-created principal to `'admin'`.
