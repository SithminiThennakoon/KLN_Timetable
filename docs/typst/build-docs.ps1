param(
  [string]$TypstExe = "typst"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $root "out"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

& $TypstExe compile (Join-Path $root "user-manual.typ") (Join-Path $outDir "User Manual.pdf")
& $TypstExe compile (Join-Path $root "technical-documentation.typ") (Join-Path $outDir "Technical Documentation.pdf")
& $TypstExe compile (Join-Path $root "abc-handover.typ") (Join-Path $outDir "ABC Handover.pdf")

Write-Host "Built documentation PDFs in $outDir"
