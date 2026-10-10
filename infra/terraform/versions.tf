terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
  }
  # Local state for this short-lived lab. It is gitignored because it holds resource IDs and ARNs.
  # For anything longer-lived, reuse the encrypted S3 backend pattern from Project 1.
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "protected-payments-api"
      ManagedBy = "terraform"
      DataClass = "test-data-only"
    }
  }
}
