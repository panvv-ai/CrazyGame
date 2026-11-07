#!/usr/bin/env bash
set -euo pipefail

version="${1:-latest}"

cd "$(dirname "$0")/frontend"
pnpm install --frozen-lockfile
pnpm build
cd ..

docker build -t "panwatchdiy:${version}" .
echo "Built panwatchdiy:${version}"
