# Copy all team box files from output_v3 to TTS Saved Objects folder
# Purpose: Deploy generated TTS objects to Tabletop Simulator for testing

param(
    [string]$OutputDir = "c:\git\kt-datacards\output_v3",
    [string]$TTSDir = "C:\Users\Jesse\Documents\My Games\Tabletop Simulator\Saves\Saved Objects\tts_objects_v3"
)

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Copy Team Boxes to TTS" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# Create TTS directory if it doesn't exist
if (-not (Test-Path $TTSDir)) {
    Write-Host "Creating TTS directory: $TTSDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $TTSDir -Force | Out-Null
}

# Get all teams
$teams = Get-ChildItem $OutputDir -Directory | Where-Object { $_.Name -ne "object-urls.json" }
$copiedCount = 0
$errorCount = 0

foreach ($team in $teams) {
    $teamName = $team.Name
    $ttsObjectsDir = Join-Path $team.FullName "tts_objects"
    
    if (-not (Test-Path $ttsObjectsDir)) {
        Write-Host "  [SKIP] No tts_objects folder: $teamName" -ForegroundColor DarkGray
        continue
    }
    
    # Find Box.json file (any filename ending with " Box.json")
    $boxFile = Get-ChildItem $ttsObjectsDir -Filter "* Box.json" -File | Select-Object -First 1
    
    if (-not $boxFile) {
        Write-Host "  [WARN] No Box.json found: $teamName" -ForegroundColor Yellow
        $errorCount++
        continue
    }
    
    # Copy to TTS directory
    $destFile = Join-Path $TTSDir $boxFile.Name
    try {
        Copy-Item $boxFile.FullName -Destination $destFile -Force
        Write-Host "  [OK] $($boxFile.Name)" -ForegroundColor Green
        $copiedCount++
    }
    catch {
        Write-Host "  [ERROR] Failed to copy $($boxFile.Name): $_" -ForegroundColor Red
        $errorCount++
    }
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Summary" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "Copied: $copiedCount" -ForegroundColor Green
if ($errorCount -gt 0) {
    Write-Host "Errors: $errorCount" -ForegroundColor Red
}
Write-Host "Target: $TTSDir" -ForegroundColor Cyan
