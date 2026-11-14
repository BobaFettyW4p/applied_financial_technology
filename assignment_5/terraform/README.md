# Terraform

Manages the R2 bucket. Wrangler deploys the Worker.

```bash
export CLOUDFLARE_API_TOKEN=...   # scoped token: Account > Workers R2 Storage > Edit
cp terraform.tfvars.example terraform.tfvars   # set account_id
terraform init
terraform plan
terraform apply
cd .. && npm run data:remote && npm run deploy
```

If you already created the bucket in the dashboard, import it first:
`terraform import cloudflare_r2_bucket.pricing_data <account_id>/treasury-pricing-data`

Later: add the zone and Worker custom domain once DNS is delegated, and move
state to R2 (S3 backend with the R2 endpoint) before sharing it with a team.

## CI/CD (GitHub Actions)

`.github/workflows/assignment5.yml` runs tests on every PR, `terraform plan` on
PRs, and on push to `main`: apply, upload data to R2, `wrangler deploy`.

One-time bootstrap (state bucket can't be managed by the config that uses it):
1. Create R2 bucket `treasury-pricing-tfstate` (dashboard or `npx wrangler r2 bucket create`).
2. R2 -> Manage API tokens -> create an S3 token with Object Read & Write on that bucket.
3. Create a Cloudflare API token with: Workers Scripts Edit, Workers R2 Storage Edit.
4. Repo secrets: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`,
   `TF_STATE_ACCESS_KEY_ID`, `TF_STATE_SECRET_ACCESS_KEY`.
5. Migrate existing local state (if any):
   `terraform init -migrate-state -backend-config='endpoints={s3="https://<account_id>.r2.cloudflarestorage.com"}'`
