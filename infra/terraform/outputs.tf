output "vault_kms_key_arn" {
  value = aws_kms_key.vault.arn
}

output "hmac_kms_key_arn" {
  value = aws_kms_key.pan_hmac.arn
}

output "vault_iam_user" {
  value = aws_iam_user.vault.name
}

output "key_admin_arn" {
  description = "The identity that can manage, but not use, the KMS keys"
  value       = local.key_admin_arn
}

output "roles_anywhere" {
  value = var.enable_roles_anywhere ? {
    trust_anchor_arn = aws_rolesanywhere_trust_anchor.lab_ca[0].arn
    profile_arn      = aws_rolesanywhere_profile.vault[0].arn
    role_arn         = aws_iam_role.vault_roles_anywhere[0].arn
  } : null
}
