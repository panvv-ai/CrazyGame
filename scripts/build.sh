#!/usr/bin/env bash
set -euo pipefail

tag="${1:-latest}"
image="crazygame:${tag}"

project_root="$(cd "$(dirname "$0")/.." && pwd)"

cd "${project_root}/frontend"
pnpm install --frozen-lockfile
pnpm build
cd "${project_root}"

docker build --build-arg CRAZYGAME_TAG="${tag}" -t "${image}" .
echo "Built ${image}"
