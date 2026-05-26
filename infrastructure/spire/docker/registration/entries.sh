#!/bin/sh
# Register platform workload entries for Docker Compose services.
# Run after spire-server and spire-agent are healthy (see bootstrap.sh).

set -e

SPIRE_SERVER_CONTAINER="${SPIRE_SERVER_CONTAINER:-ai_platform_spire_server}"
TRUST_DOMAIN="${SPIRE_TRUST_DOMAIN:-ai-platform.local}"

register_workload() {
  service_name="$1"
  spiffe_id="spiffe://${TRUST_DOMAIN}/workload/${service_name}"

  echo "Registering ${spiffe_id} (docker label: spire.service=${service_name})"

  docker exec "${SPIRE_SERVER_CONTAINER}" \
    /opt/spire/bin/spire-server entry create \
    -spiffeID "${spiffe_id}" \
    -parentID "spiffe://${TRUST_DOMAIN}/spire/agent/all" \
    -selector "docker:label:spire.service:${service_name}" \
    || true
}

register_workload "api-service"
register_workload "auth-service"
register_workload "ai-worker"
register_workload "notification-service"

echo "SPIRE registration complete."
