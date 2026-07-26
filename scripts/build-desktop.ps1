$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$icons = Join-Path $repo 'apps\desktop\src-tauri\icons\icon.ico'
Set-Location -LiteralPath $repo

if (-not (Test-Path -LiteralPath $icons)) {
    pnpm --dir apps/desktop exec tauri icon ../../resources/roundlens-icon.svg --output src-tauri/icons
}
pnpm build
cargo build --release --manifest-path apps/desktop/src-tauri/Cargo.toml
