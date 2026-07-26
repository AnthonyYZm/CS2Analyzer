$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo

uv run ruff check .
uv run mypy services/analyzer/src
uv run pytest
pnpm lint
pnpm typecheck
pnpm test
pnpm build
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
