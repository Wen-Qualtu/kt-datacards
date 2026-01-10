# Feature 00: Poetry + Task Setup

## Status
🔴 Not Started

## Overview
Set up Poetry for dependency management and virtual environment, plus Task (Taskfile) for easy script execution. This enables consistent development across multiple machines.

## Why This Feature
- **Portability**: Same environment on any machine
- **Reproducibility**: Lock file ensures consistent dependencies
- **Convenience**: Simple commands to run complex scripts
- **Isolation**: No conflicts with system Python packages

## Current State
- `requirements.txt` for dependencies
- Manual Python execution
- No virtual environment management
- No task runner

## Proposed Setup

### Poetry Configuration
```toml
# pyproject.toml
[tool.poetry]
name = "kt-datacards"
version = "0.1.0"
description = "Kill Team datacard extraction and processing for Tabletop Simulator"
authors = ["Your Name <your.email@example.com>"]
readme = "README.md"
packages = [{include = "src", from = "script"}]

[tool.poetry.dependencies]
python = "^3.9"
pillow = "^10.0.0"
pypdf2 = "^3.0.0"
pytesseract = "^0.3.10"
pyyaml = "^6.0"
pandas = "^2.0.0"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
black = "^23.7.0"
flake8 = "^6.1.0"
mypy = "^1.5.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

### Taskfile Configuration
```yaml
# Taskfile.yml
version: '3'

vars:
  PYTHON: poetry run python

tasks:
  # Setup tasks
  install:
    desc: Install dependencies using Poetry
    cmds:
      - poetry install

  update:
    desc: Update dependencies
    cmds:
      - poetry update

  # Main processing tasks
  process:
    desc: Process raw PDFs (identify and organize)
    cmds:
      - "{{.PYTHON}} script/process_raw_pdfs.py {{.CLI_ARGS}}"

  extract:
    desc: Extract individual cards as images
    cmds:
      - "{{.PYTHON}} script/extract_pages.py {{.CLI_ARGS}}"

  urls:
    desc: Generate URL CSV
    cmds:
      - "{{.PYTHON}} script/generate_urls.py {{.CLI_ARGS}}"

  backside:
    desc: Add default backsides to cards
    cmds:
      - "{{.PYTHON}} script/add_default_backsides.py {{.CLI_ARGS}}"

  all:
    desc: Run complete pipeline (process → extract → backside → urls)
    cmds:
      - task: process
      - task: extract
      - task: backside
      - task: urls

  # Specific team processing
  process-team:
    desc: Process specific team(s) - Usage: task process-team -- --teams kasrkin,blooded
    cmds:
      - "{{.PYTHON}} script/main.py {{.CLI_ARGS}}"

  # Development tasks
  test:
    desc: Run tests
    cmds:
      - poetry run pytest tests/

  lint:
    desc: Run linting
    cmds:
      - poetry run flake8 script/
      - poetry run mypy script/

  format:
    desc: Format code with black
    cmds:
      - poetry run black script/

  clean:
    desc: Clean generated files and cache
    cmds:
      - rm -rf **/__pycache__
      - rm -rf .pytest_cache
      - rm -rf .mypy_cache

  # Utility tasks
  shell:
    desc: Start Poetry shell
    cmds:
      - poetry shell

  info:
    desc: Show environment info
    cmds:
      - poetry env info
      - poetry show --tree

  # Documentation
  help:
    desc: Show available tasks
    cmds:
      - task --list
```

## Implementation Steps

### Phase 1: Install Tools
- [ ] Install Poetry: `curl -sSL https://install.python-poetry.org | python3 -`
- [ ] Install Task: 
  - Windows: `choco install go-task` or download from releases
  - Mac: `brew install go-task`
  - Linux: Download from GitHub releases
- [ ] Verify installations:
  ```bash
  poetry --version
  task --version
  ```

### Phase 2: Initialize Poetry
- [ ] Navigate to project root
- [ ] Run `poetry init` (interactive) or create `pyproject.toml` manually
- [ ] Migrate dependencies from `requirements.txt`:
  ```bash
  poetry add pillow pypdf2 pytesseract pyyaml pandas
  ```
- [ ] Add dev dependencies:
  ```bash
  poetry add --group dev pytest black flake8 mypy
  ```
- [ ] Generate lock file: `poetry lock`

### Phase 3: Create Taskfile
- [ ] Create `Taskfile.yml` in project root
- [ ] Define common tasks
- [ ] Test task execution:
  ```bash
  task install
  task process
  task extract
  ```

### Phase 4: Update Documentation
- [ ] Update README.md with setup instructions
- [ ] Document available tasks
- [ ] Add quick start guide

### Phase 5: Git Configuration
- [ ] Add to `.gitignore`:
  ```
  # Poetry
  poetry.lock
  .venv/
  
  # Python
  __pycache__/
  *.py[cod]
  *$py.class
  *.so
  .Python
  
  # Testing
  .pytest_cache/
  .coverage
  htmlcov/
  
  # Type checking
  .mypy_cache/
  ```
- [ ] Decide whether to commit `poetry.lock` (recommended: yes)

### Phase 6: Testing
- [ ] Test on current machine
- [ ] Test on second machine (fresh clone)
- [ ] Verify reproducibility

## Usage Examples

### Initial Setup (New Machine)
```bash
# Clone repository
git clone <repo-url>
cd kt-datacards

# Install dependencies
task install

# Run pipeline
task all
```

### Daily Workflow
```bash
# Process new PDFs
task process

# Extract specific team
task process-team -- --teams kasrkin

# Run full pipeline
task all

# Format code before commit
task format
```

