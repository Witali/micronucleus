param(
    [string]$MicroMusicRoot = $env:MICROMUSIC_ROOT,
    [string]$NodePath = 'node',
    [string]$Distribution = 'Ubuntu',
    [string]$Artifact,
    [switch]$Dense,
    [switch]$Jitter
)

$ErrorActionPreference = 'Stop'
if (-not $MicroMusicRoot) { throw 'Pass -MicroMusicRoot or set MICROMUSIC_ROOT.' }
$microMusicCheckout = (Resolve-Path -LiteralPath $MicroMusicRoot).Path
$receiverRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$nativeNode = (Get-Command $NodePath -ErrorAction Stop).Source
$linuxRoot = & wsl.exe -d $Distribution --exec wslpath -a $receiverRoot.Replace('\','/')
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the receiver checkout in WSL.' }
$linuxRoot = $linuxRoot.Trim()
$exportArguments = @('-d', $Distribution, '--cd', $linuxRoot, '--exec', 'python3',
    'tools/micromusic_usb/export_fixtures.py', '--output', 'build/micromusic/fixtures.json')
if ($Artifact) {
    $metadataPath = (Resolve-Path -LiteralPath $Artifact).Path
    $linuxArtifact = & wsl.exe -d $Distribution --exec wslpath -a $metadataPath.Replace('\','/')
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the frozen artifact in WSL.' }
    $linuxArtifact = $linuxArtifact.Trim()
    $exportArguments += @('--artifact', $linuxArtifact)
}
if ($Dense) { $exportArguments += '--dense' }
if ($Jitter) { $exportArguments += '--jitter' }

$previousCheckout = $env:MICROMUSIC_ROOT
try {
    $env:MICROMUSIC_ROOT = $microMusicCheckout
    & $nativeNode --test (Join-Path $PSScriptRoot 'adapter.test.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'The MicroMusic adapter tests failed.' }
    & wsl.exe @exportArguments
    if ($LASTEXITCODE -ne 0) { throw 'USB fixture export failed.' }
    $result = & $nativeNode (Join-Path $PSScriptRoot 'verify.mjs') (Join-Path $receiverRoot 'build/micromusic/fixtures.json')
    $resultCode = $LASTEXITCODE
    $report = Join-Path $receiverRoot 'build/micromusic/report.json'
    [IO.File]::WriteAllText($report, (($result -join [Environment]::NewLine) + [Environment]::NewLine), [Text.UTF8Encoding]::new($false))
    $result | Write-Output
    if ($resultCode -ne 0) { throw "Executor comparison failed; inspect $report" }
    Write-Output "Executor comparison passed; report $report"
} finally {
    $env:MICROMUSIC_ROOT = $previousCheckout
}
