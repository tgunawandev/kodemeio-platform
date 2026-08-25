# =============================================================================
# Terraform Remote State Backend
# =============================================================================
# Uses Hetzner Object Storage (S3-compatible) to store state remotely so that
# multiple operators and CI can share a consistent view of infrastructure.
#
# SETUP STEPS:
#   1. Create a bucket in Hetzner Object Storage:
#        kctl-hz storage bucket create kodemeio-terraform-state
#   2. Generate access keys:
#        kctl-hz storage keys create --bucket kodemeio-terraform-state
#   3. Export the keys as environment variables before running terraform:
#        export AWS_ACCESS_KEY_ID="<access-key>"
#        export AWS_SECRET_ACCESS_KEY="<secret-key>"
#   4. Uncomment the backend block below.
#   5. Run: terraform init -reconfigure
#
# NOTE: Do not put AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in terraform.tfvars
# or any committed file. Use environment variables or a secrets manager (1Password).
#
# Hetzner Object Storage endpoints by region:
#   Falkenstein : https://fsn1.your-objectstorage.com
#   Nuremberg   : https://nbg1.your-objectstorage.com
#   Helsinki    : https://hel1.your-objectstorage.com
# =============================================================================

# terraform {
#   backend "s3" {
#     # Bucket and key
#     bucket = "kodemeio-terraform-state"
#     key    = "platform/terraform.tfstate"
#
#     # Hetzner Object Storage endpoint (S3-compatible)
#     region   = "fsn1"
#     endpoint = "https://fsn1.your-objectstorage.com"
#
#     # Required flags for non-AWS S3
#     skip_credentials_validation = true
#     skip_metadata_api_check     = true
#     skip_region_validation      = true
#     force_path_style            = true
#
#     # State locking via DynamoDB is not supported on Hetzner Object Storage.
#     # Coordinate applies manually (or use Terraform Cloud for locking).
#   }
# }

# =============================================================================
# Module-level state note
# =============================================================================
# Each local module (modules/cloudflare, modules/hetzner) can also be
# operated independently with its own backend. When operating via this root
# module, a single state file covers all resources. Choose one approach:
#
#   A) Root module only (recommended for small teams)
#      - One state file: platform/terraform.tfstate
#      - One plan/apply cycle for all infra
#
#   B) Per-module state (advanced, for independent lifecycle)
#      - State file per module: cloudflare/terraform.tfstate, hetzner/terraform.tfstate
#      - Requires terraform_remote_state data sources to share outputs across modules
#      - Run terraform init/plan/apply separately in each module directory
# =============================================================================
