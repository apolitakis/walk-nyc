# TestFlight: getting Walk NYC to friends' iPhones

TestFlight installs the app on anyone's iPhone from an email invite or a public link, with no cable and no 7-day expiry (each build lasts 90 days). It needs the paid Apple Developer Program.

Because the app loads `https://walk-nyc.pages.dev`, **content and web fixes reach testers on the next "ship" with no new build.** A new TestFlight build is only needed when native code changes (anything under `ios/native/`, `Info.plist`, the icon, the plugin).

## What's already set up in the repo

| Thing | Value |
|---|---|
| Bundle id | `com.apolitakis.walknyc` |
| Name on the home screen | Walk NYC |
| Version shown to testers | `MARKETING_VERSION` = 1.0.0 (Xcode project) |
| Build number | set by `scripts/testflight.sh` to the UTC date and time, e.g. `20261118.1530` |
| Devices | iPhone only (iOS 17+). iPads can still run it in iPhone mode. |
| Icon | 1024 px, square, no transparency, made from `hosting/cloudflare/public/icon.svg` |
| Launch screen | black, with the walker logo |
| Encryption question | answered in Info.plist (`ITSAppUsesNonExemptEncryption` = NO; the app only uses HTTPS) |
| Privacy manifest | `App/PrivacyInfo.xcprivacy`: no tracking; precise location and note text sent with feedback notes, not linked to the user; UserDefaults reason CA92.1 |
| Background modes | Audio only. Geofences use `CLMonitor`, which wakes the app without the "Location updates" background mode, and leaving that mode on is a common App Review rejection. |
| Privacy policy | `hosting/cloudflare/public/privacy.html` → `https://walk-nyc.pages.dev/privacy.html` (live after the next ship) |
| Upload | `scripts/testflight.sh` + `ExportOptions.plist` |

## One-time setup (Alex)

1. **Join the Apple Developer Program** ($99/year) at https://developer.apple.com/programs/enroll/ with your Apple ID, as an individual. Approval is usually quick but can take up to 48 hours.
2. **Find your Team ID**: https://developer.apple.com/account → Membership details → Team ID (10 characters).
3. **Xcode → Settings → Accounts**: make sure your Apple ID is there and the new paid team (your name, not "Personal Team") shows up.
4. **Register the bundle id**: https://developer.apple.com/account/resources/identifiers → **+** → App IDs → App → Description "Walk NYC", Explicit bundle id `com.apolitakis.walknyc`. No extra capabilities are needed. (If Apple says the id isn't available, for example because the free Personal Team holds it, ask a thread to switch the app to `com.apolitakis.walknyc.app` and use that here and in step 5.)
5. **Create the app in App Store Connect**: https://appstoreconnect.apple.com/apps → **+** → New App.
   - Platform iOS, Name **Walk NYC** (App Store names are unique worldwide; if it's taken use "Walk NYC: Audio Tours". The home-screen name stays "Walk NYC".)
   - Primary language English (U.S.), Bundle ID `com.apolitakis.walknyc`, SKU `walknyc`, User Access: Full Access.
6. **Ship the web layer** so the privacy page is live (say "ship" in a thread).

## Each build (Alex, or a Remote Control thread on the Mac)

```bash
cd ~/Documents/walk-nyc && git pull
cd ios
TEAM_ID=ABCDE12345 ./scripts/testflight.sh
```

The script syncs the web layer, archives a Release build signed by your team (Xcode creates the distribution certificate and profile the first time), and uploads it. The build shows up in App Store Connect → your app → TestFlight after 5 to 30 minutes of processing. Apple emails you when it's ready.

From Xcode instead: open `native/App/App.xcodeproj`, App target → Signing & Capabilities → Team = your paid team, bump **Build** under General, pick "Any iOS Device (arm64)", then Product → Archive → Distribute App → TestFlight & App Store.

## Testing yourself first (no review)

App Store Connect → TestFlight → **Internal Testing** → **+** → group "Me" → add yourself → add the build. Install the TestFlight app on your iPhone and accept the invite. Internal testers get builds right away, without Beta App Review. This is the moment to do the outdoor geofence walk from `BUILD-iOS.md`.

## Inviting friends (one review per version)

Friends who aren't on your App Store Connect team are **external testers**, so the first build of each version goes through Beta App Review (usually under a day).

1. TestFlight → **Test Information** (left sidebar):
   - Beta App Description: *Audio walking tours of Manhattan and Brooklyn. Pick a tour, start walking mode, and each stop's story plays when you get there, even with your phone in your pocket. Tap the pencil to send a note about anything that's wrong or could be better.*
   - Feedback Email: your email.
   - Privacy Policy URL: `https://walk-nyc.pages.dev/privacy.html`
   - Beta App Review Information: your name, phone and email. Sign-in required: **off**.
   - Review notes (paste):
     > Walk NYC plays recorded walking-tour narration. Location is used to start each stop's audio on arrival, including with the phone locked (iOS region monitoring), which is why it asks for "Always" location. Reviewers outside New York can open any tour and tap a stop to play it; arrival triggers only fire in Manhattan and Brooklyn. No account or login.
2. TestFlight → **External Testing** → **+** → group "Friends" → add the build → answer "What to Test" (e.g. *Try a tour in walking mode with your phone locked; send notes with the pencil.*) → **Submit for Review**.
3. Once approved, add friends to the group by email, or turn on **Public Link** and send them the link. They install the **TestFlight** app from the App Store, then tap the invite.

Later builds of the same version usually skip the full review. Bump `MARKETING_VERSION` in the Xcode project for a new version (1.0.1, 1.1.0...).

## Good to know

- **Notes from friends land in the same feedback store** as yours (`GET /api/feedback`). Each note carries the app version and user agent but no name, so ask friends to sign notes if you want to know who wrote them.
- **TestFlight feedback**: testers can also take a screenshot and share it as TestFlight feedback; it shows up in App Store Connect → TestFlight → Feedback.
- **Builds expire after 90 days.** Upload a new one before then (the script makes that one command).
- **App Privacy** answers in App Store Connect (left sidebar) are only required for an App Store release, not TestFlight. When you get there, they match `PrivacyInfo.xcprivacy`: Precise Location and Other User Content, used for App Functionality, not linked to identity, no tracking.
