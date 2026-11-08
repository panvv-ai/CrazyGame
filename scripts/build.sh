#!/usr/bin/env bash
set -euo pipefail

image="${1:-crazygame}"

project_root="$(cd "$(dirname "$0")/.." && pwd)"

cd "${project_root}/frontend"
pnpm install --frozen-lockfile
pnpm build
cd "${project_root}"

docker build -t "${image}:latest" .
echo "Built ${image}:latest"
