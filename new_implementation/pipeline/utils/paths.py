"""Central path constants for the integrated pipeline sandbox.

Everything lives under ``new_implementation/`` and is fully detached from the
production pipelines at the repo root. Inside the sandbox we use clean names
(``input/``, ``layers/``, ``output/``) — no ``acc`` prefixes.
"""
from __future__ import annotations

from pathlib import Path

# new_implementation/ root: utils -> pipeline -> root
ROOT = Path(__file__).resolve().parents[2]

INPUT = ROOT / "input"     # raw PDFs for the kt-app track
LAYERS = ROOT / "layers"   # intermediate layers
OUTPUT = ROOT / "output"   # final outputs

# Shared config still lives at the repo root (read-only). Copy into the sandbox
# later if we want full isolation.
REPO_ROOT = ROOT.parent
TEAM_CONFIG = REPO_ROOT / "config" / "team-config.yaml"

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
#     {team}-{type}-{name}.pdf     classified single-card PDFs
#     manifest.json                entity grouping (source-agnostic)
#     content/{team}-content.json  content analysis
#     artwork/                     lore art + {team}-artwork-metadata.json
#       icons/                     token / portrait / landscape icons
# Run-level metadata lives at the integration root.
INTEGRATION = LAYERS / "integration"

PIPELINE_METADATA_FILE = INTEGRATION / "metadata.json"
OUTPUT_METADATA_FILE = INTEGRATION / "output-metadata.json"


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


# --- output ---------------------------------------------------------------
def team_output(team: str) -> Path:
    """output/{team}"""
    return OUTPUT / team
