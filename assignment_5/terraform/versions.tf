terraform {
  required_version = ">= 1.6"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  # State lives in a separate, manually created R2 bucket (see README.md).
  # The endpoint is passed at init time:
  #   -backend-config='endpoints={s3="https://<account_id>.r2.cloudflarestorage.com"}'
  # Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY (R2 API token).
  backend "s3" {
    bucket                      = "treasury-pricing-tfstate"
    key                         = "assignment_5/terraform.tfstate"
    region                      = "auto"
    use_lockfile                = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_s3_checksum            = true
  }
}

# Auth: export CLOUDFLARE_API_TOKEN (scoped token, not the Global API Key).
provider "cloudflare" {}
