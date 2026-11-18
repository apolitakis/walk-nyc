#!/usr/bin/env bash
# Publish rendered narration (out/audio/) to the `audio` branch of apolitakis/walk-nyc.
# A GitHub Action on that branch then uploads it to the R2 bucket walk-nyc-audio,
# using the repo secrets CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID.
# This machine never holds the Cloudflare token; it only needs push access to the repo
# (on the A40: the deploy key behind the `github-walknyc` SSH host alias).
#
# The branch is a single orphan commit, force-pushed each time, so old renders don't pile up in history.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
src="${1:-$here/out/audio}"
remote="${WALKNYC_REMOTE:-git@github-walknyc:apolitakis/walk-nyc.git}"

[ -f "$src/manifest.json" ] || { echo "No manifest.json in $src" >&2; exit 1; }
# Every file the manifest names must exist, or the app would point at missing audio.
python3 -I - "$src" <<'PY'
import json, os, sys
src = sys.argv[1]
m = json.load(open(os.path.join(src, "manifest.json")))
tracks = m["tracks"]
items = tracks.values() if isinstance(tracks, dict) else tracks
missing = [t["file"] for t in items if not os.path.isfile(os.path.join(src, os.path.basename(t["file"])))]
if missing:
    sys.exit(f"manifest names {len(missing)} missing files, e.g. {missing[:3]}")
print(f"manifest OK: {len(list(items))} tracks, voice {m.get('voice')}")
PY

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
mkdir -p "$work/audio" "$work/.github/workflows"
cp "$src"/*.mp3 "$src/manifest.json" "$work/audio/"
cat > "$work/.github/workflows/upload-audio.yml" <<'YML'
name: Upload narration to R2
on:
  push:
    branches: [audio]
  workflow_dispatch:
concurrency:
  group: r2-audio
  cancel-in-progress: false
jobs:
  upload:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
      CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm install -g wrangler@4
      - name: Upload mp3s, then manifest.json last
        working-directory: audio
        run: |
          set -euo pipefail
          # mp3s first (8 at a time); if any fails, xargs fails and the manifest is not uploaded.
          ls *.mp3 | xargs -P 8 -I{} wrangler r2 object put "walk-nyc-audio/audio/{}" --file "{}" --content-type audio/mpeg --remote
          wrangler r2 object put walk-nyc-audio/audio/manifest.json --file manifest.json --content-type application/json --remote
          echo "Uploaded $(ls *.mp3 | wc -l) tracks + manifest.json"
      - name: Check the live site
        working-directory: audio
        run: |
          set -euo pipefail
          curl -fsS https://walk-nyc.pages.dev/audio/manifest.json | python3 -c "import json,sys; m=json.load(sys.stdin); print('live manifest:', len(m['tracks']), 'tracks,', m.get('voice'))"
          f=$(ls *.mp3 | head -1)
          curl -fsS -o /dev/null -w "$f: %{http_code}\n" "https://walk-nyc.pages.dev/audio/$f"
YML

cd "$work"
git init -q -b audio
git add -A
git -c user.name="$(git -C "$here" config user.name || echo A40)" -c user.email="$(git -C "$here" config user.email || echo a40@localhost)" \
  commit -q -m "Narration audio: $(ls audio/*.mp3 | wc -l) tracks ($(date -u +%F))"
git push --force "$remote" audio:audio
echo "Pushed. Watch the upload at https://github.com/apolitakis/walk-nyc/actions"
