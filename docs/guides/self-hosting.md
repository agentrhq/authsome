# Self-hosting Authsome

Run a persistent Authsome daemon in a container — useful for CI runners, shared agent hosts, or any environment where installing Python tooling is inconvenient.

## Quick start

```bash
# Clone the repo (or copy docker-compose.yml)
git clone https://github.com/agentrhq/authsome.git
cd authsome

# Start the daemon
docker compose up -d

# Verify it's running
curl http://localhost:7998/health
```

The daemon is now available at `http://localhost:7998`.

Point agents at it by setting:

```bash
export AUTHSOME_DAEMON_URL=http://localhost:7998
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `AUTHSOME_HOME` | `/data/authsome` | Root directory for credentials, keys, and the database |
| `AUTHSOME_HOST` | `0.0.0.0` | Interface the daemon binds to inside the container |
| `AUTHSOME_PORT` | `7998` | TCP port |
| `AUTHSOME_SERVER_BASE_URL` | _(derived from host:port)_ | Public URL used to build OAuth callback URLs. **Must be set when behind a reverse proxy.** |
| `AUTHSOME_ENCRYPTION_MODE` | `local_key` | `local_key` stores the master key on disk; `keyring` uses the OS keyring (not available in containers) |
| `AUTHSOME_LOG_LEVEL` | `info` | Uvicorn log level (`debug`, `info`, `warning`, `error`) |
| `AUTHSOME_ANALYTICS` | `1` | Set to `0` to disable telemetry |

## Volume

All credentials and keys live at `AUTHSOME_HOME` (`/data/authsome` by default), which is declared as a Docker named volume.

```
/data/authsome/
  server/
    authsome.db        # SQLite database (identities, principals, vaults)
    master.key         # Vault encryption key — back this up
    kv_store/          # Encrypted credential blobs
  client/
    logs/
```

> **Keep `master.key` safe.** Without it, stored credentials cannot be decrypted.

## Upgrading

```bash
docker compose pull        # fetch the latest image
docker compose up -d       # restart with zero downtime (data volume is preserved)
```

## Backup and restore

```bash
# Backup
docker run --rm -v authsome-data:/data/authsome -v $(pwd):/backup \
  busybox tar czf /backup/authsome-backup.tar.gz -C /data/authsome .

# Restore
docker run --rm -v authsome-data:/data/authsome -v $(pwd):/backup \
  busybox tar xzf /backup/authsome-backup.tar.gz -C /data/authsome
```

## TLS with Caddy

Add a Caddy sidecar to the compose file for automatic HTTPS:

```yaml
services:
  authsome:
    image: authsome:latest
    restart: unless-stopped
    expose:
      - "7998"
    environment:
      AUTHSOME_SERVER_BASE_URL: https://auth.example.com
    volumes:
      - authsome-data:/data/authsome

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    depends_on:
      - authsome

volumes:
  authsome-data:
  caddy-data:
```

`Caddyfile`:

```
auth.example.com {
  reverse_proxy authsome:7998
}
```

## Building the image locally

```bash
docker build -t authsome:local .
```

The build is multi-stage:

1. **`ui-builder`** — Node 24 + pnpm compiles the Next.js dashboard to static HTML.
2. **`py-builder`** — uv bundles the Python package (including the built UI) into a wheel.
3. **`runtime`** — Slim Python 3.13 image; installs the wheel, runs as a non-root `authsome` user.
