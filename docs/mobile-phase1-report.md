# Phase 1 Construction Report

> Date: 2026-11-16
>
> Status: stopped after Phase 1 for review. Phase 2 has not started.

## Completed

- Added the versioned Android and mobile UI plan at `docs/mobile-android-plan.md`.
- Added Vitest, jsdom and React Testing Library without upgrading the existing Vite or React versions.
- Added `motion@14.14.0` with lazy `domMax` feature loading.
- Centralized compatibility color, radius, shadow and touch tokens on the Aurora token layer.
- Added shared motion tokens for page, press, sheet and stagger behavior.
- Added `BottomSheet`, `Toast`, `Skeleton`, `SkeletonCard`, `Pressable`, `PageTransition`, `StaggerList` and `AnimatedNumber`.
- Added focus management, Escape handling, Android back-event handling, drag dismissal, body scroll locking and visual-viewport sizing to BottomSheet.
- Replaced route-level key reconstruction with direction-aware route transitions.
- Added session-based scroll restoration for history navigation.
- Changed the mobile bar to Overview / Watchlist / Groups / Holdings / Alerts with an animated selection indicator.
- Kept AI and Settings in the top utility controls.
- Added higher contrast/touch sizing and removed duplicate mobile navigation CSS.
- Added missing root `make test` and `make build` targets.
- Added a reproducible Chaquopy compatibility probe under `android/compatibility`.

## New dependencies

- Runtime: `motion@14.14.0`
- Development: `vitest@2.1.9`, `jsdom@25.0.1`, `@testing-library/react@16.3.3`, `@testing-library/user-event@14.6.1`, `@testing-library/jest-dom@6.6.3`

## Verification

- `make test`: 19 backend tests and 15 frontend tests passed.
- `pnpm check:i18n`: passed.
- `pnpm build`: passed.
- Responsive overflow scan: 30 page/width combinations passed at 320, 375, 390, 414 and 768px.
- Desktop navigation verified at 1440px.
- Production build: main JS 713.25 kB (228.04 kB gzip), lazy Motion features 106.96 kB (36.84 kB gzip), lazy AI page 19.21 kB (5.60 kB gzip).
- Motion remains lazily loaded; the main bundle remains above the pre-existing Vite warning threshold.

Screenshots:

- `docs/images/mobile-phase1/overview-320.png`
- `docs/images/mobile-phase1/watchlist-390.png`
- `docs/images/mobile-phase1/groups-768.png`
- `docs/images/mobile-phase1/overview-1440.png`

## Remaining issues

- Existing business pages still use the desktop-oriented modal and long-form layout; these belong to Phase 2 and Phase 3.
- Page data request caching is intentionally deferred to Phase 2. Phase 1 only removes the unnecessary outer route key and adds scroll memory.
- React Router 6 emits future-flag warnings in development. They are pre-existing and do not fail the build.
- Chaquopy runtime compatibility is recorded in `docs/mobile-phase0-report.md`.

## Next phase

Phase 2 should start with Overview only:

1. Compress the empty-state hero and remove duplicate calls to action.
2. Put real holdings/group state and the chart in the first usable mobile viewport.
3. Apply the new transition and stagger primitives locally.
4. Add page-level request caching so returning to Overview preserves data and avoids an immediate duplicate fetch.
