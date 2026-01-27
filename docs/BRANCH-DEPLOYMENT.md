# Branch Deployment Implementation

## Overview

The pipeline now supports **dynamic branch URLs** for GitHub raw file access. This enables testing and deployment workflows where TTS objects and URLs reference different branches (e.g., `acc`, `dev`, `feature/*`).

## What Changed

### 1. Configuration (script/config.py)
- Added `GITHUB_BRANCH` from environment variable `KT_BRANCH` (default: "main")
- Added `get_github_url(path, branch)` helper function for building URLs
- All GitHub URLs now use the configured branch

### 2. Pipeline (script/run_pipeline.py)
- Added `--branch` CLI argument (default: "main")
- Sets `KT_BRANCH` environment variable before importing modules
- Logs which branch is being used

### 3. URL Generator (script/generators/objects/urls.py)
- Uses `get_github_url()` for all URL generation
- Accepts branch parameter in constructor
- Generates branch-aware URLs for:
  - Card images (output_v2)
  - TTS objects (tts_objects)
  - Mesh files (.obj)

### 4. TTS Generators (script/generators/tts_objects.py)
- Imports `get_github_url()` and `GITHUB_BRANCH`
- All TTS JSON objects will reference correct branch URLs

### 5. Taskfile (Taskfile.yml)
- New task runner for simplified pipeline management
- Built-in branch support via `BRANCH` variable
- Pre-configured deployment tasks:
  - `task deploy-main` - Main branch URLs
  - `task deploy-acc` - Acceptance testing branch
  - `task deploy-dev` - Development branch
  - `task all BRANCH=custom` - Any custom branch

## Usage Examples

### Via Command Line

```bash
# Default (main branch)
python script/run_pipeline.py --step all

# Acceptance testing branch
python script/run_pipeline.py --step all --branch acc

# Development branch
python script/run_pipeline.py --step urls --branch dev

# Feature branch
python script/run_pipeline.py --step all --branch feature/new-team
```

### Via Task Runner (Recommended)

```bash
# Install Task first: choco install go-task

# Main branch (default)
task all

# Acceptance testing
task deploy-acc

# Development
task deploy-dev

# Custom branch
task all BRANCH=feature/update

# Process specific teams with branch
task team TEAMS="kasrkin blooded" BRANCH=acc
```

### Via Environment Variable

```powershell
# PowerShell
$env:KT_BRANCH = "acc"
python script/run_pipeline.py --step all
```

```bash
# Linux/Mac
export KT_BRANCH=acc
python script/run_pipeline.py --step all
```

## Testing Workflow

### Scenario: Test new changes on `acc` branch before merging to `main`

```bash
# 1. Create and checkout acc branch
git checkout -b acc
git push origin acc

# 2. Generate files with acc branch URLs
task deploy-acc
# This generates URLs like:
# https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/acc/output_v2/...

# 3. Commit and push generated files
git add output_v2/ tts_objects/
git commit -m "Generated with acc branch URLs"
git push origin acc

# 4. Test in Tabletop Simulator using acc branch files
# TTS objects will load images/meshes from acc branch

# 5. If tests pass, merge to main
git checkout main
git merge acc

# 6. Regenerate with main branch URLs
task deploy-main

# 7. Push to main
git add .
git commit -m "Deploy to main"
git push origin main
```

## URL Format Examples

### Main Branch (Default)
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/chaos/legionaries/datacards/card-001-front.jpg
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/tts_objects/Legionaries Cards.json
```

### Acc Branch
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/acc/output_v2/chaos/legionaries/datacards/card-001-front.jpg
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/acc/tts_objects/Legionaries Cards.json
```

### Feature Branch
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/feature/update/output_v2/chaos/legionaries/datacards/card-001-front.jpg
```

## Technical Details

### How It Works

1. **Environment Variable**: `KT_BRANCH` set via CLI arg or shell
2. **Config Import**: `config.py` reads `KT_BRANCH` at import time
3. **URL Building**: `get_github_url()` constructs URLs with configured branch
4. **Generation**: All generators use `get_github_url()` for consistency

### Branch Precedence

1. CLI argument: `--branch acc`
2. Environment variable: `KT_BRANCH=acc`
3. Taskfile variable: `BRANCH=acc`
4. Default: `main`

### Files That Use Branch URLs

- `output_v2/datacards-urls.json` - All card/mesh URLs
- `tts_objects/*.json` - TTS card box objects
- `tts_objects/display-table/*.json` - Display table grid
- Generated TTS metadata files

## Benefits

✅ **Test before merging**: Generate and test with branch-specific URLs  
✅ **Parallel workflows**: Multiple branches can coexist  
✅ **Safe deployments**: Test changes without affecting main  
✅ **Easy rollback**: Keep main stable while testing  
✅ **Feature development**: Each feature can have its own deployment  

## See Also

- [Taskfile Guide](TASKFILE-GUIDE.md) - Complete task runner documentation
- [Development Guide](DEVELOPMENT.md) - General development workflow
- [Configuration](../script/config.py) - Central configuration module
