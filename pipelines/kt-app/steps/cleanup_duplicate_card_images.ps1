# Cleanup duplicate card image files in cards folder
# Rule: Keep datacards WITHOUT team prefix, other types WITH prefix

$output_v3 = "c:\git\kt-datacards\output_v3"
$teams = Get-ChildItem $output_v3 -Directory

$totalRemoved = 0

foreach ($team in $teams) {
    $teamName = $team.Name
    $cardsDir = Join-Path $team.FullName "cards"
    
    if (-not (Test-Path $cardsDir)) {
        continue
    }
    
    Write-Host "Processing $teamName..." -ForegroundColor Cyan
    
    # Process datacards - remove files WITH team prefix
    $datacardsDir = Join-Path $cardsDir "datacards"
    if (Test-Path $datacardsDir) {
        $prefixedFiles = Get-ChildItem $datacardsDir -Filter "$teamName-*.png"
        foreach ($file in $prefixedFiles) {
            Write-Host "  Removing: $($file.Name)" -ForegroundColor Yellow
            Remove-Item $file.FullName -Force
            $totalRemoved++
        }
    }
    
    # Process other card types - remove files WITHOUT team prefix
    $otherTypes = @("equipment", "firefight_ploys", "strategy_ploys", "faction_rules", "operatives_selection", "token_guide")
    foreach ($cardType in $otherTypes) {
        $typeDir = Join-Path $cardsDir $cardType
        if (Test-Path $typeDir) {
            # Get all PNG files that DON'T start with team name
            $unprefixedFiles = Get-ChildItem $typeDir -Filter "*.png" | Where-Object { 
                -not $_.Name.StartsWith("$teamName-")
            }
            foreach ($file in $unprefixedFiles) {
                Write-Host "  Removing: $cardType/$($file.Name)" -ForegroundColor Yellow
                Remove-Item $file.FullName -Force
                $totalRemoved++
            }
        }
    }
}

Write-Host "`nTotal card images removed: $totalRemoved" -ForegroundColor Green
