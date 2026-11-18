#!/usr/bin/env bash
# Publish rendered narration (out/audio/*.mp3 + manifest.json) as a GitHub release on apolitakis/walk-nyc.
# Publishing the release triggers .github/workflows/upload-audio.yml, which uploads it to R2.
# Needs only the GitHub CLI logged in (gh auth login) with write access to the repo; no Cloudflare credentials.
set -euo pipefail
cd "$(dirname "$0")"
REPO=apolitakis/walk-nyc
[ -f out/audio/manifest.json ] || { echo "out/audio/manifest.json missing; render first" >&2; exit 1; }
TAG="audio-$(date -u +%Y%m%d-%H%M)"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
n=$(ls out/audio/*.mp3 | wc -l)
tar -czf "$TMP/audio.tar.gz" -C out/audio .
echo "Packed $n mp3s + manifest.json ($(du -h "$TMP/audio.tar.gz" | cut -f1))"
gh release create "$TAG" "$TMP/audio.tar.gz" --repo "$REPO" --title "Narration $TAG" \
  --notes "Recorded narration: $n tracks. Uploaded to R2 by the 'Upload audio to R2' workflow." --latest=false
echo "Published $TAG. Watch the upload: gh run list --repo $REPO --workflow upload-audio.yml"
