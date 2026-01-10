# Feature 05: Parameterized Execution

## Status
🔴 Not Started

## Overview
Add command-line parameters and configuration options to run the processing pipeline selectively instead of always processing everything.

## Current Behavior
- Scripts always process all teams
- No way to run specific steps
- Slow when only updating one team
- No dry-run or preview mode

## Proposed Features

### 1. Team Filtering
Process only specific teams:
```bash
# Single team
python main.py --teams angels-of-death

# Multiple teams
python main.py --teams angels-of-death,blooded,kasrkin

# All teams (default)
python main.py
```

### 2. Pipeline Steps
Run specific pipeline steps:
```bash
# Only process raw PDFs
python main.py --steps process

# Only extract images
python main.py --steps extract

# Only generate URLs
python main.py --steps urls

# Multiple steps
python main.py --steps process,extract,urls

# All steps (default)
python main.py
```

### 3. Combined Filtering
```bash
# Process and extract for specific teams
python main.py --teams kasrkin,blooded --steps process,extract
```

### 4. Dry Run Mode
Preview what would be done without making changes:
```bash
python main.py --dry-run
python main.py --teams kasrkin --dry-run
```

### 5. Verbosity Control
```bash
# Quiet mode (errors only)
python main.py --quiet

# Normal mode (default)
python main.py

# Verbose mode (detailed logging)
python main.py --verbose

# Debug mode (everything)
python main.py --debug
```

### 6. Force Processing
Re-process even if no changes detected:
```bash
python main.py --force
python main.py --teams kasrkin --force
```

### 7. Output Format Options
```bash
# Skip URL CSV generation
python main.py --no-csv

# Generate additional formats
python main.py --output json,csv,markdown
```

## Command Line Interface

### Full CLI Specification
```bash
usage: main.py [-h] [--teams TEAMS] [--steps STEPS] [--dry-run] [--force]
               [--verbose] [--quiet] [--debug] [--no-csv] [--output FORMAT]
               [--config CONFIG]

Process Kill Team datacards from PDFs to images.

optional arguments:
  -h, --help            show this help message and exit
  
  # Team filtering
  --teams TEAMS         Comma-separated list of teams to process (default: all)
  
  # Pipeline control
  --steps STEPS         Pipeline steps to run: process,extract,urls (default: all)
  --force               Force processing even if no changes detected
  --dry-run             Show what would be done without making changes
  
  # Logging
  --verbose, -v         Verbose output
  --quiet, -q           Quiet mode (errors only)
  --debug               Debug mode (maximum logging)
  
  # Output
  --no-csv              Skip CSV URL generation
  --output FORMAT       Additional output formats (json,csv,markdown)
  
  # Configuration
  --config CONFIG       Path to config file (default: script/config/settings.py)

examples:
  # Process only kasrkin team
  python main.py --teams kasrkin
  
  # Dry run for multiple teams
  python main.py --teams kasrkin,blooded --dry-run
  
  # Only extract images (skip processing)
  python main.py --steps extract
  
  # Force reprocess with verbose logging
  python main.py --teams angels-of-death --force --verbose
```

## Implementation Steps

### Phase 1: Argument Parsing
- [ ] Install `argparse` (built-in) or `click` library
- [ ] Define CLI arguments
- [ ] Add help text
- [ ] Add validation

### Phase 2: Pipeline Refactoring
- [ ] Make pipeline steps independent
- [ ] Add step enumeration
- [ ] Allow selective execution
- [ ] Add dry-run support

### Phase 3: Team Filtering
- [ ] Validate team names against team-mapping
- [ ] Filter input files by team
- [ ] Skip processing for non-selected teams

### Phase 4: Logging System
- [ ] Set up logging levels
- [ ] Configure output format
- [ ] Add progress indicators
- [ ] Add summary reports

### Phase 5: Force Mode
- [ ] Add flag to bypass hash checking
- [ ] Force re-extraction of images
- [ ] Update metadata accordingly

### Phase 6: Configuration File
- [ ] Support external config file
- [ ] Override default settings
- [ ] Validate configuration

### Phase 7: Testing
- [ ] Test each parameter combination
- [ ] Test error cases
- [ ] Verify dry-run mode
- [ ] Test with various team selections

## Code Structure

