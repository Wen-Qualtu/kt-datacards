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


# --- shared layers --------------------------------------------------------
SHARED = LAYERS / "shared"
ARTWORK = SHARED / "artwork"        # icons + artwork (both tracks write here)
INTEGRATION = SHARED / "integration"  # {team}-{type}-{name}.pdf (merge point)
INTEGRATION_MANIFESTS = INTEGRATION / "_manifests"  # {team}.json (entity grouping)
CONTENT = SHARED / "content"        # {team}-content.json (content analysis)


def artwork_team_dir(team: str) -> Path:
    """layers/shared/artwork/{team} — per-team icons/ + artwork/."""
    return ARTWORK / team


def classified_file(team: str, card_type: str, name: str) -> Path:
    """layers/shared/integration/{team}-{type}-{name}.pdf (no front/back postfix)."""
    return INTEGRATION / f"{team}-{card_type}-{name}.pdf"


def integration_manifest_file(team: str) -> Path:
    """layers/shared/integration/_manifests/{team}.json — source-agnostic entity
    grouping (a copy of the structure manifest) so downstream shared steps do not
    depend on which track ran."""
    return INTEGRATION_MANIFESTS / f"{team}.json"


def content_file(team: str) -> Path:
    return CONTENT / f"{team}-content.json"


# --- output ---------------------------------------------------------------
def team_output(team: str) -> Path:
    """output/{team}"""
    return OUTPUT / team
