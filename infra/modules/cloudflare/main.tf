# Cloudflare Provider Configuration
# https://registry.terraform.io/providers/cloudflare/cloudflare/latest/docs

terraform {
  required_version = ">= 1.0"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# Get account details
data "cloudflare_accounts" "main" {
  name = var.cloudflare_account_name
}

locals {
  account_id = data.cloudflare_accounts.main.accounts[0].id
}
