# RoundLens repository guide

## Goal and stack

Build a privacy-first Windows 10/11 CS2 personal match analyzer with a Tauri 2/Rust desktop shell, React/TypeScript UI, and Python 3.11 JSONL sidecar. Awpy is the primary parser; demoparser2 only supplements fields. SQLite stores relational/history data and Parquet stores dense tick/trajectory data.

## Layout

- `apps/desktop`: React/Vite UI and `src-tauri` shell.
- `services/analyzer`: Python sidecar, domain logic, parsers, persistence and tests.
- `packages/contracts`: single-source JSON Schemas and generated language types.
- `resources`: benchmarks, prompts and licensed/locally-derived map metadata only.
- `docs`: architecture, protocol, data, security, metrics and ADRs.
- `scripts`: development, test and Windows packaging entry points.
- `tests`: cross-language integration, packaging and local-only fixture instructions.

## Commands

- Dev: `pnpm dev`, `uv run roundlens-analyzer --data-dir <path>`
- Test: `pnpm test`, `uv run pytest`, `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml`
- Check: `pnpm lint`, `pnpm typecheck`, `uv run ruff check .`, `uv run mypy services/analyzer/src`
- Build: `pnpm build`, `uv build`, `cargo build --manifest-path apps/desktop/src-tauri/Cargo.toml`
- Package: `scripts/build-sidecar.ps1`, `scripts/package-windows.ps1`

## Non-negotiable data and security rules

1. Demo, raw tick and trajectory data never leave the device. Never commit or upload a user Demo.
2. Only a user-triggered AI report may use the network, and only with a redacted, bounded aggregate payload.
3. API keys live only in Windows Credential Manager (an in-memory store is allowed in tests). Never write them to SQLite, JSON, `.env`, logs, crash reports, IPC debug output, localStorage, or frontend persistence.
4. React must never bypass Rust to read a key or call a provider. Rust returns configured/not configured, never the secret.
5. Python stdout is reserved exclusively for one-line JSONL protocol messages. Logs go to stderr or a log file.
6. Missing data is `unavailable`/`partial`, never numeric zero. A metric without required capabilities is omitted from issues and AI input.
7. Every new or changed metric needs tests for the calculation, capability gating and missing-data behavior.
8. A rule impact score is not an exact win probability. Estimated reaction, visibility or movement values must remain labeled `estimated`.
9. Do not silently swallow parser or advanced-metric failures; persist a stable error/status and log technical detail without secrets.
10. Deleting analysis data must never delete the source `.dem`. Validate all paths and hashes before relinking or destructive work.
11. Do not bundle Valve/CS2/FACEIT logos, radar images, maps or other assets unless redistribution rights are verified.

## Engineering rules

- Keep parser-specific column names inside `parsers`/`normalization`; metric code consumes internal models.
- JSON Schemas are the source of truth for IPC and reports. Keep protocol version `1` and report schema version `1.0.0` synchronized.
- Default tests are hermetic: mock parser/provider, synthetic events, no paid API and no undocumented Demo fixture.
- Update `docs/IMPLEMENTATION_PLAN.md` after milestone verification. Do not mark a feature complete until its test/build command actually passed.
