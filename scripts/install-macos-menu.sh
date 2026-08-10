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

mkdir -p "$INSTALL_DIR" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/EtherGPT"
swiftc "$ROOT_DIR/macos/EtherGPTMenu.swift" -framework Cocoa -o "$TARGET"

/usr/libexec/PlistBuddy -c "Clear dict" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :Label string org.ethergpt.menu" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :ProgramArguments array" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :ProgramArguments:0 string $TARGET" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :RunAtLoad bool true" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :KeepAlive bool true" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :StandardOutPath string $HOME/Library/Logs/EtherGPT/menu.log" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :StandardErrorPath string $HOME/Library/Logs/EtherGPT/menu-error.log" "$PLIST"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/org.ethergpt.menu"
echo "Installed EtherGPT menu-bar app: $TARGET"
