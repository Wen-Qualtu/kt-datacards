"""Card image processing — renders the classified PDFs to JPEG.

layers/integration/{team}/{team}-{type}-{name}[.-{card_number}].pdf
   ->  output/{team}/cards/{plural_type}/{base}-front.jpg (+ -back.jpg)

Each integration PDF holds the front on page 0 and the optional back on page 1.
Fronts (and any real back) are rendered at 300 DPI; when a card has no back page
the pre-generated team backside (``extract_backsides``) is used, falling back to
the global default. Datacards are landscape; all other card types are portrait.

Source-agnostic — drives off the shared integration PDFs + manifest instead of a
track-specific structure.json.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from ..utils import naming, paths
from ..utils.stable_io import stable_write
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

DPI = 300
ZOOM = DPI / 72  # PDF base is 72 DPI
JPEG_QUALITY = 90

# Card types in manifest order (plural underscore keys == output subdir names).
CARD_TYPES = (
    "datacards",
    "operatives_selection",
    "faction_rules",
    "equipment",
    "firefight_ploys",
    "strategy_ploys",
    "token_guide",
)

DEFAULT_BACKSIDE = {
    "portrait": paths.DEFAULTS / "card-backside" / "default-backside-portrait.jpg",
    "landscape": paths.DEFAULTS / "card-backside" / "default-backside-landscape.jpg",
}


def _sanitize_filename(name: str) -> str:
    """Canonical card-image slug — delegates to :func:`naming.slug`.

    Uses the SAME normalization as the classified PDF names (``naming.slug``) so
    a card only ever has ONE filename. Accents are transliterated (``DÔZR`` →
    ``dozr``) and punctuation is normalized consistently — apostrophes/periods
    dropped (``SHAS'UI`` → ``shasui``, ``C.A.T.`` → ``cat``) and ``! & , ‑`` and
    other non-alphanumerics collapsed to a hyphen (``SSSSHHHH!`` → ``sssshhhh``,
    ``FAITH & FURY`` → ``faith-fury``). This removes the punctuation/curly-quote
    duplicate cards (``sssshhhh`` vs ``sssshhhh!``, ``khaines`` vs ``khaine’s``).
    """
    return naming.slug(name)


def _image_base(team: str, card_type: str, name: str) -> str:
    """Legacy step-4 naming: datacards keep the operative name; other types get a
    team prefix (and a redundant team suffix stripped)."""
    sanitized = _sanitize_filename(name)
    if card_type == "datacards":
        return sanitized
    if not sanitized.startswith(f"{team}-"):
        if sanitized.endswith(f"-{team}"):
            sanitized = sanitized[: -len(team) - 1]
        sanitized = f"{team}-{sanitized}"
    return sanitized


def _entity_pdfs(team: str, entity: dict, card_type_key: str) -> list[Path]:
    """Resolve an entity's integration PDF paths (mirrors integrate_classified)."""
    card_type = naming.STRUCTURE_KEY_TO_TYPE.get(card_type_key, card_type_key)
    name = entity.get("name") or "unknown"
    cards = entity.get("cards", [])
    multi = len(cards) > 1
    pdfs: list[Path] = []
    for card in cards:
        base = naming.classified_name(team, card_type, name)
        if multi:
            base = f"{base}-{card['card_number']}"
        pdfs.append(paths.integration_team_dir(team) / f"{base}.pdf")
    return pdfs


def _render_page(doc: fitz.Document, page_idx: int, out_path: Path) -> bool:
    try:
        pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with stable_write(out_path):
            pix.save(out_path, jpg_quality=JPEG_QUALITY)
        return True
    except Exception as e:
        logger.error(f"  Failed to render {out_path.name}: {e}")
        return False


def _copy_default_backside(team: str, out_path: Path, is_portrait: bool) -> bool:
    orientation = "portrait" if is_portrait else "landscape"
    candidates = [
        paths.team_config_dir(team) / "card-backside" / f"{team}-backside-{orientation}.jpg",
        paths.team_config_dir(team) / "card-backside" / f"default-backside-{orientation}.jpg",
        paths.integration_team_dir(team) / "card-backside" / f"{team}-backside-{orientation}.jpg",
        DEFAULT_BACKSIDE[orientation],
    ]
    src = next((p for p in candidates if p.exists()), None)
    if not src:
        logger.error(f"  Backside not found for {team} ({orientation})")
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out_path)
    return True


