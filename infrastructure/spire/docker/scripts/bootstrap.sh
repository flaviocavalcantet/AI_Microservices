#!/usr/bin/env bash
# Bootstrap SPIRE server join token and register Docker Compose workloads.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPIRE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILES="-f docker-compose.yml -f ${SPIRE_DIR}/docker-compose.spire.yml"

cd "${SPIRE_DIR}/../.."

echo "==> Starting SPIRE server..."
docker compose ${COMPOSE_FILES} up -d spire-server

echo "==> Waiting for SPIRE server..."
for i in $(seq 1 30); do
  if docker compose ${COMPOSE_FILES} exec -T spire-server \
    /opt/spire/bin/spire-server healthcheck >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Generating agent join token..."
TOKEN=$(docker compose ${COMPOSE_FILES} exec -T spire-server \
  /opt/spire/bin/spire-server token generate \
  -spiffeID "spiffe://ai-platform.local/spire/agent/all" \
  -ttl 3600 | awk '/Token:/{print $2}')

if [ -z "${TOKEN}" ]; then
  echo "Failed to generate join token" >&2
  exit 1
fi

echo "${TOKEN}" > "${SPIRE_DIR}/docker/agent/conf/bootstrap.token"
echo "    Wrote bootstrap.token"

echo "==> Starting SPIRE agent..."
docker compose ${COMPOSE_FILES} up -d spire-agent

echo "==> Waiting for SPIRE agent..."
for i in $(seq 1 30); do
  if docker compose ${COMPOSE_FILES} exec -T spire-agent \
    /opt/spire/bin/spire-agent healthcheck >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "==> Registering workload entries..."
docker compose ${COMPOSE_FILES} run --rm spire-bootstrap

echo "==> SPIRE Docker bootstrap complete."
echo "    Verify: docker compose ${COMPOSE_FILES} exec spire-agent \\"
echo "      /opt/spire/bin/spire api fetch x509 -spiffeID spiffe://ai-platform.local/workload/api-service"
