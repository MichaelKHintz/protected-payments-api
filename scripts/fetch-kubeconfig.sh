#!/usr/bin/env bash
# Copy the k3s admin kubeconfig to ~/.kube/payments-lab.yaml through SSM (no SSH, no open ports).
# It contains a cluster-admin client key: it stays outside the repo, readable only by you.
set -euo pipefail
INSTANCE_ID=$(terraform -chdir=infra/terraform output -raw instance_id)
CMD_ID=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
  --parameters 'commands=["cat /etc/rancher/k3s/k3s.yaml"]' --query Command.CommandId --output text)
aws ssm wait command-executed --command-id "$CMD_ID" --instance-id "$INSTANCE_ID"
mkdir -p ~/.kube
umask 077
aws ssm get-command-invocation --command-id "$CMD_ID" --instance-id "$INSTANCE_ID" \
  --query StandardOutputContent --output text > ~/.kube/payments-lab.yaml
echo "Wrote ~/.kube/payments-lab.yaml. Run: export KUBECONFIG=~/.kube/payments-lab.yaml"
