# Two customer managed keys:
#   vault    - symmetric key that wraps per-card data keys (envelope encryption), rotated automatically
#   pan_hmac - HMAC key that fingerprints card numbers for duplicate detection
# Separation of duties: the identity running Terraform can manage both keys but cannot use them,
# and token-vault can use them but cannot manage them.

data "aws_caller_identity" "current" {}

data "aws_iam_session_context" "current" {
  arn = data.aws_caller_identity.current.arn
}

locals {
  # The IAM role (or user) behind your current session, e.g. your Identity Center admin role.
  key_admin_arn = data.aws_iam_session_context.current.issuer_arn

  vault_principals = concat(
    [aws_iam_user.vault.arn],
    var.enable_roles_anywhere ? [aws_iam_role.vault_roles_anywhere[0].arn] : []
  )

  # Deliberately no Encrypt, Decrypt, GenerateDataKey, GenerateMac, ReEncrypt, or CreateGrant.
  key_admin_actions = [
    "kms:CreateAlias", "kms:DeleteAlias", "kms:UpdateAlias", "kms:DescribeKey",
    "kms:EnableKey", "kms:DisableKey", "kms:EnableKeyRotation", "kms:DisableKeyRotation",
    "kms:RotateKeyOnDemand", "kms:GetKeyPolicy", "kms:PutKeyPolicy", "kms:GetKeyRotationStatus",
    "kms:ListKeyRotations", "kms:ListResourceTags", "kms:TagResource", "kms:UntagResource",
    "kms:UpdateKeyDescription", "kms:ListGrants", "kms:RevokeGrant",
    "kms:ScheduleKeyDeletion", "kms:CancelKeyDeletion",
  ]

  only_from_the_node = {
    test     = "IpAddress"
    variable = "aws:SourceIp"
    values   = ["${aws_eip.node.public_ip}/32"]
  }
}

data "aws_iam_policy_document" "vault_key" {
  #checkov:skip=CKV_AWS_111:In a KMS key policy, "*" means this key only; usage is limited by principal and conditions.
  #checkov:skip=CKV_AWS_356:Same reason: key policies are attached to a single key.
  statement {
    sid = "KeyAdministrationWithoutUse"
    principals {
      type        = "AWS"
      identifiers = [local.key_admin_arn]
    }
    actions   = local.key_admin_actions
    resources = ["*"]
  }

  statement {
    sid = "TokenVaultEnvelopeEncryption"
    principals {
      type        = "AWS"
      identifiers = local.vault_principals
    }
    actions   = ["kms:GenerateDataKey", "kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:app"
      values   = ["token-vault"]
    }
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "kms:EncryptionContextKeys"
      values   = ["app", "token"]
    }
    condition {
      test     = local.only_from_the_node.test
      variable = local.only_from_the_node.variable
      values   = local.only_from_the_node.values
    }
  }
}

resource "aws_kms_key" "vault" {
  description              = "${var.name}: wraps token-vault data keys (envelope encryption)"
  key_usage                = "ENCRYPT_DECRYPT"
  customer_master_key_spec = "SYMMETRIC_DEFAULT"
  enable_key_rotation      = true
  rotation_period_in_days  = var.kms_rotation_days
  deletion_window_in_days  = 7
  policy                   = data.aws_iam_policy_document.vault_key.json
}

resource "aws_kms_alias" "vault" {
  name          = "alias/${var.name}-vault"
  target_key_id = aws_kms_key.vault.key_id
}

data "aws_iam_policy_document" "hmac_key" {
  #checkov:skip=CKV_AWS_111:In a KMS key policy, "*" means this key only; usage is limited by principal and conditions.
  #checkov:skip=CKV_AWS_356:Same reason: key policies are attached to a single key.
  statement {
    sid = "KeyAdministrationWithoutUse"
    principals {
      type        = "AWS"
      identifiers = [local.key_admin_arn]
    }
    actions   = local.key_admin_actions
    resources = ["*"]
  }

  statement {
    sid = "TokenVaultFingerprints"
    principals {
      type        = "AWS"
      identifiers = local.vault_principals
    }
    actions   = ["kms:GenerateMac"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:MacAlgorithm"
      values   = ["HMAC_SHA_256"]
    }
    condition {
      test     = local.only_from_the_node.test
      variable = local.only_from_the_node.variable
      values   = local.only_from_the_node.values
    }
  }
}

resource "aws_kms_key" "pan_hmac" {
  description              = "${var.name}: HMAC-SHA256 fingerprints of card numbers"
  key_usage                = "GENERATE_VERIFY_MAC"
  customer_master_key_spec = "HMAC_256"
  enable_key_rotation      = false # KMS can't rotate HMAC keys automatically; see docs/kms-key-management.md
  deletion_window_in_days  = 7
  policy                   = data.aws_iam_policy_document.hmac_key.json
}

resource "aws_kms_alias" "pan_hmac" {
  name          = "alias/${var.name}-pan-hmac"
  target_key_id = aws_kms_key.pan_hmac.key_id
}
