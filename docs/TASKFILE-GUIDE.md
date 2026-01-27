# Task Runner Guide

This project uses [Task](https://taskfile.dev/) for easy pipeline management and deployment.

## Installation

### Windows (PowerShell)
```powershell
# Using Chocolatey
choco install go-task

# Or using Scoop
scoop install task

# Or download from https://github.com/go-task/task/releases
```

### Quick Start
```bash
task --list          # Show all available tasks
task help            # Same as above
task all             # Run full pipeline
task test-imports    # Verify setup
```

## Main Pipeline Tasks

```bash
# Run full pipeline (all steps)
task all

# Run individual steps
task process      # Process PDFs and identify teams
task extract      # Extract card images
task backsides    # Add backsides to cards
task urls         # Generate URLs JSON
task tokens       # Token integration

# Process specific teams
task team TEAMS="kasrkin"
task team TEAMS="kasrkin blooded"

# Quick test on small team
task test-team
task test-team TEST_TEAM=ratlings
```

## Branch Deployment

The pipeline supports dynamic branch URLs for testing different environments:

```bash
# Default: main branch
task all
task all BRANCH=main

# Deploy with acc branch URLs
task deploy-acc

# Deploy with dev branch URLs  
task deploy-dev

# Custom branch
task urls BRANCH=feature/my-branch
```

### How Branch URLs Work

When you run tasks with a branch parameter:
- All GitHub raw URLs will use that branch
- Generated TTS objects will reference the correct branch
- datacards-urls.json will have branch-specific URLs

**Examples:**
- Main: `https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/...`
- Acc: `https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/acc/output_v2/...`
- Dev: `https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/dev/output_v2/...`

### Testing Workflow

1. **Create your test branch in git:**
   ```bash
   git checkout -b acc
   git push origin acc
   ```

2. **Generate files with branch URLs:**
   ```bash
   task deploy-acc
   # Or
   task all BRANCH=acc
   ```

3. **Commit and push generated files:**
   ```bash
   git add output_v2/ tts_objects/
   git commit -m "Generated with acc branch URLs"
   git push origin acc
   ```

4. **Test in TTS using the acc branch URLs**

5. **When ready, merge to main:**
   ```bash
   git checkout main
   git merge acc
   task deploy-main  # Regenerate with main URLs
   git push origin main
   ```

## Common Workflows

### Full Release
```bash
task all                     # Generate all files
# Review output
git add .
git commit -m "Release: updated datacards"
git push
```

### Test New Team on Separate Branch
```bash
# Create test branch
git checkout -b test/new-team
git push origin test/new-team

# Process just that team with test branch URLs
task team TEAMS="new-team-name" BRANCH=test/new-team

# Commit and push
git add .
git commit -m "Add new team"
git push origin test/new-team

# Test in TTS, then merge when ready
```

### Quick Team Update
```bash
# Extract images for specific teams only
task team-extract TEAMS="kasrkin blooded"

# Generate URLs
task urls

# Commit
git add output_v2/
git commit -m "Update kasrkin and blooded images"
```

## Environment Variables

You can also set the branch via environment variable:

```powershell
# PowerShell
$env:KT_BRANCH = "acc"
task all

# Or inline
$env:KT_BRANCH="dev"; task urls
```

```bash
# Linux/Mac
export KT_BRANCH=acc
task all

# Or inline
KT_BRANCH=dev task urls
```

## Troubleshooting

### Check Environment
```bash
task check-env    # Verify Python and dependencies
```

### Test Imports
```bash
task test-imports # Test all module imports
```

### Verbose Logging
Add `-v` flag through the TEAMS variable or edit Taskfile:
```bash
# Edit task to add -v flag temporarily
task test-team
```

### Clean Up
```bash
task clean-logs   # Remove log files
```

## Development Tasks

```bash
task format       # Format code with black (requires black)
task lint         # Lint code with pylint (requires pylint)
task gen-tts      # Generate TTS objects only
task gen-metadata # Generate metadata only
```

## Examples Summary

```bash
# Quick test
task test-team

# Full pipeline, main branch
task all

# Full pipeline, acc branch for testing
task deploy-acc

# Process one team with custom branch
task team TEAMS="kasrkin" BRANCH=feature/update

# Extract images for multiple teams
task team-extract TEAMS="kasrkin blooded ratlings"

# Just regenerate URLs with dev branch
task urls BRANCH=dev

# Show all tasks
task --list
```

## Task File Structure

See [Taskfile.yml](Taskfile.yml) for full task definitions and customization options.
