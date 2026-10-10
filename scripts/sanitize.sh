#!/usr/bin/env bash
# Mask values that identify your accounts before evidence goes into the repo.
#   scripts/sanitize.sh evidence-raw/phase1-tests.txt > docs/evidence/phase1-tests.txt
# It's a safety net, not a guarantee: read the output before you commit it.
set -euo pipefail
perl -pe '
  s/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/<jwt>/g;                  # access tokens
  s/\b(AKIA|ASIA)[0-9A-Z]{16}\b/<aws-access-key-id>/g;
  s/sk-ant-[A-Za-z0-9_-]+/<anthropic-api-key>/g;
  s/\b\d{12}\b/<aws-account-id>/g;
  s/\b(i|vol|sg|subnet|vpc|eni|eipalloc|ami)-[0-9a-f]{8,17}\b/$1-<redacted>/g;
  s/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/<uuid>/g;   # KMS key IDs, request IDs
  s/\b0oa[0-9A-Za-z]{17}\b/<okta-client-id>/g;
  s/\baus[0-9A-Za-z]{17}\b/<okta-auth-server-id>/g;
  s/\b[a-z0-9-]+\.okta\.com\b/<your-org>.okta.com/g;
  s/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/<email>/g;
  s/\b(?:\d{1,3}\.){3}\d{1,3}\b/<ip>/g;
' "$@"
