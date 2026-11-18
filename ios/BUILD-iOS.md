# iOS app — build brief (for Claude Code on Alex's Mac)

## Goal

Wrap the existing web app (`hosting/cloudflare/public/`) as an iOS app for Alex's own iPhone, and add what a web page can't do:
1. **Stops that trigger with the phone locked or in a pocket** (geofences, i.e. iOS region monitoring).
2. **Proper background audio** with lock-screen and AirPods controls.

Everything else (tours, player, transcript, feedback notes) stays in the web layer, unchanged.

## Architecture

- **Capacitor** (current major version) with the iOS platform. Use Swift Package Manager rather than CocoaPods if the Capacitor version supports it.
- **Live web layer:** set `server.url` in `capacitor.config` to `https://walk-nyc.pages.dev`, so every Cloudflare ship updates the app without an Xcode rebuild. Also bundle a copy of `public/` as `webDir` for reference. Fine for a personal, sideloaded app (App Store review would object). If offline launch turns out to matter, revisit: bundle the web layer and fetch `tours.json` and audio remotely.
- **Feature detection** in `index.html`: `const NATIVE = window.Capacitor?.isNativePlatform?.()`. Web behavior stays the default; native paths only light up when `NATIVE`.

## Native work

### 1. Geofencing plugin (write a small custom Capacitor plugin in Swift)

Community plugins exist, but a ~150-line custom plugin around `CLLocationManager` is easier to reason about. API:

```
Geofence.requestPermission()                       -> {status}  // ask When-In-Use first, then Always
Geofence.setStops([{id:"fidi:3", lat, lng, radius}]) // replaces monitored regions
Geofence.clear()
event "enter" {id, timestamp}
```

- iOS monitors at most **20 regions** per app, so only the active tour's stops (≤ 9) are registered when walking mode starts.
- Region monitoring needs radius ≥ ~100 m to be reliable and may fire late in Midtown canyons. Register at max(100, settings radius) and let JS confirm with a precise GPS fix when it can.
- In JS, `startWalk()` calls `setStops` for the tour. On `enter`, run the same logic as `checkTriggers()` (play now or queue).

### 2. Arrival while the app is suspended

When a region fires, iOS wakes the app in the background for about 10 seconds; the WebView's JS may not get to run.
- **v1 (start here):** the plugin posts a **local notification** ("Arrived: 4. Wall Street — tap to play"). If the app is still running, audio is already playing, or JS is alive, it plays or queues the stop directly, as the web app does.
- **v2 (if v1 is annoying):** the plugin plays the stop's mp3 natively with `AVPlayer` (URL from `audio/manifest.json`, which the JS hands to the plugin in `setStops`), then tells the WebView on resume so the transcript catches up. Test whether iOS allows starting playback from a region wake with an active `.playback` audio session; that's the risk to check first.

### 3. Background audio

- Xcode → Signing & Capabilities → Background Modes: **Audio, AirPlay, and Picture in Picture**. (Originally also **Location updates**; removed for TestFlight on 2026-11-18 because `CLMonitor` doesn't need it. See NOTES.md.)
- At launch, set `AVAudioSession` category `.playback` (mode `.spokenAudio`), so `<audio>` in the WKWebView keeps playing when locked.
- The web app already sets `navigator.mediaSession` metadata and handlers; confirm the lock screen shows them inside WKWebView. If not, mirror them via `MPNowPlayingInfoCenter` and `MPRemoteCommandCenter` in a tiny plugin.

### 4. Info.plist

- `NSLocationWhenInUseUsageDescription`, `NSLocationAlwaysAndWhenInUseUsageDescription`: "Walk NYC starts each stop's narration when you arrive, even with your phone in your pocket."
- `UIBackgroundModes`: `audio` (`location` removed 2026-11-18, see NOTES.md).
- If the service worker should run inside WKWebView, add `WKAppBoundDomains` with `walk-nyc.pages.dev`. Optional: the app works without the service worker.

## Install on Alex's iPhone

- Xcode → Settings → Accounts → add Alex's Apple ID. In the target's Signing, pick that "Personal Team" and a unique bundle id (e.g. `com.apolitakis.walknyc`).
- Turn on Developer Mode on the iPhone (Settings → Privacy & Security), plug it in, select it as the run destination, and Run.
- With a free account the install lasts **7 days** (rebuild and Run again to renew). The paid Apple Developer Program ($99/yr) makes it last a year and enables TestFlight.

## Test plan (outdoors)

1. Start walk mode on a tour near home (FiDi: Bowling Green and Stone Street are ~300 m apart), lock the phone, and walk between stops. The arrival notification or audio should fire within ~50–150 m.
2. Lock-screen controls pause, resume and skip the recorded audio.
3. Write a note mid-walk; confirm it shows up via `GET /api/feedback`.
4. Ship a trivial web change; reopen the app and confirm it picked it up without a rebuild.

Keep a short log of what worked in `ios/NOTES.md` for future threads.