### main.py
```python
import argparse
from src.pipeline import DatacardPipeline
from src.utils.logger import setup_logger

def parse_args():
    parser = argparse.ArgumentParser(
        description="Process Kill Team datacards"
    )
    
    parser.add_argument(
        "--teams",
        type=str,
        help="Comma-separated list of teams"
    )
    
    parser.add_argument(
        "--steps",
        type=str,
        default="process,extract,urls",
        help="Pipeline steps to run"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force processing"
    )
    
    # ... more arguments
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Setup logging
    logger = setup_logger(
        verbose=args.verbose,
        quiet=args.quiet,
        debug=args.debug
    )
    
    # Parse teams
    teams = None
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    
    # Parse steps
    steps = [s.strip() for s in args.steps.split(',')]
    
    # Create pipeline
    pipeline = DatacardPipeline(
        dry_run=args.dry_run,
        force=args.force
    )
    
    # Run pipeline
    pipeline.run(teams=teams, steps=steps)
    
    logger.info("Processing complete!")

if __name__ == "__main__":
    main()
```

### Pipeline Integration
```python
class DatacardPipeline:
    def __init__(self, dry_run=False, force=False):
        self.dry_run = dry_run
        self.force = force
    
    def run(self, teams=None, steps=None):
        if steps is None:
            steps = ['process', 'extract', 'urls']
        
        if 'process' in steps:
            self.process_raw_pdfs(teams=teams)
        
        if 'extract' in steps:
            self.extract_images(teams=teams)
        
        if 'urls' in steps:
            self.generate_urls(teams=teams)
    
    def process_raw_pdfs(self, teams=None):
        if self.dry_run:
            logger.info("[DRY RUN] Would process raw PDFs")
            return
        
        # Actual processing
        ...
```

## Configuration File Support

### config.yaml Example
```yaml
# Processing options
default_dpi: 300
image_format: PNG
parallel_processing: true
max_workers: 4

# Paths (override defaults)
input_dir: "input"
output_dir: "output"
processed_dir: "processed"
archive_dir: "archive"

# URL generation
github_base_url: "https://raw.githubusercontent.com/..."
generate_csv: true

# Logging
log_level: INFO
log_file: "logs/processing.log"

# Teams (default teams to process if none specified)
default_teams:
  - angels-of-death
  - kasrkin
  - blooded
```

### Using Config File
```bash
python main.py --config my_config.yaml
```

## Progress Reporting

### Console Output Example
```
=== Kill Team Datacard Processing ===

Selected teams: kasrkin, blooded
Pipeline steps: process, extract, urls

[1/3] Processing raw PDFs...
  ✓ kasrkin: identified 5 PDFs
  ✓ blooded: identified 3 PDFs
  
[2/3] Extracting images...
  kasrkin: ████████████████████ 25/25 cards
  blooded: ████████████████████ 18/18 cards
  
[3/3] Generating URLs...
  ✓ CSV updated: 43 total URLs

=== Summary ===
Processed teams: 2
Total cards: 43
Time elapsed: 2m 15s
```

## Dry Run Output Example
```
=== DRY RUN MODE ===

Would process:
  - kasrkin (5 PDFs found)
    → datacards: 8 pages
    → equipment: 12 pages
    → faction-rules: 2 pages
  
  - blooded (3 PDFs found)
    → datacards: 6 pages
    → equipment: 10 pages

Would extract: 38 card images
Would update: datacards-urls.csv

No changes made (dry run mode)
```

## Benefits
- **Speed**: Process only what's needed
- **Flexibility**: Run specific pipeline steps
- **Safety**: Dry-run mode prevents accidents
- **Debugging**: Verbose modes help troubleshooting
- **Automation**: Easy to script and schedule

## Use Cases

### 1. Quick Update
New PDF for one team:
```bash
python main.py --teams kasrkin
```

### 2. Regenerate URLs Only
After moving files:
```bash
python main.py --steps urls
```

### 3. Test New Processing
Before committing:
```bash
python main.py --teams kasrkin --dry-run --verbose
```

### 4. Force Rebuild
After code changes:
```bash
python main.py --force
```

### 5. Batch Processing Script
```bash
#!/bin/bash
teams=("kasrkin" "blooded" "angels-of-death")

for team in "${teams[@]}"; do
    python main.py --teams "$team" --verbose
done
```

## Estimated Effort
- **Complexity**: Medium
- **Time**: 4-6 hours
- **Risk**: Low

## Dependencies
- Requires Feature 02 (Code Refactoring) to be complete
- Works best with Feature 03 (Enhanced Metadata)

## Testing Checklist
- [ ] Test with single team
- [ ] Test with multiple teams
- [ ] Test with invalid team names
- [ ] Test each pipeline step individually
- [ ] Test combinations of steps
- [ ] Test dry-run mode
- [ ] Test force mode
- [ ] Test all logging levels
- [ ] Test with config file
- [ ] Test with no arguments (default behavior)
