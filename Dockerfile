# Stage 1: Build the Next.js static UI
FROM node:24-slim AS ui-builder
WORKDIR /app
COPY ui/ ./ui/
RUN npm install -g pnpm@10 --silent && \
    pnpm --dir ui install --frozen-lockfile && \
    pnpm --dir ui build

# Stage 2: Build the Python wheel
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS py-builder
WORKDIR /app
COPY . .
# Inject UI assets built in stage 1 before packaging the wheel
COPY --from=ui-builder /app/ui/out ./ui/out
RUN mkdir -p src/authsome/ui/web && \
    cp -R ui/out/. src/authsome/ui/web/ && \
    uv build --wheel --out-dir /dist

# Stage 3: Minimal runtime image
FROM python:3.13-slim AS runtime

RUN groupadd -r authsome && \
    useradd -r -g authsome -d /home/authsome -m -s /sbin/nologin authsome

COPY --from=py-builder /dist /dist
COPY --from=ghcr.io/astral-sh/uv:python3.13-bookworm-slim /usr/local/bin/uv /usr/local/bin/uv
RUN wheel="$(find /dist -maxdepth 1 -name '*.whl' -print -quit)" && \
    test -n "$wheel" && \
    uv pip install --system --no-cache "${wheel}[postgres,redis]" && \
    rm -rf /dist

ENV AUTHSOME_HOME=/data/authsome

EXPOSE 7998

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7998/health', timeout=3).read()"]

USER authsome

ENTRYPOINT ["authsome", "daemon", "serve"]
CMD ["--host", "0.0.0.0", "--port", "7998"]
