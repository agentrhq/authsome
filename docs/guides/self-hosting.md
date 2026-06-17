# Self-hosting Authsome

Run Authsome as a production service with Postgres for the server registries and Redis for shared runtime state plus the encrypted vault raw KV layer.

## Quick start

The repository ships a compose file that wires the daemon to Postgres and Redis. Set a stable master key source first, then bring the stack up and verify the root health check.

```bash
export AUTHSOME_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export AUTHSOME_MASTER_KEY="$(openssl rand -base64 32)"
export AUTHSOME_UI_SESSION_KEY="$(openssl rand -base64 32)"
docker compose up -d
curl http://localhost:7998/health
```

The daemon should answer on `http://localhost:7998`. The root `/health` endpoint is the container health target used by the image and by `docker compose`.
The included compose file reads `AUTHSOME_MASTER_KEY` and `AUTHSOME_UI_SESSION_KEY` from the host environment. The `_FILE` variants are supported by Authsome itself, but if you want to use file-mounted secrets you must add those mounts and pass the file paths yourself in a custom compose file.

## First run

After `/health` responds, point the CLI at the daemon and run onboarding:

```bash
authsome onboard --base-url http://localhost:7998
```

For a hosted deployment, use the same public URL that you configured as `AUTHSOME_BASE_URL`:

```bash
authsome onboard --base-url https://authsome.example.com
```

Onboarding creates a local Identity, registers it with the daemon, and opens the browser claim flow. Complete the claim to bind the Identity to a Principal and its default Vault before running agent commands against the hosted daemon.

## What this deployment does

- Postgres stores the relational server registries: identities, principals, vaults, claims, and bindings.
- Redis stores shared runtime state and, when configured, backs the raw KV layer that holds encrypted vault blobs.
- The Authsome container keeps only a small home directory for logs and optional fallback key material. Primary production state lives in Postgres and Redis.
- Browser sessions remain stateless signed cookies for now, so every replica must use the same `AUTHSOME_UI_SESSION_KEY`. Any future stateful browser session store is tracked separately.

## Prerequisites

- Docker and Docker Compose v2.
- Postgres 16.
- Redis 7.
- Stable `AUTHSOME_MASTER_KEY` and `AUTHSOME_UI_SESSION_KEY` values for the included compose file.

Do not commit production secrets. Use your platform secret store or Docker secrets for the included compose file. If you prefer `_FILE` variables, wire up your own secret mounts and file paths in a custom compose file.

## Required environment variables

| Variable | Default | Description |
|---|---|---|
| `AUTHSOME_ENV` | `dev` | Runtime mode. Set to `prod` for production deployments; in `prod`, `AUTHSOME_DATABASE_URL` and `AUTHSOME_REDIS_URL` are required. |
| `AUTHSOME_DATABASE_URL` | none | Postgres DSN for the daemon-owned registries. The compose file points this at the bundled Postgres service. |
| `AUTHSOME_REDIS_URL` | none | Redis URL for shared runtime state and the encrypted vault raw KV backend. |
| `AUTHSOME_POSTGRES_PASSWORD` | none | Required password used by the bundled Postgres service and the daemon's database URL. |
| `AUTHSOME_POSTGRES_USER` | `authsome` | Postgres role name used by the bundled compose file. |
| `AUTHSOME_POSTGRES_DB` | `authsome` | Postgres database name used by the bundled compose file. |
| `AUTHSOME_MASTER_KEY` | none | Base64-encoded 32-byte master key. Highest priority when set. |
| `AUTHSOME_MASTER_KEY_FILE` | none | Advanced alternative for custom compose or platform-secret setups where you mount a file into the container and point Authsome at that path yourself. |
| `AUTHSOME_UI_SESSION_KEY` | none | Shared signing secret for stateless browser session JWTs. Must be identical on every replica. |
| `AUTHSOME_UI_SESSION_KEY_FILE` | none | Advanced alternative for custom compose or platform-secret setups where you mount the UI session key into the container. |
| `AUTHSOME_BASE_URL` | `http://localhost:7998` | Public daemon URL used to build OAuth callback URLs. Set this to the reverse-proxy URL in production. |
| `AUTHSOME_HOME` | `/data/authsome` | Home directory for logs, generated fallback secrets, and other daemon-local files. |
| `AUTHSOME_HOST` | `0.0.0.0` | Host interface the daemon binds to inside the container. |
| `AUTHSOME_PORT` | `7998` | TCP port the daemon listens on. |
| `AUTHSOME_DO_NOT_TRACK` | `1` | Set to `0` only if you intentionally want telemetry enabled. |
| `AUTHSOME_POSTHOG_API_KEY` | none | Enables PostHog analytics when present and telemetry is not opted out. |
| `AUTHSOME_POSTHOG_HOST` | `https://us.i.posthog.com` | Override the PostHog ingestion host if needed. |

The daemon still accepts the legacy `DATABASE_URL` alias, but production deployments should set `AUTHSOME_DATABASE_URL`. The included compose file sets `AUTHSOME_ENV=prod`, which makes the Postgres and Redis URLs mandatory at startup.
The included compose file hard-requires `AUTHSOME_MASTER_KEY` and `AUTHSOME_UI_SESSION_KEY` from the host environment; it does not mount secret files or pass `_FILE` paths for you.

## Secret resolution

On startup, Authsome resolves the master key and UI session signing key in this order:

1. `AUTHSOME_MASTER_KEY`
2. `AUTHSOME_MASTER_KEY_FILE`, or the default server key file at `AUTHSOME_HOME/server/master.key`
3. The OS keyring entry
4. A generated fallback, stored in the keyring when possible, otherwise written to the default server key file

`AUTHSOME_MASTER_KEY` and `AUTHSOME_UI_SESSION_KEY` are the strongest and cleanest production options for the included compose file because they avoid writing secret material to disk. If you use `_FILE` variables, mount them read-only, point Authsome at the mounted paths, and treat that as a custom compose setup rather than the out-of-the-box quick start.

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
- The UI session key or key file, because stateless browser session JWTs cannot be verified consistently across replicas without it.
- The `authsome-data` volume only if you want daemon logs or a fallback key file to survive container replacement.

Browser sessions remain stateless signed cookies for now, so there is no separate session database to back up yet.

For restores, bring back the master key first, then restore Postgres and Redis, then start the daemon.

## Upgrades

Pull the new image, restart the stack, and watch the health endpoint until it responds:

```bash
docker compose pull
docker compose up -d
curl http://localhost:7998/health
```

Because schema migrations run at startup, keep the Postgres and Redis services healthy during the upgrade. If the daemon restarts, re-check `/health` after the migration pass completes.

## Example production notes

- Use your platform secret store for `AUTHSOME_MASTER_KEY` and `AUTHSOME_UI_SESSION_KEY`. Only switch to `_FILE` variables if you have added real secret mounts and file paths to your own compose file.
- Set `AUTHSOME_BASE_URL` to the public URL behind your reverse proxy.
- Terminate TLS at your reverse proxy, such as Caddy, nginx, Traefik, or your platform load balancer. The Authsome container serves plain HTTP on port `7998` inside the private network.
- Keep `AUTHSOME_HOME` mounted only if you want local logs or fallback key material to persist.
- Consider pointing `AUTHSOME_POSTHOG_API_KEY` at a real analytics key only if you have opted in to telemetry.
