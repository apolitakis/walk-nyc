#!/usr/bin/env bash
# Upload rendered narration in out/audio/ to the R2 bucket walk-nyc-audio under the audio/ prefix.
# Needs CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID in the environment, plus Node (npx).
# Uploads the mp3s first and manifest.json last, so the live app never sees entries for files that aren't there yet.
set -euo pipefail
cd "$(dirname "$0")/out/audio"
BUCKET=walk-nyc-audio
n=0; total=$(ls *.mp3 | wc -l)
for f in *.mp3; do
  n=$((n+1)); echo "[$n/$total] $f"
  npx --yes wrangler@4 r2 object put "$BUCKET/audio/$f" --file "$f" --content-type audio/mpeg --remote >/dev/null
done
npx --yes wrangler@4 r2 object put "$BUCKET/audio/manifest.json" --file manifest.json --content-type application/json --remote >/dev/null
echo "Uploaded $total tracks + manifest.json"
