# Changelog

## 0.3.1 — 2026-11-17
- First deploy to Cloudflare Pages (walk-nyc.pages.dev): feedback notes stored in the walk-nyc-feedback KV namespace, R2 bucket walk-nyc-audio ready for recorded narration.

## 0.3.0 — 2026-11-17
- Feedback notes: a pencil button saves a note with the current tour, stop, sentence and location to `/api/feedback`, queued on the phone when offline.
- Recorded narration (Kokoro, voice af_heart) streamed from Cloudflare R2, with sentence-synced transcript, lock-screen controls and phone-voice fallback.
- Moved hosting to Cloudflare Pages (from Netlify Drop).

## 0.2.0 — 2026-11-17
- Voice menu hides novelty voices and labels quality tiers; GPS and map handle a blocked environment.

## 0.1.0 — 2026-11-17
- First version: 22 tours, GPS walk mode, phone text-to-speech, transcript, map.
