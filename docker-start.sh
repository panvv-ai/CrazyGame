#!/usr/bin/env bash
#
# CrazyGame one-command Docker build and deployment
# CrazyGame 一键构建并部署脚本
#
# Purpose / 目的:
#   Build crazygame:<TAG>, recreate the Compose container, and wait for health.
#   构建 crazygame:<TAG>，重建 Compose 容器，并等待健康检查通过。
#
# Usage / 用法:
#   ./docker-start.sh [OPTIONS] [TAG]
#   ./docker-start.sh              # WARN and fall back to TAG=v1
#   ./docker-start.sh v2           # Build and deploy crazygame:v2
#   ./docker-start.sh --no-build v2
#   ./docker-start.sh --no-cache v2
#   ./docker-start.sh --dry-run v2
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

BUILD_IMAGE=1
NO_CACHE=0
DRY_RUN=0
TAG=""

usage() {
  cat <<'EOF'
CrazyGame one-command Docker deployment
CrazyGame 一键 Docker 构建与部署

Usage / 用法:
  ./docker-start.sh [TAG]             (no TAG -> WARN, fallback to v1)
  ./docker-start.sh --no-build <TAG>
  ./docker-start.sh --no-cache <TAG>
  ./docker-start.sh --dry-run <TAG>

Examples / 示例:
  ./docker-start.sh                   # auto-select v1
  ./docker-start.sh v2
  ./docker-start.sh --no-build v2
  CRAZYGAME_NODE_IMAGE=docker.m.daocloud.io/library/node:22-alpine \
  CRAZYGAME_PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim \
    ./docker-start.sh v2

No TAG defaults to v1 with a warning.
未传 TAG 时会输出 WARN，并自动使用 v1。
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

warn() {
  if [[ -t 2 && -z "${NO_COLOR:-}" ]]; then
    printf '\033[33mWARN:\033[0m %s\n' "$*" >&2
  else
    printf 'WARN: %s\n' "$*" >&2
  fi
}

docker_retry() {
  local description="$1"
  shift
  local attempt
  for attempt in 1 2 3; do
    echo "→ ${description} (attempt ${attempt}/3)"
    if "$@"; then
      return 0
    fi
    if [[ "$attempt" -lt 3 ]]; then
      sleep "$((attempt * 2))"
    fi
  done
  return 1
}

ensure_base_image() {
  local image="$1"
  if docker image inspect "$image" >/dev/null 2>&1; then
    echo "✓ Base image cached: ${image}"
    return 0
  fi
  docker_retry "Pulling base image ${image}" docker pull "$image"
}

for argument in "$@"; do
  case "$argument" in
    -h|--help)
      usage
      exit 0
      ;;
    --no-build)
      BUILD_IMAGE=0
      ;;
    --no-cache)
      NO_CACHE=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -*)
      fail "Unknown option: ${argument}"
      ;;
    *)
      [[ -z "$TAG" ]] || fail "Only one image tag may be supplied."
      TAG="$argument"
      ;;
  esac
done

if [[ -z "$TAG" ]]; then
  warn "未指定镜像 TAG，自动使用 v1。"
  warn "No image tag supplied; falling back to v1."
  TAG="v1"
fi

if [[ ! "$TAG" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
  fail "Invalid Docker image tag: ${TAG}"
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  command -v docker >/dev/null 2>&1 || fail "docker is not installed."
  docker compose version >/dev/null 2>&1 || fail "docker compose is unavailable."
fi

IMAGE="crazygame:${TAG}"
NODE_IMAGE="${CRAZYGAME_NODE_IMAGE:-node:22-alpine}"
PYTHON_IMAGE="${CRAZYGAME_PYTHON_IMAGE:-python:3.11-slim}"

echo "============================================================"
echo "  CrazyGame Docker deployment"
echo "============================================================"
echo "Image        : ${IMAGE}"
echo "Node base    : ${NODE_IMAGE}"
echo "Python base  : ${PYTHON_IMAGE}"
echo "Build        : $([[ "$BUILD_IMAGE" -eq 1 ]] && echo yes || echo no)"
echo "No cache     : $([[ "$NO_CACHE" -eq 1 ]] && echo yes || echo no)"
echo

if [[ "$BUILD_IMAGE" -eq 1 ]]; then
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "→ Base images will be pulled only when missing."
    echo "+ docker build --build-arg CRAZYGAME_TAG=${TAG} --build-arg NODE_IMAGE=${NODE_IMAGE} --build-arg PYTHON_IMAGE=${PYTHON_IMAGE}$([[ "$NO_CACHE" -eq 1 ]] && echo ' --no-cache') -f Dockerfile -t ${IMAGE} ."
  else
    ensure_base_image "$NODE_IMAGE" || {
      echo
      echo "Docker Hub metadata download failed." >&2
      echo "Configure Docker Desktop → Settings → Resources → Proxies," >&2
      echo "or override CRAZYGAME_NODE_IMAGE / CRAZYGAME_PYTHON_IMAGE with a reachable mirror." >&2
      exit 1
    }
    ensure_base_image "$PYTHON_IMAGE" || {
      echo
      echo "Docker Hub metadata download failed." >&2
      echo "Configure Docker Desktop → Settings → Resources → Proxies," >&2
      echo "or override CRAZYGAME_NODE_IMAGE / CRAZYGAME_PYTHON_IMAGE with a reachable mirror." >&2
      exit 1
    }

    BUILD_ARGS=(
      --build-arg "CRAZYGAME_TAG=${TAG}"
      --build-arg "NODE_IMAGE=${NODE_IMAGE}"
      --build-arg "PYTHON_IMAGE=${PYTHON_IMAGE}"
    )
    if [[ "$NO_CACHE" -eq 1 ]]; then
      BUILD_ARGS+=(--no-cache)
    fi
    docker_retry \
      "Building ${IMAGE}" \
      docker build "${BUILD_ARGS[@]}" -f Dockerfile -t "$IMAGE" . || {
        echo
        echo "Image build failed." >&2
        echo "For registry EOF/timeouts, set Docker Desktop proxy or use reachable base-image mirrors." >&2
        exit 1
      }
  fi
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "+ CRAZYGAME_TAG=${TAG} docker compose up -d --no-build --force-recreate"
  echo
  echo "Dry run complete."
  exit 0
fi

docker image inspect "$IMAGE" >/dev/null 2>&1 || {
  fail "Image ${IMAGE} does not exist. Run without --no-build first."
}

echo
echo "→ Recreating CrazyGame container with ${IMAGE}"
CRAZYGAME_TAG="$TAG" docker compose up -d --no-build --force-recreate

CONTAINER_ID="$(CRAZYGAME_TAG="$TAG" docker compose ps -q crazygame)"
[[ -n "$CONTAINER_ID" ]] || fail "CrazyGame container was not created."

echo "→ Waiting for health check"
for _ in $(seq 1 60); do
  STATUS="$(
    docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
      "$CONTAINER_ID" 2>/dev/null || true
  )"
  case "$STATUS" in
    healthy|running)
      echo
      echo "✓ Deployment complete"
      echo "  URL  : http://127.0.0.1:8000"
      echo "  Image: ${IMAGE}"
      echo "  Logs : CRAZYGAME_TAG=${TAG} docker compose logs -f crazygame"
      echo "  Stop : docker compose down"
      exit 0
      ;;
    exited|dead)
      break
      ;;
  esac
  sleep 1
done

echo
echo "Container did not become healthy." >&2
CRAZYGAME_TAG="$TAG" docker compose logs --tail=120 crazygame >&2 || true
exit 1
