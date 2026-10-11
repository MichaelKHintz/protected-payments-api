#!/usr/bin/env bash
# Print an Auth0 client-credentials access token, or Auth0's error on stderr.
#   scripts/get-token.sh checkout "payments:write payments:read"
#   scripts/get-token.sh support  "support:summarize payments:read"
#   scripts/get-token.sh checkout "" api://wrong-audience      # optional audience override
# Reads the issuer and client credentials from .env.okta (gitignored). The secret is passed to curl
# on stdin, so it never appears in the process list or your shell history.
set -euo pipefail
source "$(dirname "$0")/../.env.okta"
case "${1:-}" in
  checkout) ID=$CHECKOUT_CLIENT_ID; SECRET=$CHECKOUT_CLIENT_SECRET ;;
  support)  ID=$SUPPORT_CLIENT_ID;  SECRET=$SUPPORT_CLIENT_SECRET ;;
  *) echo "usage: $0 checkout|support \"<scopes>\" [audience]" >&2; exit 2 ;;
esac
SCOPE=${2:-}
AUDIENCE=${3:-api://payments-lab}
EXTRA=()
[ -n "$SCOPE" ] && EXTRA=(--data-urlencode "scope=$SCOPE")
RESPONSE=$({
  printf 'data-urlencode = "client_id=%s"\n' "$ID"
  printf 'data-urlencode = "client_secret=%s"\n' "$SECRET"
} | curl -sS -K - -X POST "${OKTA_ISSUER%/}/oauth/token" \
  -H "Accept: application/json" \
  -d grant_type=client_credentials \
  --data-urlencode "audience=$AUDIENCE" \
  "${EXTRA[@]+"${EXTRA[@]}"}")
TOKEN=$(jq -r '.access_token // empty' <<<"$RESPONSE")
if [ -z "$TOKEN" ]; then
  echo "$RESPONSE" | jq . >&2   # e.g. {"error": "access_denied", ...}
  exit 1
fi
echo "$TOKEN"
