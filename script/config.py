"""Central configuration for paths and settings.

This module provides a single source of truth for all paths, URLs, and
configuration constants used throughout the Kill Team datacards pipeline.

Usage:
    from config import PROJECT_ROOT, OUTPUT_V2_DIR, GITHUB_OUTPUT_V2_URL
    from config import get_github_url  # For branch-aware URLs
"""
import os
import subprocess
from pathlib import Path


def _get_current_git_branch() -> str:
    """
    Get the current git branch name.
    
    Returns:
        Branch name, or 'main' if not in a git repo or command fails
    """
    try:
        # Get the project root directory from where this config file is located
        project_root = Path(__file__).parent.parent
        
        result = subprocess.run(
            ['git', '-C', str(project_root), 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch and branch != 'HEAD':
                return branch
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return 'main'

# ============================================================================
# PROJECT STRUCTURE
# ============================================================================

# Project root - calculated once from this file's location
# config.py is in script/, so parent is project root
PROJECT_ROOT = Path(__file__).parent.parent

# Directory paths (all derived from PROJECT_ROOT)
CONFIG_DIR = PROJECT_ROOT / 'config'
INPUT_DIR = PROJECT_ROOT / 'input'
PROCESSED_DIR = PROJECT_ROOT / 'processed'
ARCHIVE_DIR = PROJECT_ROOT / 'archive'
OUTPUT_DIR = PROJECT_ROOT / 'output'  # Legacy V1 structure (immutable)
OUTPUT_V2_DIR = PROJECT_ROOT / 'output_v2'  # Current V2 structure
TTS_OBJECTS_DIR = PROJECT_ROOT / 'tts_objects'
METADATA_DIR = PROJECT_ROOT / 'metadata'
DEV_DIR = PROJECT_ROOT / 'dev'
DOCS_DIR = PROJECT_ROOT / 'docs'

# ============================================================================
# BRANCH CONFIGURATION
# ============================================================================

# Branch for GitHub URLs - Priority:
# 1. Environment variable KT_BRANCH (if set via CLI or manually)
# 2. Current git branch (auto-detected)
# 3. Default: 'main'
_env_branch = os.getenv('KT_BRANCH')
GITHUB_BRANCH = _env_branch if _env_branch else _get_current_git_branch()

# ============================================================================
# CONFIGURATION FILES
# ============================================================================

TEAM_CONFIG_PATH = CONFIG_DIR / 'team-config.yaml'
TEAM_GUIDS_PATH = CONFIG_DIR / 'team-guids.json'

# Default asset directories
DEFAULTS_DIR = CONFIG_DIR / 'defaults'
DEFAULT_BOX_DIR = DEFAULTS_DIR / 'box'
DEFAULT_BACKSIDE_DIR = DEFAULTS_DIR / 'card-backside'
DEFAULT_TTS_IMAGE_DIR = DEFAULTS_DIR / 'tts-image'
DEFAULT_TTS_SCRIPT_DIR = DEFAULTS_DIR / 'tts-script'
DEFAULT_TOKEN_DIR = DEFAULTS_DIR / 'tts-token'

# Team-specific asset directories
TEAMS_CONFIG_DIR = CONFIG_DIR / 'teams'

# ============================================================================
# PROCESSING SETTINGS
# ============================================================================

# Image extraction
DEFAULT_DPI = 300

# Token generation
DEFAULT_TOKEN_CANVAS_PX = 512
DEFAULT_TOKEN_MERGE_DISTANCE_PX = 5.0

# ============================================================================
# GITHUB URLS
# ============================================================================

GITHUB_REPO_OWNER = "Wen-Qualtu"
GITHUB_REPO_NAME = "kt-datacards"

# Branch comes from environment variable or defaults to main
# Note: GITHUB_BRANCH was set earlier in the file from KT_BRANCH env var

GITHUB_BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{GITHUB_BRANCH}"
GITHUB_OUTPUT_URL = f"{GITHUB_BASE_URL}/output"  # Legacy V1
GITHUB_OUTPUT_V2_URL = f"{GITHUB_BASE_URL}/output_v2"  # Current V2
GITHUB_TTS_URL = f"{GITHUB_BASE_URL}/tts_objects"


def get_github_url(path: str, branch: str = None) -> str:
    """
    Build a GitHub raw URL with dynamic branch support.
    
    Args:
        path: Relative path from repo root (e.g., 'output_v2/chaos/legionaries/datacards/...')
        branch: Optional branch override (default: uses GITHUB_BRANCH from env/config)
    
    Returns:
        Full GitHub raw URL
        
    Examples:
        >>> get_github_url('output_v2/chaos/team/datacards/card.jpg')
        'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output_v2/...'
        
        >>> get_github_url('tts_objects/file.json', branch='acc')
        'https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/acc/tts_objects/file.json'
    """
    _branch = branch or GITHUB_BRANCH
    return f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/{_branch}/{path}"

# ============================================================================
# OUTPUT FILES
# ============================================================================

# V2 output files
DATACARDS_URLS_JSON = OUTPUT_V2_DIR / "datacards-urls.json"
TTS_METADATA_JSON = OUTPUT_V2_DIR / "tts-metadata.json"
TTS_CARD_BOXES_JSON = OUTPUT_V2_DIR / "tts-card-boxes.json"
METADATA_YAML = OUTPUT_V2_DIR / "metadata.yaml"

# TTS objects
DISPLAY_TABLE_DIR = TTS_OBJECTS_DIR / "display-table"
DISPLAY_TABLE_JSON = DISPLAY_TABLE_DIR / "kt_all_teams_grid.json"
MANAGER_BAG_JSON = DISPLAY_TABLE_DIR / "kt_manager_only.json"
TEAM_SPAWNER_JSON = DISPLAY_TABLE_DIR / "kt_team_spawner.json"
TOKENS_DIR = TTS_OBJECTS_DIR / "tokens"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_team_config_dir(team_name: str) -> Path:
    """Get the config directory for a specific team.
    
    Args:
        team_name: Team slug (e.g., 'kasrkin', 'hearthkyn-salvagers')
    
    Returns:
        Path to team's config directory
    """
    return TEAMS_CONFIG_DIR / team_name


def get_team_box_dir(team_name: str) -> Path:
    """Get the custom box directory for a specific team.
    
    Args:
        team_name: Team slug
    
    Returns:
        Path to team's box assets, falls back to defaults if not exists
    """
    team_box = get_team_config_dir(team_name) / 'box'
    return team_box if team_box.exists() else DEFAULT_BOX_DIR


def get_team_backside_dir(team_name: str) -> Path:
    """Get the custom backside directory for a specific team.
    
    Args:
        team_name: Team slug
    
    Returns:
        Path to team's backside assets, falls back to defaults if not exists
    """
    team_backside = get_team_config_dir(team_name) / 'card-backside'
    return team_backside if team_backside.exists() else DEFAULT_BACKSIDE_DIR


def get_team_metadata_dir(team_name: str) -> Path:
    """Get the metadata directory for a specific team.
    
    Args:
        team_name: Team slug
    
    Returns:
        Path to team's metadata directory
    """
    return METADATA_DIR / team_name


def get_team_processed_dir(team_name: str) -> Path:
    """Get the processed PDFs directory for a specific team.
    
    Args:
        team_name: Team slug
    
    Returns:
        Path to team's processed directory
    """
    return PROCESSED_DIR / team_name


def get_team_output_v2_dir(team_name: str, faction: str) -> Path:
    """Get the output_v2 directory for a specific team.
    
    Args:
        team_name: Team slug
        faction: Faction name (imperium, chaos, xenos)
    
    Returns:
        Path to team's V2 output directory
    """
    return OUTPUT_V2_DIR / faction / team_name


def get_team_archive_dir(team_name: str) -> Path:
    """Get the archive directory for a specific team.
    
    Args:
        team_name: Team slug
    
    Returns:
        Path to team's archive directory
    """
    return ARCHIVE_DIR / team_name
