# Phase 2–4 Construction Report

> Date: 2026-11-17
>
> Status: Phase 2–4 implemented. Phase 0's Chaquopy blocker remains the reason
> Android business services use the approved Kotlin-local fallback.

## Phase 2: core mobile pages

- Added in-memory page caching so route changes preserve the last loaded data.
- Overview keeps real portfolio/group state and the chart in the first usable
  mobile viewport; empty states are compact and duplicate actions are removed.
- Watchlist uses a compact mobile card/list layout, cleaner search deck, touch
  sizing, live freshness labels and readable mini charts.
- Groups uses a horizontal group rail, summary metrics, chart and member weights
  in workflow order.
- Holdings replaces the hidden wide table with mobile holding cards, a
  horizontal currency summary and a Bottom Sheet editor.
- Alerts prioritizes monitoring state, threshold, current value, progress and
  frequency; creation/editing uses the shared Bottom Sheet.
- Every page validates empty, loading, error and long translated labels without
  horizontal page overflow.

## Phase 3: AI, settings, charts and complex forms

- AI chat and history move into a mobile Bottom Sheet while the composer remains
  sticky above the bottom navigation.
- Settings uses a 3×2 category rail for language, AI, news, daily review,
  notification channels and data migration.
- Form inputs use a unified 48px control height, visible border, focus ring,
  translucent surface and consistent placeholder contrast.
- Bottom Sheet actions remain visible while long alert forms scroll.
- Charts enable touch dragging, pinch zoom, wheel zoom and crosshair interaction.
- Data migration supports selectable modules, optional credential inclusion and
  password-encrypted import/export.

## Phase 4: Android local runtime

- Added a Kotlin Android project with application ID `ai.panvv.crazygame`.
- WebView loads the same React build from local APK assets.
- Android uses a local JavaScript bridge rather than a PC backend.
- SQLite stores encrypted application state; the AES-GCM key is held by Android
  Keystore.
- Implemented local instrument search and Tencent/Eastmoney quote fallbacks.
- Implemented local watchlist, groups, holdings, alert rules, alert hits,
  settings, AI sessions, AI reports and daily reviews.
- WorkManager schedules 15-minute alert scans and daily-review checks.
- Local notifications, Feishu webhooks and Aliyun SMS signing are implemented.
- AI chat uses the configured OpenAI-compatible endpoint with local streaming
  callbacks; image recognition uses the configured vision model.
- `.crazygame` packages are encrypted with PBKDF2-HMAC-SHA256 and AES-256-GCM.
- PC Web now also exposes transfer export/import APIs in the same data package
  shape.

## Release workflow

- Generated a dedicated 4096-bit RSA release key. The key and passwords are kept
  under ignored `.secrets/`.
- Release signing has been verified with APK Signature Scheme v2.
- `make android-debug` and `make android-release` build through the checked-in
  Gradle wrapper.
- GitHub Actions verifies backend/frontend tests, builds debug APKs on normal
  changes and publishes signed APKs on `mobile-v*` tags.
- The release artifact is `artifacts/CrazyGame_1.apk`.

## Verification evidence

- Backend: 22 tests passed.
- Frontend: 23 tests passed.
- Production frontend and Android-mode frontend builds passed.
- Android debug and signed release builds passed.
- Release APK installed and launched on the API 36 ARM64 emulator.
- Android search returned `600519 贵州茅台`; adding it produced a live Tencent
  quote and the card rendered correctly.
- Force-stopping and relaunching the app preserved encrypted local state.
- An alert rule was created through the mobile Bottom Sheet.
- WorkManager scheduled both the alert scan and daily-review tasks.
- Local notification channel and notification rendering were verified.
- Encrypted backup export and import succeeded; a wrong password was rejected.
- Responsive screenshots were generated for all seven pages at 390px and key
  pages at 768px with no horizontal page overflow.

## Known limitations

- Real AI, Feishu and Aliyun SMS calls are not end-to-end tested because no
  user-owned credentials were provided. The request paths compile and their
  failure handling is implemented, but provider acceptance still needs a user
  credential smoke test.
- WorkManager scheduling is approximate; Android may delay a nominal 15-minute
  task because of battery and vendor policies.
- The generated signing key must be backed up. Losing it prevents same-signature
  upgrades.
- The main Web bundle is 759.96 kB (241.81 kB gzip) and remains above Vite's
  500 kB warning threshold. Motion and the AI route are already lazy-loaded;
  deeper page splitting is a future optimization.
