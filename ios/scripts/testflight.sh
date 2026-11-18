#!/usr/bin/env bash
# Archive the iOS app and upload it to App Store Connect, where it shows up in TestFlight.
#
#   cd ios
#   TEAM_ID=ABCDE12345 ./scripts/testflight.sh
#
# TEAM_ID is the 10-character Team ID from developer.apple.com/account (Membership details).
# Needs: Xcode signed in to that Apple ID (Xcode > Settings > Accounts), and the app record
# already created in App Store Connect with the same bundle id.
#
# The build number is the current UTC date and time (e.g. 20261118.1530), so every upload is
# unique and higher than the last. Override with BUILD_NUMBER=... if needed.
# The version shown to testers is MARKETING_VERSION in the Xcode project (1.0.0).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${TEAM_ID:?Set TEAM_ID to your Apple Developer Team ID, e.g. TEAM_ID=ABCDE12345 ./scripts/testflight.sh}"
BUILD="${BUILD_NUMBER:-$(date -u +%Y%m%d.%H%M)}"
OUT="native/App/build/testflight"

echo "==> Syncing web layer and Capacitor config"
[ -d node_modules ] || npm install
npm run sync

rm -rf "$OUT"
mkdir -p "$OUT"
sed "s/TEAM_ID/$TEAM_ID/" ExportOptions.plist > "$OUT/ExportOptions.plist"

echo "==> Archiving build $BUILD"
xcodebuild \
  -project native/App/App.xcodeproj \
  -scheme App \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$OUT/App.xcarchive" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  CURRENT_PROJECT_VERSION="$BUILD" \
  archive

echo "==> Uploading to App Store Connect"
xcodebuild -exportArchive \
  -archivePath "$OUT/App.xcarchive" \
  -exportOptionsPlist "$OUT/ExportOptions.plist" \
  -exportPath "$OUT/export" \
  -allowProvisioningUpdates

echo "==> Uploaded build $BUILD. It appears in App Store Connect > TestFlight after processing (usually 5 to 30 minutes)."
