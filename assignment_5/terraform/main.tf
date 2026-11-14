# Durable infrastructure only. The Worker code and its R2 binding are deployed
# with Wrangler (`npm run deploy`), so Terraform and Wrangler never both manage
# the same Worker.

resource "cloudflare_r2_bucket" "pricing_data" {
  account_id    = var.account_id
  name          = var.bucket_name
  location      = var.bucket_location
  storage_class = "Standard"
}
