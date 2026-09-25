---
title: Kubernetes (Helm)
description: "Deploy UML-MCP on Kubernetes with the Helm chart, optionally protected by Entra ID."
---

# Kubernetes with Helm

The chart lives in
[`deploy/helm/uml-mcp`](https://github.com/antoinebou12/uml-mcp/tree/main/deploy/helm/uml-mcp).
It runs `uvicorn app:app` as a non-root user with a read-only root filesystem, and
includes probes, a PodDisruptionBudget and optional HPA / NetworkPolicy. Pods are
**stateless**, including the `entra-proxy` facade, so they scale horizontally with
no sticky sessions and no Redis.

## 1. Build and push the image

No public image is published yet:

```bash
docker build -t myregistry.azurecr.io/uml-mcp:1.4.0 .
docker push myregistry.azurecr.io/uml-mcp:1.4.0
```

## 2. Secrets (entra-proxy only)

```bash
kubectl create secret generic uml-mcp-auth \
  --from-literal=proxy-encryption-keys="$(python -m mcp_core.auth keygen --kid k1)" \
  --from-literal=entra-client-secret='<secret>'   # skip with workload identity
```

## 3. Install

```bash
helm upgrade --install uml-mcp deploy/helm/uml-mcp -n uml-mcp --create-namespace \
  --set image.repository=myregistry.azurecr.io/uml-mcp \
  --set ingress.enabled=true --set ingress.className=nginx \
  --set 'ingress.hosts={mcp.contoso.com}' \
  --set 'ingress.tls[0].secretName=uml-mcp-tls' --set 'ingress.tls[0].hosts={mcp.contoso.com}' \
  --set auth.mode=jwt \
  --set auth.resourceUrl=https://mcp.contoso.com/mcp \
  --set auth.entra.tenantId=<tenant-id> --set auth.entra.clientId=<api-client-id>
helm test uml-mcp -n uml-mcp   # /health = 200, POST /mcp = 401 with resource_metadata
```

Generate a values file with
`python -m mcp_core.auth generate helm-values --resource-url … --tenant-id … --client-id …`.

## Values

| Key | Default | Notes |
| --- | --- | --- |
| `image.repository` | **required** | Your registry |
| `auth.mode` | `none` | `jwt` or `entra-proxy` |
| `auth.resourceUrl` | – | Required when auth is on |
| `auth.entra.*` | – | `tenantId`, `clientId`, `appIdUri`, `cloud`, `tokenVersions` |
| `auth.config` | `{}` | Any extra JSON setting (see [configuration](configuration.md)), rendered into the `auth.json` ConfigMap |
| `auth.existingSecret` | – | Keys `proxy-encryption-keys`, `entra-client-secret` |
| `auth.preflight` | `warn` | `strict` blocks startup when IdP metadata lacks PKCE S256 |
| `workloadIdentity.enabled` | `false` | Adds the AKS workload identity annotation and label |
| `admin.enabled` | `false` | Read-only `/admin` console |
| `uvicorn.forwardedAllowIps` | `*` | Restrict to your ingress CIDR |
| `networkPolicy.enabled` | `false` | Allows ingress from the ingress namespace, plus DNS and HTTPS egress |

Entra access tokens can be large. On ingress-nginx set
`nginx.ingress.kubernetes.io/large-client-header-buffers: "4 32k"`.

## Operations

- **Rotate the proxy key:**
  1. Prepend a new `kN:` entry to `proxy-encryption-keys` and roll out.
  2. After the refresh-token lifetime (default 7 days), remove the old key.
- **Config errors:** a bad `auth.json` or a missing secret makes the pod exit at startup
  (fail closed). Check `kubectl logs`.
- **Health:** `/health` never depends on the IdP, so liveness is not affected by an
  Entra outage. Protected requests return 503 until keys can be fetched.