def _process_team(team: str) -> int:
    manifest_path = paths.integration_manifest_file(team)
    if not manifest_path.exists():
        logger.error(f"  Manifest not found: {manifest_path}")
        return 0

    import json
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    total = 0
    for card_type in CARD_TYPES:
        entities = manifest.get(card_type) or []
        if not entities:
            continue
        out_dir = paths.team_output(team) / "cards" / card_type
        is_portrait = card_type != "datacards"

        for entity in entities:
            name = entity.get("name", "UNKNOWN")
            cards = entity.get("cards", [])
            pdfs = _entity_pdfs(team, entity, card_type)
            multi = len(cards) > 1
            base_name = _image_base(team, card_type, name)

            for idx, pdf_path in enumerate(pdfs, 1):
                if not pdf_path.exists():
                    logger.warning(f"  Missing PDF: {pdf_path.name}")
                    continue
                base = f"{base_name}-card{idx}" if multi else base_name

                try:
                    doc = fitz.open(pdf_path)
                    page_count = doc.page_count
                    front_ok = _render_page(doc, 0, out_dir / f"{base}-front.jpg")
                    has_back = page_count > 1
                    if has_back:
                        if _render_page(doc, 1, out_dir / f"{base}-back.jpg"):
                            total += 1
                    doc.close()
                except Exception as e:
                    logger.error(f"  Failed to open {pdf_path.name}: {e}")
                    continue

                if front_ok:
                    total += 1
                if not has_back and front_ok:
                    if _copy_default_backside(team, out_dir / f"{base}-back.jpg", is_portrait):
                        total += 1

    logger.info(f"  Rendered {total} card images")
    return total


def get_all_teams() -> list[str]:
    """All teams that have an integration manifest."""
    if not paths.INTEGRATION.exists():
        return []
    return sorted(
        d.name for d in paths.INTEGRATION.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )


def _inputs_for(team: str) -> list:
    """Source files this step renders from: the manifest, the classified PDFs, and
    every candidate backside (team override, config default, generated, global
    default) so a backside change re-renders the affected cards."""
    team_dir = paths.integration_team_dir(team)
    cfg_bs = paths.team_config_dir(team) / "card-backside"
    integ_bs = team_dir / "card-backside"
    inputs = [paths.integration_manifest_file(team)]
    inputs.extend(sorted(team_dir.glob("*.pdf")))
    for orient in ("portrait", "landscape"):
        inputs.append(cfg_bs / f"{team}-backside-{orient}.jpg")
        inputs.append(cfg_bs / f"default-backside-{orient}.jpg")
        inputs.append(integ_bs / f"{team}-backside-{orient}.jpg")
        inputs.append(DEFAULT_BACKSIDE[orient])
    return inputs


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No teams with a manifest found (run integrate_classified first)")
        return {"processed": 0, "failed": 0}

    logger.info(f"generate_card_images: {len(teams)} team(s)")

    processed = failed = skipped = 0
    for team in teams:
        logger.info(f"[{team}]")
        state = StateManager(team)
        inputs = _inputs_for(team)
        if state.can_skip("generate_card_images", inputs, force):
            logger.info("  unchanged, skip")
            skipped += 1
            continue

        try:
            count = _process_team(team)
        except Exception as e:
            logger.error(f"  Error: {e}")
            failed += 1
            continue
        if count > 0:
            processed += 1
            cards_root = paths.team_output(team) / "cards"
            for f in sorted(cards_root.rglob("*.jpg")):
                state.record_output("generate_card_images", f"cards/{f.relative_to(cards_root).as_posix()}", f)
            state.record_inputs("generate_card_images", inputs)
            state.mark_complete("generate_card_images")
            state.save()
        else:
            failed += 1

    StateIndex().rebuild_and_save()
    logger.info(f"generate_card_images done: processed={processed} skipped={skipped} failed={failed}")
    return {"processed": processed, "skipped": skipped, "failed": failed}

