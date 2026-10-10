#!/usr/bin/env bash
# Forward localhost:6443 to the k3s API server through SSM Session Manager. Leave it running in its own terminal.
set -euo pipefail
INSTANCE_ID=$(terraform -chdir=infra/terraform output -raw instance_id)
exec aws ssm start-session --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["6443"],"localPortNumber":["6443"]}'
