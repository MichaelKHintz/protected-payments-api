# Phase 1 workload credential: an IAM user whose access key lives in a Kubernetes Secret.
# This is the weakest link in the lab on purpose; docs/credentials-design.md explains why
# and roles-anywhere.tf replaces it. The access key is created with the AWS CLI, never in
# Terraform, so the secret never lands in Terraform state.

resource "aws_iam_user" "vault" {
  #checkov:skip=CKV_AWS_273:Intentional Phase 1 workload credential, documented as a weakness and replaced by Roles Anywhere.
  name          = "${var.name}-token-vault"
  path          = "/workloads/"
  force_destroy = true # lets `terraform destroy` remove the access key you create by hand
  tags          = { Purpose = "token-vault workload credential - Phase 1" }
}

# The KMS key policies grant this user what it needs. This inline policy only takes things away:
# an explicit Deny wins over any Allow, so even if someone later attaches AdministratorAccess
# to this user, the key can still only do these three operations, on these two keys.
data "aws_iam_policy_document" "vault_guardrail" {
  statement {
    sid         = "DenyEverythingExceptVaultCrypto"
    effect      = "Deny"
    not_actions = ["kms:GenerateDataKey", "kms:Decrypt", "kms:GenerateMac"]
    resources   = ["*"]
  }
  statement {
    sid           = "DenyAnyOtherKey"
    effect        = "Deny"
    actions       = ["kms:*"]
    not_resources = [aws_kms_key.vault.arn, aws_kms_key.pan_hmac.arn]
  }
}

resource "aws_iam_user_policy" "vault_guardrail" {
  #checkov:skip=CKV_AWS_40:Deny-only guardrail that can only remove permissions from this one workload identity.
  name   = "guardrail-deny-all-but-vault-crypto"
  user   = aws_iam_user.vault.name
  policy = data.aws_iam_policy_document.vault_guardrail.json
}
