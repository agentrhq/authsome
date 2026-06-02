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
RUN pip install --no-cache-dir /dist/*.whl && rm -rf /dist

ENV AUTHSOME_HOME=/data/authsome

EXPOSE 7998

VOLUME ["/data/authsome"]

USER authsome

ENTRYPOINT ["authsome", "daemon", "serve"]
CMD ["--host", "0.0.0.0", "--port", "7998"]
