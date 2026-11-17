# CrazyGame Android Development

## Runtime architecture

- Android uses a Kotlin `WebView` to host the same React source used by PC Web.
- The frontend talks to `window.CrazyGameNative`, a local JavaScript bridge.
- Business state is stored in an encrypted SQLite value protected by an
  Android Keystore AES-GCM key.
- Market, news, AI, Feishu, and Aliyun SMS requests go directly from the device
  to their configured public providers. There is no CrazyGame cloud service.
- WorkManager checks local alerts approximately every 15 minutes and checks the
  daily review schedule. The in-app UI polls visible data about every 30 seconds.
- Local notification delivery is enabled by default. Feishu and Aliyun SMS remain
  available as remote channels.

## Local commands

```bash
export JAVA_HOME="$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home"
export ANDROID_HOME="/opt/homebrew/share/android-commandlinetools"
export ANDROID_SDK_ROOT="$ANDROID_HOME"

make android-debug
make android-release
```

The APK is built from `frontend/dist`, which Gradle regenerates with
`pnpm build:android` before packaging.

Install and launch on a connected device or emulator:

```bash
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n ai.panvv.crazygame/.MainActivity
```

## Signing

The local signing configuration is read from `.secrets/keystore.properties` and
`.secrets/crazygame-release.jks`. The entire `.secrets/` directory is ignored.

The generated release certificate uses a 4096-bit RSA key and is valid for 10,000
days. Back up the keystore and passwords outside the repository; losing them
prevents same-signature upgrades of an installed APK.

For GitHub Actions, add:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

Pushing a `mobile-v*` tag builds a signed `CrazyGame_1.apk` release asset. Normal
branches and pull requests build and upload the debug APK.

## Data transfer

The Android data package contains selectable watchlist, group, holding, alert,
LLM, and news sections. Package contents are encrypted with a user-supplied
password using PBKDF2-HMAC-SHA256 and AES-256-GCM. The same package format is
accepted by the PC backend.

Android and PC databases are not synchronized. Import is an explicit manual
merge or replacement operation through a file.
