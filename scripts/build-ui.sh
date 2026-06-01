#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="${ROOT_DIR}/ui"
TARGET_DIR="${ROOT_DIR}/src/authsome/ui/web"
UV_BIN="${UV:-uv}"

"${UV_BIN}" run pnpm --dir "${UI_DIR}" install --frozen-lockfile
"${UV_BIN}" run pnpm --dir "${UI_DIR}" build

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"
cp -R "${UI_DIR}/out/." "${TARGET_DIR}/"
touch "${TARGET_DIR}/.gitkeep"
