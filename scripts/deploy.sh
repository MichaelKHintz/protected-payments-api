#!/usr/bin/env bash
# Apply the manifests in k8s/base with the image digests from the latest build.
# Digests come from the build job summary, or from crane if they aren't set:
#   TOKEN_VAULT_DIGEST=sha256:... PAYMENTS_API_DIGEST=sha256:... scripts/deploy.sh
set -euo pipefail
REPO=ghcr.io/michaelkhintz/protected-payments-api
TAG="sha-$(git rev-parse HEAD)"
TOKEN_VAULT_DIGEST=${TOKEN_VAULT_DIGEST:-$(crane digest "$REPO/token-vault:$TAG")}
PAYMENTS_API_DIGEST=${PAYMENTS_API_DIGEST:-$(crane digest "$REPO/payments-api:$TAG")}
echo "token-vault  @ $TOKEN_VAULT_DIGEST"
echo "payments-api @ $PAYMENTS_API_DIGEST"

for f in namespace networkpolicies certificates token-vault payments-api; do
  [ -f "k8s/base/$f.yaml" ] || continue  # certificates.yaml arrives in Phase 2
  sed -e "s|TOKEN_VAULT_DIGEST|$TOKEN_VAULT_DIGEST|g" -e "s|PAYMENTS_API_DIGEST|$PAYMENTS_API_DIGEST|g" \
    "k8s/base/$f.yaml" | kubectl apply -f -
done
kubectl -n payments rollout status deploy/token-vault --timeout=120s
kubectl -n payments rollout status deploy/payments-api --timeout=120s
