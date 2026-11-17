# Phase 0 Analysis and Compatibility Report

> Date: 2026-11-16
>
> Result: the current Chaquopy path is blocked. Use the approved Kotlin-local
> fallback for Android business services when Phase 4 begins.

## Scope

Phase 0 verified whether the current FastAPI/Pydantic backend can be embedded in
an Android APK with Chaquopy. It did not modify business pages and did not start
Phase 2.

The probe is retained at `android/compatibility/` so it can be rerun if upstream
Android wheels become available.

## Toolchain

- Host: macOS 15.5 on arm64
- JDK: OpenJDK 21.0.13
- Gradle: 8.13 through the checked-in wrapper
- Android SDK command-line tools: 22.0
- Android platform: API 36
- Build tools: 36.0.0; Gradle also installed its required 35.0.0
- Platform tools: 37.0.1
- Emulator: 37.2.13
- System image: Android 36 default arm64-v8a
- AVD: `crazygame-api36`

The local SDK root is `/opt/homebrew/share/android-commandlinetools`. It is
recorded in the ignored `android/compatibility/local.properties`.

## Probe configuration

- Chaquopy 17.2.0
- Python 3.11.14
- Android Gradle plugin 8.13.2
- `compileSdk 36`, `targetSdk 36`, `minSdk 26`
- `arm64-v8a` and `x86_64`
- FastAPI 0.162.2
- Pydantic 2.14.3
- SQLAlchemy 2.1.8
- APScheduler 3.11.3
- httpx 0.28.1
- uvicorn 0.54.0
- python-multipart 0.0.33

## Results

### cryptography

The current desktop version `cryptography 50.0.2` has no Chaquopy Android wheel.
The compatible Android wheel currently published by Chaquopy is `42.0.8`, which
is allowed by the existing project requirement `cryptography>=42.0.0`.

### Pydantic 2

After pinning cryptography to the available Android wheel, the build advanced
to Pydantic resolution and failed:

```text
Could not find a version that satisfies the requirement pydantic-core==2.50.4
(from pydantic) (from versions: 0.0.1)
```

Pydantic 2.14.3 depends on a compiled `pydantic-core` release that has no
Chaquopy Android wheel. This blocks FastAPI because the current application uses
Pydantic 2 schemas throughout the backend.

Because dependency installation failed, the probe could not proceed to:

- APK installation
- Python startup in the emulator
- SQLite creation on Android
- HTTPS request verification
- uvicorn loopback startup
- WebView request to `/api/health`

These must not be reported as validated.

## Decision

The confirmed fallback is now active for Phase 4:

- Keep Kotlin WebView as the Android container.
- Keep the same React UI.
- Implement Android data, quote aggregation and local alert services in Kotlin.
- Keep Android and PC data independent and local.
- Do not require a PC connection or cloud service.
- Do not force a Pydantic 1 downgrade or maintain custom Android wheels unless
  the product direction changes explicitly.

This Phase 0 result does not change the Phase 1 UI infrastructure delivered in
`docs/mobile-phase1-report.md`.
