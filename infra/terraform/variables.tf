variable "region" {
  description = "AWS region for every resource in the lab"
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Prefix for resource names"
  type        = string
  default     = "payments-lab"
}

variable "instance_type" {
  description = "EC2 size for the single k3s node (8 GiB is comfortable for k3s, Kyverno, cert-manager, and both services)"
  type        = string
  default     = "t3.large"
}

variable "k3s_version" {
  description = "Pinned k3s release; cert-manager 1.21 supports Kubernetes 1.33-1.36"
  type        = string
  default     = "v1.36.5+k3s1"
}

variable "kms_rotation_days" {
  description = "Automatic rotation period for the vault's KMS key"
  type        = number
  default     = 365
}

# --- Stretch goal: IAM Roles Anywhere (see roles-anywhere.tf) ---

variable "enable_roles_anywhere" {
  description = "Create the Roles Anywhere trust anchor, profile, and role for token-vault"
  type        = bool
  default     = false
}

variable "roles_anywhere_ca_pem" {
  description = "Public certificate (PEM) of the lab's private root CA; never the private key"
  type        = string
  default     = ""
}
