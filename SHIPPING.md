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
2. Publish from the A40:
   ```
   cd ~/lab/walk-nyc-voices && bash publish_audio.sh
   ```
   This checks that every file in `manifest.json` exists, then force-pushes `out/audio/` as a single commit to the `audio` branch (over the `github-walknyc` deploy key). Pushing to that branch runs the **Upload narration to R2** Action, which uploads each mp3 to the R2 bucket `walk-nyc-audio` under `audio/`, then `manifest.json` last, so the app never sees a manifest pointing at missing files. The Action then checks the live manifest and one mp3. Watch it at https://github.com/apolitakis/walk-nyc/actions.
   - The Cloudflare token lives only in the repo secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, scoped to R2 object writes on `walk-nyc-audio`. The A40 doesn't need it.
   - The Action's definition is in `voices/publish_audio.sh`, which writes it into the `audio` branch. Edit it there, not on the branch.
   - To re-run an upload without re-pushing: Actions -> Upload narration to R2 -> Run workflow, on branch `audio`.
   - Fallback, with the token in the environment: `bash upload_r2.sh` uploads directly.
3. No redeploy needed: the Pages Function reads R2 directly. The app picks up the new manifest on its next launch.

## Reading feedback notes

```
curl -s -H "x-feedback-key: $WALKNYC_FEEDBACK_KEY" https://walk-nyc.pages.dev/api/feedback
```
Returns `{"notes":[...]}`, newest first. Each note has the text, tour, stop index and title, the sentence playing when it was written, lat/lng/accuracy, app version, and time. Typical workflow: read the notes, group them (facts, pronunciation, GPS placement, UX), propose fixes to Alex, make the agreed changes, ship when told.
