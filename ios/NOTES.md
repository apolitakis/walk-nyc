# iOS app: build log

What was built from `BUILD-iOS.md`, what works, and what's still untested. Newest first.

## 2026-11-18: TestFlight prep (not yet built on the Mac)

Made in the cloud, so none of this has been through Xcode yet. The first `scripts/testflight.sh` run is the check.
- App icon from `icon.svg` (square, no alpha) and a black launch screen with the walker logo; WebView background `#0d0d0e` (`capacitor.config.json`, needs `npm run sync`).
- iPhone only (`TARGETED_DEVICE_FAMILY = 1`), `MARKETING_VERSION` 1.0.0, `VERSIONING_SYSTEM = apple-generic`.
- Info.plist: removed the `location` background mode (CLMonitor doesn't need it; App Review flags it when an app doesn't track continuously). If arrivals don't fire with the phone locked on the outdoor test, putting it back is the first thing to try. Added `ITSAppUsesNonExemptEncryption` = NO and the Travel category; clearer location strings.
- `App/PrivacyInfo.xcprivacy` (added to the target's Resources).
- `scripts/testflight.sh` + `ExportOptions.plist`: archive and upload with `TEAM_ID=... ./scripts/testflight.sh`.
- `hosting/cloudflare/public/privacy.html` for the TestFlight privacy policy URL (live after the next ship).
- Steps for Alex: `TESTFLIGHT.md`.

## 2026-11-17: first build (Capacitor wrapper)

Built on Alex's Mac: Xcode 27.2, iOS 27.2 Simulator runtime, Node 26.13.1 LTS (installed to `~/.local/node`, symlinked into `~/.local/bin`; there was no Node or Homebrew on the Mac before).

### Layout

```
ios/
  package.json, capacitor.config.json   Capacitor 8.6 project (iOS only)
  www/                                  copy of hosting/cloudflare/public (gitignored; `npm run sync-web`)
  native/App/App.xcodeproj              Xcode project; Swift Package Manager, no CocoaPods
  native/App/App/GeofencePlugin.swift   custom Geofence plugin
  native/App/App/MainViewController.swift   registers the plugin (capacitorDidLoad)
  native/App/App/AppDelegate.swift      AVAudioSession .playback / .spokenAudio at launch
```

- `server.url` is `https://walk-nyc.pages.dev`, so the app always shows whatever was last shipped to Cloudflare. **The native wiring in `index.html` only reaches the app after the next "ship".** Until then the app runs the 0.3.1 web layer as a plain web view, without geofences.
- Bundle id `com.apolitakis.walknyc`, display name "Walk NYC", deployment target iOS 17.
- Info.plist: both location usage strings from the brief, `UIBackgroundModes` = audio + location, and `UIRequiredDeviceCapabilities` changed from the template's `armv7` to `arm64`. `WKAppBoundDomains` is not set, so the service worker probably won't run inside the app (the brief says that's fine).

### Commands

```bash
cd ios
npm install                  # first time only
npm run sync                 # copy public/ to www/ and run `cap sync ios`
npm run open                 # open the project in Xcode
```

Simulator build from the command line:

```bash
cd ios/native/App
xcodebuild -project App.xcodeproj -scheme App -destination 'platform=iOS Simulator,name=iPhone 18 Pro' build
```

### Geofence plugin

- JS API as in the brief: `requestPermission()` → `{status, notifications}`, `setStops({stops})`, `clear()`, and an `enter` event `{id, timestamp, tapped}`. Stops may also carry `title`, which is used for the notification text.
- Registers each stop at max(100 m, settings radius), and at most 20 stops.
- **Uses `CLMonitor` (iOS 17+), not `CLLocationManager.startMonitoring(for:)`.** The old API failed every region with `kCLErrorDomain error 5` on the iOS 27.2 Simulator. CLMonitor accepted the stops but marked them `unmonitored [conditionUnsupported]`, so **the Simulator can't test geofences at all**. The real test has to be the outdoor walk on the phone.
- Each event logs a `Geofence:` line with its state and iOS's reasons (iOS 18+), for example `fidi:3 -> unmonitored [accuracyLimited]`. Read them in Xcode's console or Console.app while the phone is plugged in.
- v1 arrival: if the app isn't in the foreground, it posts a local notification ("Arrived: 4. Wall Street", "Tap to play"). The `enter` event always goes to JS too. Tapping the notification re-sends `enter` with `tapped: true`, which plays that stop.
- Permission flow: asks When-In-Use first, then Always. If iOS doesn't show the Always prompt, the call resolves after 4 s with the status it has. The JS shows a toast when the status isn't "always".

### index.html (web layer)

- `NATIVE = window.Capacitor?.isNativePlatform?.()`. In a normal browser it's false and nothing new runs. The script parses (`node --check`); I haven't opened it in a browser.
- `startWalk()` → `Geofence.requestPermission()` + `setStops()` for the tour; `stopWalk()` → `clear()`.
- The tail of `checkTriggers()` became `arrive(t, i)`, shared by GPS and geofence arrivals (play now, or queue if something is playing).
- On `enter`: if a GPS fix from the last 15 s has accuracy ≤ 50 m, the geofence is ignored and `checkTriggers()` decides, because 100 m regions fire early. Otherwise it arrives right away. Events that come before `tours.json` loads (cold launch from a notification) are held and replayed.
- In the app, the walking-mode banner says "You can lock your phone" instead of "Keep this page open".

### Checked in the Simulator (iPhone 18 Pro, iOS 27.2)

- ✅ Builds (Debug, Simulator) with no warnings in app code; installs and launches; loads the live site.
- ✅ With a local copy of the new `index.html` (temporary localhost `server.url`): `NATIVE` true, plugin found, `requestPermission` → `always`, `setStops` registered 8 FiDi stops.
- ❌ Arrivals can't be tested in the Simulator (`conditionUnsupported`, see above).
- Not checked: lock-screen Now Playing controls inside WKWebView, background audio with the screen locked, the notification tap path. These need the phone.

### Next

- Alex: sign and install on the iPhone (steps in the PR), then run the outdoor test plan in `BUILD-iOS.md`.
- Ship the `index.html` change to Cloudflare (only when Alex says "ship") so the app gets the native wiring. Bump `APP_VERSION` and CHANGELOG then.
- If lock-screen controls don't show the track, add `MPNowPlayingInfoCenter` / `MPRemoteCommandCenter` (brief §3).
