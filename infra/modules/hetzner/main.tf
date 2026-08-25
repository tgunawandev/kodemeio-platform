terraform {
  required_version = ">= 1.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }

  # Optional: S3 backend for remote state
  # backend "s3" {
  #   bucket                      = "kodemeio-terraform-state"
  #   key                         = "hetzner/terraform.tfstate"
  #   region                      = "fsn1"
  #   endpoint                    = "https://fsn1.your-objectstorage.com"
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  #   force_path_style            = true
  # }
}

provider "hcloud" {
  token = var.hcloud_token
}

# Available locations
data "hcloud_locations" "all" {}

# Available server types
data "hcloud_server_types" "all" {}