### Development
```bash
# Start poetry shell (for interactive work)
poetry shell

# Run tests
task test

# Lint code
task lint

# Check environment
task info
```

## File Structure After Implementation

```
kt-datacards/
├── pyproject.toml          # Poetry configuration
├── poetry.lock             # Locked dependencies
├── Taskfile.yml            # Task definitions
├── .gitignore              # Updated with Python/Poetry ignores
├── README.md               # Updated with setup instructions
├── requirements.txt        # Keep for reference, deprecated
├── script/
│   ├── src/                # Source code (after refactoring)
│   └── ...
└── ...
```

## Updated README.md Section

Add this to README.md:

```markdown
## Setup

### Prerequisites
- Python 3.9 or higher
- [Poetry](https://python-poetry.org/docs/#installation)
- [Task](https://taskfile.dev/installation/)

### Installation

1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd kt-datacards
   ```

2. Install dependencies:
   ```bash
   task install
   ```

3. Verify setup:
   ```bash
   task info
   ```

## Usage

### Process All Teams
```bash
task all
```

### Process Specific Steps
```bash
task process      # Identify and organize PDFs
task extract      # Extract card images
task backside     # Add default backsides
task urls         # Generate URL CSV
```

### Process Specific Teams
```bash
task process-team -- --teams kasrkin,blooded
```

### Development
```bash
task test         # Run tests
task lint         # Check code quality
task format       # Format code
task help         # Show all available tasks
```

## Available Tasks

Run `task --list` to see all available tasks.
```

## Benefits

### For Multi-Machine Workflow
- **Consistent Environment**: Same Python version and dependencies everywhere
- **Quick Setup**: `task install` on any new machine
- **No System Pollution**: Virtual environment keeps system Python clean
- **Lock File**: Ensures exact same versions across machines

### For Development
- **Simple Commands**: `task process` instead of `poetry run python script/process_raw_pdfs.py`
- **Documented Workflow**: Taskfile serves as documentation
- **Easy to Remember**: Clear task names
- **Composable**: Chain tasks together

### For Collaboration
- **Reproducible**: Anyone can get same environment
- **Self-Documenting**: `task --list` shows what's available
- **Version Controlled**: Dependencies tracked in git

## Migration from requirements.txt

### Automatic Migration
```bash
# Install from requirements.txt
cat requirements.txt | xargs poetry add

# Or one by one
poetry add pillow
poetry add pypdf2
poetry add pytesseract
poetry add pyyaml
poetry add pandas
```

### Keep requirements.txt?
- **Option A**: Delete it (Poetry is source of truth)
- **Option B**: Keep for reference (deprecated)
- **Option C**: Generate from Poetry for compatibility:
  ```bash
  poetry export -f requirements.txt --output requirements.txt
  ```
- **Recommendation**: Option B or C

## Common Tasks Reference

| Task | Command | Description |
|------|---------|-------------|
| Install | `task install` | Install all dependencies |
| Process All | `task all` | Run complete pipeline |
| Process PDFs | `task process` | Identify and organize PDFs |
| Extract Cards | `task extract` | Extract card images |
| Generate URLs | `task urls` | Update CSV with URLs |
| Process Team | `task process-team -- --teams kasrkin` | Process specific team(s) |
| Run Tests | `task test` | Run test suite |
| Format Code | `task format` | Auto-format with Black |
| Lint Code | `task lint` | Check code quality |
| Show Info | `task info` | Display environment info |
| Show Help | `task --list` | List all tasks |

## Advanced Task Features

### Passing Arguments
```bash
# Pass arguments to script
task process-team -- --teams kasrkin --verbose

# With multiple flags
task process-team -- --teams kasrkin,blooded --dry-run --force
```

### Task Dependencies
```yaml
# In Taskfile.yml
deploy:
  deps: [test, lint]  # Run test and lint before deploy
  cmds:
    - echo "Deploying..."
```

### Environment Variables
```yaml
# In Taskfile.yml
vars:
  OUTPUT_DIR: output
  INPUT_DIR: input

tasks:
  process:
    cmds:
      - echo "Processing from {{.INPUT_DIR}} to {{.OUTPUT_DIR}}"
```

## Troubleshooting

### Poetry Not Found
```bash
# Add to PATH (Linux/Mac)
export PATH="$HOME/.local/bin:$PATH"

# Windows: Add to System PATH
# %APPDATA%\Python\Scripts
```

### Wrong Python Version
```bash
# Specify Python version
poetry env use 3.9

# Or use specific Python
poetry env use /path/to/python3.9
```

### Virtual Environment Issues
```bash
# Remove and recreate
poetry env remove python
poetry install
```

### Task Not Found
```bash
# Verify installation
task --version

# Run with full path
./task install  # If task is in project directory
```

## Estimated Effort
- **Complexity**: Low
- **Time**: 1-2 hours
- **Risk**: Very Low
- **Priority**: **Should be done first** (foundation for all other work)

## Dependencies
- None (this is a foundation feature)
- Should be completed before other features
- Enables Feature 02 (Code Refactoring)
- Enables Feature 05 (Parameterized Execution)

## Testing Checklist
- [ ] Install Poetry on machine 1
- [ ] Install Task on machine 1
- [ ] Run `task install`
- [ ] Run `task all`
- [ ] Verify outputs are correct
- [ ] Clone to machine 2
- [ ] Run `task install` on machine 2
- [ ] Run `task all` on machine 2
- [ ] Verify same behavior
- [ ] Test individual tasks
- [ ] Test task with arguments
- [ ] Verify virtual environment isolation
