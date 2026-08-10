#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The menu-bar app is only available on macOS." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$HOME/.local/lib/ethergpt"
TARGET="$INSTALL_DIR/EtherGPTMenu"
PLIST="$HOME/Library/LaunchAgents/org.ethergpt.menu.plist"
APP_DIR="$HOME/Applications/EtherGPT.app"
APP_EXECUTABLE="$APP_DIR/Contents/MacOS/EtherGPT"
APP_RESOURCES="$APP_DIR/Contents/Resources"
ICON_GENERATOR="$INSTALL_DIR/EtherGPTIconGenerator"

mkdir -p "$INSTALL_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/EtherGPT" "$APP_DIR/Contents/MacOS" "$APP_RESOURCES"
swiftc "$ROOT_DIR/macos/EtherGPTMenu.swift" -framework Cocoa -o "$TARGET"
swiftc "$ROOT_DIR/macos/EtherGPTLauncher.swift" -framework Cocoa -o "$APP_EXECUTABLE"
swiftc "$ROOT_DIR/macos/EtherGPTIconGenerator.swift" -framework Cocoa -o "$ICON_GENERATOR"

ICON_TEMP="$(mktemp -d)"
trap 'rm -rf "$ICON_TEMP"' EXIT
"$ICON_GENERATOR" "$ICON_TEMP/EtherGPT.iconset"
iconutil -c icns "$ICON_TEMP/EtherGPT.iconset" -o "$APP_RESOURCES/EtherGPT.icns"

cp "$ROOT_DIR/macos/Info.plist" "$APP_DIR/Contents/Info.plist"

/usr/libexec/PlistBuddy -c "Clear dict" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :Label string org.ethergpt.menu" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :ProgramArguments array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :ProgramArguments:0 string $TARGET" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :RunAtLoad bool true" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :KeepAlive bool false" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :StandardOutPath string $HOME/Library/Logs/EtherGPT/menu.log" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :StandardErrorPath string $HOME/Library/Logs/EtherGPT/menu-error.log" "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl enable "gui/$(id -u)/org.ethergpt.menu"
launchctl bootstrap "gui/$(id -u)" "$PLIST"

touch "$APP_DIR"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$APP_DIR" >/dev/null 2>&1 || true
fi
echo "Installed EtherGPT menu-bar app: $TARGET"
echo "Installed EtherGPT launcher app: $APP_DIR"
