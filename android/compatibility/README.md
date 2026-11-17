# Chaquopy compatibility probe

This throwaway-but-reproducible Android app verifies whether the current
CrazyGame Python dependency set can run inside an APK.

Current result: **blocked**. Chaquopy has no compatible Android wheel for
`pydantic-core==2.50.4`, which is required by the current Pydantic 2 backend.
See `docs/mobile-phase0-report.md`. Keep this project for future revalidation,
but use the approved Kotlin-local fallback for Phase 4.

The probe uses:

- Chaquopy 17.2.0
- Python 3.11
- Android Gradle plugin 8.13.2
- `minSdk 26`
- `arm64-v8a` and `x86_64`

It imports FastAPI, Pydantic 2, cryptography, SQLAlchemy, APScheduler, httpx,
python-multipart and uvicorn; creates an in-memory SQLite database; performs a
cryptography round-trip; starts a local uvicorn server on `127.0.0.1:8765`; and
loads `/api/health` in Android WebView.

Build:

```bash
export JAVA_HOME="$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home"
export ANDROID_HOME="/opt/homebrew/share/android-commandlinetools"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
cd android/compatibility
./gradlew :app:assembleDebug
```

The result determines whether Phase 4 continues with embedded Python or uses
the approved Kotlin-local fallback.
