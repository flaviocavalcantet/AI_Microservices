# SPIRE on Docker Compose

Workload identity for the AI platform using [SPIRE](https://spire.io/) with the **Docker workload attestor** — no Kubernetes required.

## Architecture

```
┌─────────────────┐     join token      ┌─────────────────┐
│  spire-server   │◄───────────────────│  spire-agent    │
│  trust domain:  │                     │  docker.sock    │
│  ai-platform.  │                     │  attestation    │
│  local          │                     └────────┬────────┘
└─────────────────┘                              │
                                                 │ SVIDs for labeled containers
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
            api-service                  auth-service                   ai-worker
   spiffe://.../workload/api-service   spiffe://.../workload/auth-service  ...
```

Each Compose service gets a SPIFFE ID via Docker label:

```yaml
labels:
  - "spire.service=api-service"
```

Registration selector: `docker:label:spire.service:api-service`

## Quick start

From the repository root:

```bash
# 1) Start platform + SPIRE
docker compose -f docker-compose.yml -f infrastructure/spire/docker/docker-compose.spire.yml up -d

# 2) Bootstrap join token + workload entries (Git Bash / WSL / Linux)
chmod +x infrastructure/spire/docker/scripts/bootstrap.sh
chmod +x infrastructure/spire/docker/registration/entries.sh
./infrastructure/spire/docker/scripts/bootstrap.sh
```

## Verify a workload SVID

```bash
docker compose -f docker-compose.yml -f infrastructure/spire/docker/docker-compose.spire.yml \
  exec spire-agent /opt/spire/bin/spire api fetch x509 \
  -spiffeID spiffe://ai-platform.local/workload/api-service
```

You should see an X.509-SVID and key material.

## Enable SPIRE-aware services

Set on `api-service` (and peers) in `docker-compose.yml`:

```yaml
environment:
  SPIRE_ENABLED: "true"
  SPIRE_TRUST_DOMAIN: ai-platform.local
  SPIRE_WORKLOAD_ID: spiffe://ai-platform.local/workload/api-service
  SPIRE_AGENT_SOCKET: unix:///tmp/spire-agent/public/api.sock
volumes:
  - spire_agent_socket:/tmp/spire-agent/public:ro
```

The named volume `spire_agent_socket` is created by `docker-compose.spire.yml`.

## User JWT + workload identity

| Layer | Mechanism | Docker setup |
|-------|-----------|--------------|
| User | Platform JWT (`Authorization: Bearer`) | `auth-service` issues; `api-service` validates |
| Workload | SPIFFE SVID (mTLS) | SPIRE agent + Docker labels |

See [docs/IDENTITY_PROPAGATION.md](../../../docs/IDENTITY_PROPAGATION.md).

## Migrating to Kubernetes later

When you move to K8s:

1. Replace Docker attestor with `k8s_psat` node attestor + `k8s` workload attestor.
2. Keep the same trust domain and SPIFFE ID paths (`spiffe://ai-platform.local/workload/...`).
3. Use SPIRE CSI driver or Envoy SDS for automatic SVID rotation in pods.

The Docker registration entries in `registration/entries.sh` are the reference for K8s `ClusterSPIFFEID` resources.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Agent won't start | Re-run `bootstrap.sh` to refresh `agent/conf/bootstrap.token` |
| No SVID for service | Confirm Compose `labels: spire.service=<name>` and re-run registration |
| `docker.sock` permission | On Linux, add user to `docker` group; agent mounts socket read-only |
| Bootstrap token expired | Tokens are short-lived; regenerate via `bootstrap.sh` |

## Files

| Path | Purpose |
|------|---------|
| `docker-compose.spire.yml` | SPIRE server, agent, bootstrap job |
| `server/conf/server.conf` | Server config (SQLite datastore) |
| `agent/conf/agent.conf` | Agent + Docker workload attestor |
| `registration/entries.sh` | Workload registration |
| `scripts/bootstrap.sh` | One-shot setup |
