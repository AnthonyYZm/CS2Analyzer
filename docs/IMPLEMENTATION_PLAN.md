# Implementation plan

Status values: `pending`, `in progress`, `verified`, `blocked`. A milestone is verified only after its listed commands pass locally.

| Milestone | Goal and modules | Acceptance / tests | Status | Remaining risk |
|---|---|---|---|---|
| 0 | Docs, contracts, React/Tauri/Python skeleton, JSONL health, CI/scripts | `pnpm lint/test/build`; `uv run ruff check .`; `uv run pytest`; `cargo test` | verified | All listed checks pass locally |
| 1 | Sidecar lifecycle, SQLite/WAL/migrations, data dirs, persistent jobs, logs, Parquet writer | persistence/job restart tests | verified | Runtime schema migration is intentionally small; Windows lock behavior still needs a clean VM |
| 2 | drag/select/scan, streaming hash, dedupe, profile/player, basic history | import/hash/relink UI and Python tests | verified | Steam discovery has synthetic coverage, not every field installation |
| 3 | Awpy primary + demoparser2 supplement, capability probe, normalization/core persistence | parser contract + optional local Demo regression | in progress | Imports and adapter contracts pass; no redistributable real Demo fixture is available for regression |
| 4 | opening, advantage, trade/isolation, economy/utility/objective metrics | focused Python metric tests | in progress | Implemented MVP subset; several extended objective/economy metrics remain |
| 5 | encounter, first shot, speed, conversion, exposure/repeek degradation | encounter/advanced metric tests | in progress | Repeek and exact User Command reconstruction remain unavailable |
| 6 | rule impact, merged issues, strengths, reviews, history/benchmark/trend | detector/report tests | verified | Benchmarks are explicitly provisional and versioned |
| 7 | map registry, snapshot/timeline and missing-map degradation | map capability/review tests | verified | No copyrighted radar assets are bundled; timeline is the default fallback |
| 8 | provider capability modes, redacted payload, schema validation/repair/fallback, Credential Manager | mock provider + Rust secret tests | in progress | Provider/Python and Rust tests pass; real Credential Manager still needs an installed-app smoke test |
| 9 | onboarding/import/history/create/report/detail/review/strength/trend/settings, i18n/a11y | RTL flows + UI build | in progress | Core flows pass; English translation coverage and manual 1366×768 QA are incomplete |
| 10 | PyInstaller, Tauri external binary/NSIS, clean-machine checklist | health/package smoke tests | in progress | 458 MB sidecar, JSONL smoke and Rust compilation pass; NSIS build/clean-VM install remain unverified |

The plan is updated after each verification pass. Failures are fixed before advancing; untested functions remain explicitly unverified.

## Verification record — 2026-07-22

- `uv run pytest`: 25 passed; `uv run ruff check .` and `uv run mypy services/analyzer/src` passed.
- `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed; React tests: 2 passed.
- PyInstaller one-dir sidecar built successfully. Its health check loaded Awpy 2.0.2 and demoparser2 0.41.4, and a packaged JSONL request/response smoke test passed.
- Rust stable installation was attempted repeatedly but `static.rust-lang.org` timed out/reset. Consequently Rust compilation, Tauri packaging, NSIS installation, signing, and clean-machine smoke tests are not claimed as complete.

## Verification record — 2026-07-25

- Rust stable-msvc became available; `cargo test` passes 3 tests.
- Player profile now accepts a 1–64 character in-match player ID/name or SteamID64 and resolves it uniquely per Demo.
- `uv run pytest`: 26 passed; React tests: 4 passed. Ruff, mypy, ESLint, TypeScript checking, Vite production build, and Rust tests pass.
- Windows JSONL transport now forces UTF-8 and emits ASCII-safe JSON escapes.
- Source and packaged sidecars completed real local Demo regressions, including all progress events, with no Demo upload.
- Analysis creation now exposes separate deterministic local and full AI report actions. The report center lists saved reports and supports reopening them manually.
- SQLite schema version 2 records the report kind and migrates existing databases in place. The rebuilt packaged sidecar passed a `list_analyses` JSONL smoke test against the migrated local database.
