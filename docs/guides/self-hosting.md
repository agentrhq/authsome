# Self-hosting Authsome

Run Authsome as a production service with Postgres for the server registries and Redis for shared runtime state plus the encrypted vault raw KV layer.

## Quick start

The repository ships a compose file that wires the daemon to Postgres and Redis. Set a stable master key source first, then bring the stack up and verify the root health check.

```bash
export AUTHSOME_POSTGRES_PASSWORD='change-me-to-a-long-random-password'
export AUTHSOME_MASTER_KEY='base64-encoded-32-byte-key'
docker compose up -d
curl http://localhost:7998/health
```

The daemon should answer on `http://localhost:7998`. The root `/health` endpoint is the container health target used by the image and by `docker compose`.
The included compose file reads `AUTHSOME_MASTER_KEY` from the host environment. `AUTHSOME_MASTER_KEY_FILE` is supported by Authsome itself, but if you want to use a file-mounted secret you must add that mount and pass the file path yourself in a custom compose file.

## What this deployment does

- Postgres stores the relational server registries: identities, principals, vaults, claims, and bindings.
- Redis stores shared runtime state and, when configured, backs the raw KV layer that holds encrypted vault blobs.
- The Authsome container keeps only a small home directory for logs and optional fallback key material. Primary production state lives in Postgres and Redis.
- Browser sessions remain stateless signed cookies for now. Any future stateful browser session store is tracked separately.

## Prerequisites

- Docker and Docker Compose v2.
- Postgres 16.
- Redis 7.
- A stable `AUTHSOME_MASTER_KEY` for the included compose file.

Do not commit production master keys. Use your platform secret store or a Docker secret for the included compose file. If you prefer `AUTHSOME_MASTER_KEY_FILE`, wire up your own secret mount and file path in a custom compose file.

## Required environment variables

| Variable | Default | Description |
|---|---|---|
| `AUTHSOME_DATABASE_URL` | none | Postgres DSN for the daemon-owned registries. The compose file points this at the bundled Postgres service. |
| `AUTHSOME_REDIS_URL` | none | Redis URL for shared runtime state and the encrypted vault raw KV backend. |
| `AUTHSOME_POSTGRES_PASSWORD` | none | Required password used by the bundled Postgres service and the daemon's database URL. |
| `AUTHSOME_POSTGRES_USER` | `authsome` | Postgres role name used by the bundled compose file. |
| `AUTHSOME_POSTGRES_DB` | `authsome` | Postgres database name used by the bundled compose file. |
| `AUTHSOME_MASTER_KEY` | none | Base64-encoded 32-byte master key. Highest priority when set. |
| `AUTHSOME_MASTER_KEY_FILE` | none | Advanced alternative for custom compose or platform-secret setups where you mount a file into the container and point Authsome at that path yourself. |
| `AUTHSOME_BASE_URL` | `http://localhost:7998` | Public daemon URL used to build OAuth callback URLs. Set this to the reverse-proxy URL in production. |
| `AUTHSOME_HOME` | `/data/authsome` | Home directory for logs, generated fallback secrets, and other daemon-local files. |
| `AUTHSOME_HOST` | `0.0.0.0` | Host interface the daemon binds to inside the container. |
| `AUTHSOME_PORT` | `7998` | TCP port the daemon listens on. |
| `AUTHSOME_DO_NOT_TRACK` | `1` | Set to `0` only if you intentionally want telemetry enabled. |
| `AUTHSOME_POSTHOG_API_KEY` | none | Enables PostHog analytics when present and telemetry is not opted out. |
| `AUTHSOME_POSTHOG_HOST` | `https://us.i.posthog.com` | Override the PostHog ingestion host if needed. |

The current daemon settings still read the legacy `DATABASE_URL` alias internally. The compose file sets `AUTHSOME_DATABASE_URL` and mirrors it into `DATABASE_URL` so the deployment contract stays explicit while the current runtime keeps working.
The included compose file hard-requires `AUTHSOME_MASTER_KEY` from the host environment; it does not mount a secret file or pass a `_FILE` path for you.

## Master key resolution

On startup, Authsome resolves the master key in this order:

1. `AUTHSOME_MASTER_KEY`
2. `AUTHSOME_MASTER_KEY_FILE`, or the default server key file at `AUTHSOME_HOME/server/master.key`
3. The OS keyring entry
4. A generated fallback, stored in the keyring when possible, otherwise written to the default server key file

`AUTHSOME_MASTER_KEY` is the strongest and cleanest production option for the included compose file because it avoids writing secret material to disk. If you use `AUTHSOME_MASTER_KEY_FILE`, mount it read-only, point Authsome at the mounted path, and treat that as a custom compose setup rather than the out-of-the-box quick start.

## Compose layout

`docker-compose.yml` runs three services:

- `authsome` exposes port `7998`, mounts `authsome-data` for logs and fallback secret material, and points the daemon at the internal Postgres and Redis services.
- `postgres` uses `postgres:16-alpine` with a health check and the `postgres-data` volume.
- `redis` uses `redis:7-alpine`, enables append-only persistence, and stores data in the `redis-data` volume.

The `authsome` service depends on healthy Postgres and Redis before startup. If either backend is missing, unreachable, or the optional Python driver is not installed, the daemon fails fast during boot.

## Startup and migrations

Authsome applies relational schema migrations at startup before it serves traffic. That means the daemon must be able to reach Postgres and Redis on boot. In production, treat a failing container start as a dependency or secret problem, not a warning to ignore.

When Postgres or Redis is configured but unreachable, startup aborts. If the image was built without the matching optional extras, startup also aborts because the required drivers are missing.

## Backup and restore

Back up these pieces together:

- Postgres data, because it stores the server registries.
- Redis persistence, if you enable or rely on it for encrypted vault blobs or shared runtime state.
- The master key or key file, because encrypted vault data cannot be decrypted without it.
- The `authsome-data` volume only if you want daemon logs or a fallback key file to survive container replacement.

Browser sessions remain stateless signed cookies for now, so there is no separate session database to back up yet.

For restores, bring back the master key first, then restore Postgres and Redis, then start the daemon.

## Upgrades

Pull the new image, restart the stack, and watch the health endpoint until it reports ready:

```bash
docker compose pull
docker compose up -d
curl http://localhost:7998/health
```

Because schema migrations run at startup, keep the Postgres and Redis services healthy during the upgrade. If the daemon restarts, re-check `/health` after the migration pass completes.

## Example production notes

- Use your platform secret store for `AUTHSOME_MASTER_KEY`. Only switch to `AUTHSOME_MASTER_KEY_FILE` if you have added a real secret mount and file path to your own compose file.
- Set `AUTHSOME_BASE_URL` to the public URL behind your reverse proxy.
- Keep `AUTHSOME_HOME` mounted only if you want local logs or fallback key material to persist.
- Consider pointing `AUTHSOME_POSTHOG_API_KEY` at a real analytics key only if you have opted in to telemetry.
