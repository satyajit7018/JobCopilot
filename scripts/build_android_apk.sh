#!/usr/bin/env bash
# ==============================================================================
# JobCopilot — Automated Android APK & TWA Builder
# Generates a standalone Android Application (.apk / .aab) from JobCopilot PWA
# ==============================================================================

set -e

APP_NAME="JobCopilot"
PACKAGE_ID="com.jobcopilot.app"
HOST_URL="${1:-https://jobcopilot.app}"

echo "======================================================="
echo "⚡ Building Android Application for $APP_NAME"
echo "📦 Package: $PACKAGE_ID"
echo "🌐 Host URL: $HOST_URL"
echo "======================================================="

# Check Node.js and npm
if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx is required to run Bubblewrap CLI."
    echo "Please install Node.js (v18+) from https://nodejs.org"
    exit 1
fi

# Check Java / JDK
if ! command -v javac &> /dev/null && [ -z "$JAVA_HOME" ]; then
    echo "⚠️  Warning: JDK 17+ is recommended for compiling the final APK."
    echo "You can install OpenJDK: 'brew install openjdk@17' (macOS) or 'apt install openjdk-17-jdk' (Linux)"
fi

echo ""
echo "🚀 Step 1: Initializing Bubblewrap Android TWA Project..."
npx -y @bubblewrap/cli init --manifest="$HOST_URL/manifest.json" || {
    echo "💡 Initializing local manifest wrapper..."
    npx -y @bubblewrap/cli init --manifest="./frontend/manifest.json"
}

echo ""
echo "🔨 Step 2: Building signed Android APK & AAB..."
npx -y @bubblewrap/cli build

echo ""
echo "======================================================="
echo "✨ Build Complete! Your Android App packages are ready:"
echo "📱 Debug APK: ./app-debug.apk"
echo "🚀 Release AAB: ./app-release-bundle.aab"
echo "======================================================="
echo "To install on your connected Android device:"
echo "  adb install -r app-debug.apk"
echo "======================================================="
