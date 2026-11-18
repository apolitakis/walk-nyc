# Walk NYC — notes for Claude

GPS-triggered audio walking tours of Manhattan and Brooklyn for Alex's phone: 22 tours, 162 stops, ~72k words (~7.5 h recorded), plus optional "Go deeper" chapters per stop (about twice the base narration; being written in Nov 2026). Alex walks with it and leaves feedback notes in the app; threads read the notes and improve the content and code.

## Where things live

| What | Where | Updated when |
|---|---|---|
| Source of truth | this repo, `apolitakis/walk-nyc` | every change |
| Public site (and what the iOS app loads) | Cloudflare Pages project `walk-nyc` → `https://walk-nyc.pages.dev` (from `hosting/cloudflare/`) | **only when Alex says "ship"** |
| Recorded narration | Cloudflare R2 bucket `walk-nyc-audio`, served at `/audio/*` by `functions/audio/[[path]].js` | after re-rendering audio (see SHIPPING.md) |
| Feedback notes | Cloudflare KV namespace bound as `FEEDBACK`, written by `functions/api/feedback.js` | live, from the app |
| Working copy for Alex to try in chat | claude.ai artifact https://claude.ai/artifact/PxCra3Y6bzRypdE6xjtHDA (pinned) | republish after changes; it can't reach /api or /audio, so it uses phone speech and keeps notes on the phone |
| Audio rendering | Alex's A40 workstation (`alex@192.168.1.196`, `~/lab/walk-nyc-voices`, venv via uv + Python 3.12) | when narration text changes |
| Legacy | Netlify Drop site peaceful-torte-556209.netlify.app | retire once Cloudflare is live |

## Layout

- `content/NN-<tour>.txt` — narration source, one file per tour (format below). **Edit text here, never in tours.json.**
- `content/deeper/NN-<tour>.txt` — "Go deeper" chapters for that tour's stops, same file name as the tour (format below).
- `build.py` — `python3 build.py` regenerates `hosting/cloudflare/public/tours.json` and `voices/tracks.json`, checks the deeper files against the tours, and prints word counts.
- `hosting/cloudflare/public/` — the app: one `index.html` (vanilla JS, no build step), `sw.js` (offline shell; skips /audio and /api), icons, manifest.
- `hosting/cloudflare/functions/` — Pages Functions: `api/feedback.js`, `audio/[[path]].js` (R2 with HTTP Range support, which Safari needs).
- `hosting/cloudflare/wrangler.toml` — bindings `FEEDBACK` (KV) and `AUDIO` (R2). Secret `FEEDBACK_KEY` gates reading notes.
- `voices/` — audio render kit (Kokoro on the A40; macOS `say` as an alternative). Outputs `out/audio/*.mp3` + `manifest.json` with sentence start times.
- `ios/BUILD-iOS.md` — plan for the Capacitor iOS wrapper (built with Claude Code on Alex's Mac).
- `SHIPPING.md` — one-time Cloudflare setup, ship, audio upload, reading feedback.

## Narration format

```
=== TOUR
id: fidi
title: Financial District & the Battery
area: Manhattan
blurb: One line.
=== OVERVIEW
Paragraphs separated by blank lines.
=== STOP Stop Title @ 40.7036,-74.0168
Paragraphs.
```
Write for the ear: spell out abbreviations ("Street", not "St."), avoid symbols, and keep the second-person "look up at…" voice. Pronunciation fixes live in two places that must match: `SPEAK_FIX` in `index.html` and `voices/common.py`. Flag legends as legends; keep claims you aren't sure of out. Stop coordinates were hand-placed: when a note says a stop triggered late or early, fix its `@ lat,lng`.

"Go deeper" chapters (`content/deeper/NN-<tour>.txt`):
```
=== STOP Stop Title
=== DEEPER Chapter Title | history
Paragraphs.
=== DEEPER Another Chapter | look
Paragraphs.
```
- `STOP` names the stop exactly as in the tour file, without coordinates. Each `DEEPER` line is one chapter with one topic: `history`, `people`, `companies`, `architecture`, `nature`, `look` (look closer), `underfoot` (under your feet), `names`, `food`, `politics`, `culture`, `legends`. The ids live in `build.py` `LENSES` and the labels and descriptions in `index.html` `LENSES`; add a topic in both.
- Aim for about twice the stop's own narration, in three or four chapters of 250 to 350 words, each one able to stand alone. Don't repeat what the stop already says; build on it. Same voice and rules as the stops. Anything in a `legends` chapter is told as a story, with what's documented and what isn't.
- Audio: chapter n of stop i (both as shown in the app, from 1) is track key `<tour>:<i-1>:<n>`, file `<tour>-<ii>-d<n>.mp3`. Chapters are numbered by position, so inserting or reordering a chapter makes the later chapters' recordings at that stop stale.

## Rules

- Don't deploy to Cloudflare unless Alex says "ship". Bump `APP_VERSION` in index.html and add a line to CHANGELOG.md when you ship.
- After changing any stop or chapter text, its recorded audio is stale. List which tracks need re-rendering. `render_kokoro.py --all` skips existing files, so delete those mp3s and their manifest entries before rerendering.
- GPU work on the A40 goes through Alex's shared queue conventions, and the render script refuses CUDA if the `gpu-fan` service isn't active.
- App facts worth knowing: iOS web pages only get basic built-in voices (WebKit fingerprinting protection), hence recorded audio; iPhone Silent mode mutes web speech; browser GPS stops when the screen locks, hence the iOS wrapper.
