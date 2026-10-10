# Stretch goal: swap the IAM user's static access key for short-lived credentials.
# token-vault presents the X.509 certificate it already has from cert-manager (Phase 2);
# IAM Roles Anywhere checks it against the lab CA and returns one-hour STS credentials.
# Enable by setting enable_roles_anywhere and roles_anywhere_ca_pem in terraform.tfvars (gitignored).

resource "aws_rolesanywhere_trust_anchor" "lab_ca" {
  count   = var.enable_roles_anywhere ? 1 : 0
  name    = "${var.name}-private-ca"
  enabled = true
  source {
    source_type = "CERTIFICATE_BUNDLE"
    source_data {
      x509_certificate_data = var.roles_anywhere_ca_pem
    }
  }
}

resource "aws_iam_role" "vault_roles_anywhere" {
  count                = var.enable_roles_anywhere ? 1 : 0
  name                 = "${var.name}-token-vault-ra"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "rolesanywhere.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession", "sts:SetSourceIdentity"]
      Condition = {
        # Only certificates issued under our trust anchor (prevents confused-deputy use)...
        ArnEquals = { "aws:SourceArn" = aws_rolesanywhere_trust_anchor.lab_ca[0].arn }
        # ...and only the certificate that names token-vault's workload identity.
        StringEquals = { "aws:PrincipalTag/x509SAN/URI" = "spiffe://payments-lab/ns/payments/sa/token-vault" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "vault_roles_anywhere_guardrail" {
  count  = var.enable_roles_anywhere ? 1 : 0
  name   = "guardrail-deny-all-but-vault-crypto"
  role   = aws_iam_role.vault_roles_anywhere[0].id
  policy = data.aws_iam_policy_document.vault_guardrail.json
}

resource "aws_rolesanywhere_profile" "vault" {
  count            = var.enable_roles_anywhere ? 1 : 0
  name             = "${var.name}-token-vault"
  enabled          = true
  role_arns        = [aws_iam_role.vault_roles_anywhere[0].arn]
  duration_seconds = 3600
}
