# Shipping, audio, and feedback

All commands run from the repo root unless noted, with `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` set (stored in the Walk NYC project's environment). The token needs Pages: Edit, Workers KV Storage: Edit, and Workers R2 Storage: Edit.

## One-time setup

```
cd hosting/cloudflare
npx wrangler pages project create walk-nyc --production-branch main
npx wrangler kv namespace create walk-nyc-feedback      # paste the printed id into wrangler.toml
npx wrangler r2 bucket create walk-nyc-audio
npx wrangler pages secret put FEEDBACK_KEY --project-name walk-nyc   # pick a long random string; store it in the project env as WALKNYC_FEEDBACK_KEY
```

## Ship (only when Alex says "ship")

```
python3 build.py
cd hosting/cloudflare && npx wrangler pages deploy public --project-name walk-nyc --branch main --commit-dirty=true
```
Then check `https://walk-nyc.pages.dev/` loads, `/audio/manifest.json` returns JSON (if audio is uploaded), and `POST /api/feedback` with `{"note":"ship test"}` returns `{"ok":true}`.

## Recorded audio

1. Render on the A40 (see `voices/README.md`): `python render_kokoro.py --all --voice af_heart`. Alex's chosen voice is **af_heart**.
2. Publish to GitHub; a GitHub Action uploads to R2. On the A40 (needs only `gh` logged in, no Cloudflare credentials):
   ```
   cd ~/lab/walk-nyc-voices && bash publish_audio.sh   # copy voices/publish_audio.sh there first if missing
   ```
   It packs `out/audio/` into `audio.tar.gz` and attaches it to a new release tagged `audio-YYYYMMDD-HHMM`. Publishing the release runs `.github/workflows/upload-audio.yml`, which uploads each mp3 to R2 under `audio/`, then `manifest.json` last (so the app never sees a manifest pointing at missing files), then checks the live site serves it. To re-run for an existing release: Actions → "Upload audio to R2" → Run workflow, with the tag.
   The workflow uses the repository secret `CLOUDFLARE_R2_TOKEN` (a token with only Workers R2 Storage: Edit, or R2 Object Read & Write on `walk-nyc-audio`) and the repository variable `CLOUDFLARE_ACCOUNT_ID`.
   Fallback with a token in the environment: `bash upload_r2.sh` does the same upload directly.
3. No redeploy needed: the Pages Function reads R2 directly. The app picks up the new manifest on its next launch.

## Reading feedback notes

```
curl -s -H "x-feedback-key: $WALKNYC_FEEDBACK_KEY" https://walk-nyc.pages.dev/api/feedback
```
Returns `{"notes":[...]}`, newest first. Each note has the text, tour, stop index and title, the sentence playing when it was written, lat/lng/accuracy, app version, and time. Typical workflow: read the notes, group them (facts, pronunciation, GPS placement, UX), propose fixes to Alex, make the agreed changes, ship when told.
