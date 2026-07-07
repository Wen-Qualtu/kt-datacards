"""Central path constants for the integrated pipeline sandbox.

Everything lives under ``new_implementation/`` and is fully detached from the
production pipelines at the repo root. Inside the sandbox we use clean names
(``input/``, ``layers/``, ``output/``) — no ``acc`` prefixes.
"""
from __future__ import annotations

import shutil
from pathlib import Path

# new_implementation/ root: utils -> pipeline -> root
ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "input"                 # raw PDFs for the kt-app track (inbox)
INPUT_ARCHIVE = ROOT / "input_archive" # consumed input PDFs are moved here
LAYERS = ROOT / "layers"   # intermediate layers
OUTPUT = ROOT / "output"   # final outputs

# Config is self-contained inside the sandbox (copied from the repo-root config
# and stripped of pre-baked token data + the tokens_ready flag so the pipeline
# regenerates everything from scratch).
REPO_ROOT = ROOT.parent
CONFIG = ROOT / "config"
DEFAULTS = CONFIG / "defaults"
TEAM_CONFIG = CONFIG / "team-config.yaml"


def archive_input(pdf_path: Path) -> Path:
    """Move a consumed kt-app input PDF into ``input_archive/`` so ``input/``
    only ever holds not-yet-processed files (an inbox). Overwrites any existing
    archived copy. Returns the destination path; no-op-safe if already gone."""
    INPUT_ARCHIVE.mkdir(parents=True, exist_ok=True)
    dest = INPUT_ARCHIVE / pdf_path.name
    if not pdf_path.exists():
        return dest
    if dest.exists():
        dest.unlink()
    shutil.move(str(pdf_path), str(dest))
    return dest


def team_config_dir(team: str) -> Path:
    """config/teams/{team} — per-team manual overrides (backsides, dice, box)."""
    return CONFIG / "teams" / team

VALID_TRACKS = ("kt-app", "warcom")


# --- track-specific front-end layers -------------------------------------
def track_dir(track: str) -> Path:
    """layers/{track}"""
    return LAYERS / track


def staging_dir(track: str) -> Path:
    """layers/{track}/staging — warcom scrape target."""
    return track_dir(track) / "staging"


def extracted_dir(track: str) -> Path:
    """layers/{track}/extracted — per-card split PDFs."""
    return track_dir(track) / "extracted"


def structure_dir(track: str) -> Path:
    """layers/{track}/structure — per-track structure manifests."""
    return track_dir(track) / "structure"


def structure_file(track: str, team: str) -> Path:
    return structure_dir(track) / f"{team}-structure.json"


# --- integration layer (shared, source-agnostic merge point) --------------
# One folder per team holds everything produced after the two tracks converge:
#   layers/integration/{team}/
#     {team}-{type}-{name}.pdf         classified single-card PDFs
#     manifest.json                    entity grouping (source-agnostic)
#     content/{team}-content.json      content analysis
#     artwork/                         lore art + {team}-artwork-metadata.json
#       icons/                         token / portrait / landscape icons
#     {team}-pipeline-state.json       per-team step completion + output hashes
# A global index at the integration root points to every team's state file:
#     pipeline-state.json              teams -> state-file path + last_updated, last_run
INTEGRATION = LAYERS / "integration"

# Global registry: teams -> {state, last_updated} + last_run. Derived (rebuilt by
# scanning the per-team state files), so it never holds stale team keys.
PIPELINE_STATE_INDEX = INTEGRATION / "pipeline-state.json"


def integration_team_dir(team: str) -> Path:
    """layers/integration/{team} — per-team integration root."""
    return INTEGRATION / team


def classified_file(team: str, card_type: str, name: str) -> Path:
    """layers/integration/{team}/{team}-{type}-{name}.pdf (no front/back postfix)."""
    return integration_team_dir(team) / f"{team}-{card_type}-{name}.pdf"


def integration_manifest_file(team: str) -> Path:
    """layers/integration/{team}/manifest.json — source-agnostic entity grouping
    (a copy of the structure manifest) so downstream shared steps do not depend on
    which track ran."""
    return integration_team_dir(team) / "manifest.json"


def content_dir(team: str) -> Path:
    """layers/integration/{team}/content."""
    return integration_team_dir(team) / "content"


def content_file(team: str) -> Path:
    return content_dir(team) / f"{team}-content.json"


def artwork_team_dir(team: str) -> Path:
    """layers/integration/{team}/artwork — lore art files + an icons/ subfolder."""
    return integration_team_dir(team) / "artwork"


def pipeline_state_file(team: str) -> Path:
    """layers/integration/{team}/{team}-pipeline-state.json — per-team step
    completion + output hashes for change detection (rewritten wholly per run,
    so there are no stale cross-team keys)."""
    return integration_team_dir(team) / f"{team}-pipeline-state.json"


# --- output ---------------------------------------------------------------
def team_output(team: str) -> Path:
    """output/{team}"""
    return OUTPUT / team
