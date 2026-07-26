$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$service = Join-Path $repo 'services\analyzer'
$source = Join-Path $service 'dist\roundlens-analyzer'
$destinationParent = Join-Path $repo 'apps\desktop\src-tauri\binaries'
$destination = Join-Path $destinationParent 'roundlens-analyzer'
Set-Location -LiteralPath $repo

uv sync --all-groups
uv run pyinstaller --clean --noconfirm --distpath (Join-Path $service 'dist') --workpath (Join-Path $service 'build') (Join-Path $service 'roundlens_analyzer.spec')

$resolvedParent = [System.IO.Path]::GetFullPath($destinationParent)
$resolvedDestination = [System.IO.Path]::GetFullPath($destination)
if (-not $resolvedDestination.StartsWith($resolvedParent + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to replace a Sidecar directory outside src-tauri\binaries.'
}
New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
if (Test-Path -LiteralPath $destination) {
    Remove-Item -Recurse -Force -LiteralPath $destination
}
Copy-Item -Recurse -LiteralPath $source -Destination $destination
& (Join-Path $destination 'roundlens-analyzer.exe') --health-check --data-dir (Join-Path $repo '.packaging-smoke-data')
