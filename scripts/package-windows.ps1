$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo

& (Join-Path $PSScriptRoot 'build-sidecar.ps1')
$icon = Join-Path $repo 'apps\desktop\src-tauri\icons\icon.ico'
if (-not (Test-Path -LiteralPath $icon)) {
    pnpm --dir apps/desktop exec tauri icon ../../resources/roundlens-icon.svg --output src-tauri/icons
}
pnpm tauri build --bundles nsis
