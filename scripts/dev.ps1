$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo

uv sync --all-groups
pnpm install --frozen-lockfile
pnpm tauri dev
