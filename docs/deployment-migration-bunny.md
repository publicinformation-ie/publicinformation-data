# Migration Plan: Hetzner → Bunny.net Edge Storage + Pull Zone

## Overview

Migrate the static Astro site from Hetzner SFTP deployment to Bunny.net Edge Storage + Pull Zone, keeping the existing domain `publicinformation.ie` with automatic SSL. The deployment will continue to trigger from Codeberg pushes to `main` branch.

**Note**: Bunny.net has discontinued Edge Sites (formerly Bunny Pages). The current recommended approach for static site hosting is to use Edge Storage combined with a Pull Zone.

---

## Phase 1: Bunny.net Configuration (Manual Setup)

### Step 1: Create Storage Zone
1. Log in to [Bunny.net Dashboard](https://dash.bunny.net/)
2. Navigate to **Storage** → **Storage Zones**
3. Click **Add Storage Zone**
4. Configure:
   - **Name**: `publicinformation-ie` (this becomes your zone name, used in API URLs)
   - **Region**: Select closest to your audience (e.g., `de` for Europe)
   - **Replication Regions**: Enable additional regions if desired for global performance
5. Note the **Storage Zone Name** (needed for API deployment)

### Step 2: Create Pull Zone
1. In Bunny.net dashboard, navigate to **CDN** → **Pull Zones**
2. Click **Add Pull Zone**
3. Configure:
   - **Name**: `publicinformation.ie`
   - **Origin URL**: Use your Storage Zone URL (e.g., `https://publicinformation-ie.bunnycdn.com`)
   - **Origin Type**: Storage Zone
   - **Enable Bunlink**: Optional (recommended for better performance)
   - **Enable Perma-Cache**: Enable for static sites (improves cache hit rate)
4. Note the **Pull Zone ID** (numeric ID, needed for cache purging)

### Step 3: Configure Custom Domain
1. In your Pull Zone settings, go to **Hostnames**
2. Add `publicinformation.ie` and `www.publicinformation.ie`
3. Bunny will provide DNS records to verify ownership

### Step 4: Verify DNS Configuration
Since your nameservers are already on Bunny.net:
1. In Bunny.net DNS manager, ensure you have:
   - `CNAME` record for `@` pointing to your Pull Zone hostname (e.g., `pullzone-id.bunny.net`)
   - `CNAME` record for `www` pointing to the same Pull Zone hostname
   - Alternatively, use `A` records if Bunny provides specific IPs
2. Verify DNS propagation using `dig publicinformation.ie +short`

### Step 5: Configure Automatic SSL
1. In Pull Zone settings, SSL should auto-enable for custom domains
2. Navigate to **SSL** in your Pull Zone settings
3. Verify SSL certificate status (usually provisions within minutes)
4. Enable **Force HTTPS** to redirect HTTP to HTTPS

### Step 6: Create API Key and Storage Zone Password
You need two credentials:

**Bunny.net API Key** (for Pull Zone cache purging):
1. Go to [Bunny.net API Keys](https://dash.bunny.net/account/api-keys)
2. Create or verify existing key has: `pullzone.read`, `pullzone.write`
3. Copy the **API Key**

**Storage Zone Password** (for uploading files):
1. In your Storage Zone settings, go to **FTP & API Access**
2. Note or generate a **Password** (this is different from your account password)
3. Copy the **Storage Zone Password**

---

## Phase 2: Codeberg Workflow Update

### Step 7: Add Secrets to Codeberg
Add these repository secrets in Codeberg (Settings → Secrets → Actions):
- `BUNNY_API_KEY`: Your Bunny.net API key (for cache purging)
- `BUNNY_STORAGE_ZONE_NAME`: Your Storage Zone name (e.g., `publicinformation-ie`)
- `BUNNY_STORAGE_ZONE_PASSWORD`: Your Storage Zone password
- `BUNNY_PULL_ZONE_ID`: Your Pull Zone numeric ID (e.g., `123456`)

### Step 8: Update Deployment Workflow
Replace the SFTP deployment step with Bunny Edge Storage upload.

**New workflow approach:**
1. Build Astro site → `dist/` folder
2. Upload all files to Edge Storage via API (replacing existing files)
3. Purge Pull Zone cache to ensure visitors get fresh content

### Step 9: Test Manual Deployment First
Before updating the workflow, test a manual deployment:

```bash
# Build locally
cd publicinfo-prototype
npm run build

# Upload files to Edge Storage
# This uploads the entire dist folder contents to the root of your storage zone
find dist -type f -exec curl -s -X PUT \
  --url "https://storage.bunnycdn.com/{STORAGE_ZONE_NAME}/{}" \
  -H "AccessKey: {STORAGE_ZONE_PASSWORD}" \
  --upload-file {} \;

# Or upload files individually:
curl -X PUT \
  --url "https://storage.bunnycdn.com/publicinformation-ie/index.html" \
  -H "AccessKey: YOUR_STORAGE_PASSWORD" \
  --upload-file dist/index.html

# Purge Pull Zone cache (optional but recommended)
curl -X POST \
  "https://api.bunny.net/pullzone/{PULL_ZONE_ID}/purgeCache" \
  -H "AccessKey: {API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Verify the site loads at a Bunny-provided Pull Zone URL before DNS cutover.

---

## Phase 3: Workflow Implementation

Here's what the updated `.forgejo/workflows/deploy.yml` will look like:

```yaml
name: Build and Deploy to Bunny.net

on:
  push:
    branches: [main]
    paths:
      - 'publicinfo-prototype/src/**'
      - 'publicinfo-prototype/scripts/csv_to_json.py'
      - '.forgejo/workflows/deploy.yml'
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: codeberg-small

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: pip install requests

      - name: Generate JSON from CSV
        working-directory: publicinfo-prototype
        run: python scripts/csv_to_json.py

      - name: Verify JSON was generated
        working-directory: publicinfo-prototype
        run: |
          if [ ! -f src/data/public_bodies.json ]; then
            echo "ERROR: public_bodies.json was not created" >&2
            exit 1
          fi
          echo "JSON file size: $(wc -c < src/data/public_bodies.json) bytes"

      - name: Set up Node.js 22
        uses: actions/setup-node@v3
        with:
          node-version: '22'

      - name: Install Node dependencies
        working-directory: publicinfo-prototype
        run: npm ci

      - name: Build Astro site
        working-directory: publicinfo-prototype
        run: npm run build

      - name: Install curl (if not available)
        run: sudo apt-get update -qq && sudo apt-get install -y -qq curl

      - name: Upload to Bunny Edge Storage
        working-directory: publicinfo-prototype
        env:
          BUNNY_STORAGE_ZONE_NAME: ${{ secrets.BUNNY_STORAGE_ZONE_NAME }}
          BUNNY_STORAGE_ZONE_PASSWORD: ${{ secrets.BUNNY_STORAGE_ZONE_PASSWORD }}
        run: |
          # Upload all files from dist/ to storage zone root
          find dist -type f | while read -r file; do
            # Get relative path from dist/
            rel_path="${file#dist/}"
            # Skip empty paths (dist/ itself)
            if [ -n "$rel_path" ]; then
              echo "Uploading $rel_path..."
              curl -s -X PUT \
                --url "https://storage.bunnycdn.com/$BUNNY_STORAGE_ZONE_NAME/$rel_path" \
                -H "AccessKey: $BUNNY_STORAGE_ZONE_PASSWORD" \
                --upload-file "$file" \
                --fail
            fi
          done

      - name: Purge Pull Zone Cache
        working-directory: publicinfo-prototype
        env:
          BUNNY_API_KEY: ${{ secrets.BUNNY_API_KEY }}
          BUNNY_PULL_ZONE_ID: ${{ secrets.BUNNY_PULL_ZONE_ID }}
        run: |
          curl -X POST \
            "https://api.bunny.net/pullzone/$BUNNY_PULL_ZONE_ID/purgeCache" \
            -H "AccessKey: $BUNNY_API_KEY" \
            -H "Content-Type: application/json" \
            -d '{}'
```

---

## Phase 4: Cutover & Validation

### Step 10: Initial Deployment Test
1. Push a test change to a branch
2. Run the workflow manually via `workflow_dispatch`
3. Verify deployment succeeds in Bunny.net dashboard
4. Check files appear in your Storage Zone
5. Verify the site loads via your Pull Zone's temporary Bunny URL

### Step 11: DNS Cutover
1. Once Bunny deployment is verified, update DNS to point to your Pull Zone
2. Wait for DNS propagation (usually 5-60 minutes)
3. Verify `publicinformation.ie` loads with valid SSL

### Step 12: Final Validation
- [ ] Site loads on `https://publicinformation.ie`
- [ ] SSL certificate is valid (check in browser)
- [ ] All pages render correctly
- [ ] CSV files are downloadable
- [ ] JSON data loads correctly
- [ ] Any RSS feeds work (if implemented)
- [ ] Cache is being purged and fresh content appears after deployment

### Step 13: Monitor First Few Deployments
- Check Bunny.net dashboard for Storage Zone and Pull Zone status
- Verify Codeberg workflow logs for any errors
- Monitor site accessibility after pushes
- Check Pull Zone analytics for traffic and cache hit rates

---

## Rollback Plan

If issues arise:
1. **Quick rollback**: Change DNS back to Hetzner IP
2. **Workflow rollback**: Revert `.forgejo/workflows/deploy.yml` to the Hetzner version
3. **No data loss**: Original files remain on Hetzner until you manually decommission

---

## Timeline Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Bunny.net setup | 20-30 min | Manual configuration (Storage Zone + Pull Zone) |
| Workflow update | 15 min | File changes and testing |
| Testing | 30-60 min | Includes DNS propagation |
| **Total** | **1-2 hours** | Mostly waiting on DNS |

---

## Additional Notes

### Storage Zone vs. Edge Sites
- **Edge Sites** (discontinued): Was a simplified hosting product that combined storage and CDN
- **Edge Storage + Pull Zone**: The current, more flexible approach giving you direct control over both storage and CDN settings

### Performance Tips
- Enable **Perma-Cache** in your Pull Zone for static assets that never change
- Consider enabling **Bunny Optimizer** for automatic image optimization
- Use **Cache Tags** if you need granular cache control for different content types

### Cost Considerations
- Edge Storage: $0.01/GB/month for storage
- Pull Zone: $0.01/GB for bandwidth (first $1 is free each month)
- Most small static sites cost less than $1/month
