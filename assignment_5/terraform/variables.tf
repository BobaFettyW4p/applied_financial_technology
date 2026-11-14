variable "account_id" {
  description = "Cloudflare account ID (dashboard -> Workers & Pages -> Account details)."
  type        = string
}

variable "bucket_name" {
  description = "R2 bucket name. Must match bucket_name in ../wrangler.jsonc."
  type        = string
  default     = "treasury-pricing-data"
}

variable "bucket_location" {
  description = "R2 location hint: apac, eeur, enam, weur, wnam, oc."
  type        = string
  default     = "enam"
}
