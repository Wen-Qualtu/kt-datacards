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

import hashlib
import logging
import re
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

# Max per-channel pixel diff treated as pure re-encode/requant noise: a re-exported
# source PDF re-compresses embedded art, so a visually-identical card renders to
# different JPEG bytes. Below this the prior card file is kept (no churn); a real
# text/stat change flips glyph pixels fully (~255) and is always above it.
STABLE_IMAGE_TOLERANCE = 40

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
        with stable_write(out_path, image_tolerance=STABLE_IMAGE_TOLERANCE):
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


def _card_text_signature(pdf_bytes: bytes, team: str, is_portrait: bool) -> str:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page_count = doc.page_count
        text = "\x01".join(
            re.sub(r"\s+", " ", page.get_text()).strip()
            for page in doc
        )
    signature = hashlib.sha256(f"{page_count}\x00{text}".encode("utf-8")).hexdigest()
    if page_count == 1:
        orientation = "portrait" if is_portrait else "landscape"
        backside_candidates = [
            paths.team_config_dir(team) / "card-backside" / f"{team}-backside-{orientation}.jpg",
            paths.team_config_dir(team) / "card-backside" / f"default-backside-{orientation}.jpg",
            paths.integration_team_dir(team) / "card-backside" / f"{team}-backside-{orientation}.jpg",
            DEFAULT_BACKSIDE[orientation],
        ]
        backside = next((path for path in backside_candidates if path.exists()), None)
        backside_hash = StateManager._compute_hash(backside) if backside else "<missing>"
        signature = hashlib.sha256(
            f"{signature}\x00{backside_hash}".encode("utf-8")
        ).hexdigest()
    return signature


def _head_card_text_signature(pdf_path: Path, team: str, is_portrait: bool) -> Optional[str]:
    import subprocess

    try:
        relative = pdf_path.resolve().relative_to(paths.ROOT.resolve()).as_posix()
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=paths.ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return _card_text_signature(result.stdout, team, is_portrait)


def _team_card_entries(team: str) -> list[tuple[str, str, Path, bool]]:
    import json

    manifest_path = paths.integration_manifest_file(team)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    entries = []
    for card_type in CARD_TYPES:
        is_portrait = card_type != "datacards"
        for entity in manifest.get(card_type) or []:
            cards = entity.get("cards", [])
            base_name = _image_base(team, card_type, entity.get("name", "UNKNOWN"))
            pdfs = _entity_pdfs(team, entity, card_type)
            multi = len(cards) > 1
            for idx, pdf_path in enumerate(pdfs, 1):
                base = f"{base_name}-card{idx}" if multi else base_name
                entries.append((card_type, base, pdf_path, is_portrait))
    return entries


def _can_reuse_card(previous: Optional[str], current: str, outputs: list[Path], force: bool) -> bool:
    return not force and previous == current and all(path.is_file() for path in outputs)


def _stale_card_images(cards_root: Path, expected_outputs: set[Path]) -> list[Path]:
    expected = {path.resolve() for path in expected_outputs}
    if not cards_root.exists():
        return []
    return [path for path in cards_root.rglob("*.jpg") if path.resolve() not in expected]


def _prune_stale_card_images(cards_root: Path, expected_outputs: set[Path]) -> list[Path]:
    stale = _stale_card_images(cards_root, expected_outputs)
    for path in stale:
        path.unlink()
    return stale


def _expected_card_image_paths(team: str, entries) -> set[Path]:
    cards_root = paths.team_output(team) / "cards"
    return {
        output
        for card_type, base, _, _ in entries
        for output in (
            cards_root / card_type / f"{base}-front.jpg",
            cards_root / card_type / f"{base}-back.jpg",
        )
    }


def _process_team(team: str, prior_signatures: dict[str, str], force: bool):
    entries = _team_card_entries(team)
    completed_signatures = {}
    rendered = reused = 0
    cards_root = paths.team_output(team) / "cards"
    expected_outputs = _expected_card_image_paths(team, entries)

    for card_type, base, pdf_path, is_portrait in entries:
        if not pdf_path.exists():
            logger.warning(f"  Missing PDF: {pdf_path.name}")
            continue

        key = f"{card_type}/{base}"
        signature = _card_text_signature(pdf_path.read_bytes(), team, is_portrait)
        previous = prior_signatures.get(key)
        if previous is None and not force:
            previous = _head_card_text_signature(pdf_path, team, is_portrait)

        out_dir = paths.team_output(team) / "cards" / card_type
        front_path = out_dir / f"{base}-front.jpg"
        back_path = out_dir / f"{base}-back.jpg"
        if _can_reuse_card(previous, signature, [front_path, back_path], force):
            reused += 2
            completed_signatures[key] = signature
            continue

        try:
            with fitz.open(pdf_path) as doc:
                front_ok = _render_page(doc, 0, front_path)
                if doc.page_count > 1:
                    back_ok = _render_page(doc, 1, back_path)
                elif front_ok:
                    back_ok = _copy_default_backside(team, back_path, is_portrait)
                else:
                    back_ok = False
        except Exception as e:
            logger.error(f"  Failed to open {pdf_path.name}: {e}")
            continue

        rendered += int(front_ok) + int(back_ok)
        if front_ok and back_ok:
            completed_signatures[key] = signature

    stale = _prune_stale_card_images(cards_root, expected_outputs)
    logger.info(f"  Rendered {rendered} card images; reused {reused}; removed {len(stale)} stale")
    return rendered, reused, completed_signatures, len(entries)


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


def _text_signature(team: str) -> str:
    """SHA-256 of the team's classified PDFs' normalized text (+ filenames).

    The rendered card is a function of the source PDF's TEXT, not its bytes, so
    this ignores re-export byte churn and is identical across tracks (kt-app and
    warcom emit the same classified file set + rules text). Used to skip a whole
    team's re-render when nothing textual changed.
    """
    parts = []
    for pdf in sorted(paths.integration_team_dir(team).glob("*.pdf")):
        try:
            with fitz.open(pdf) as doc:
                txt = "".join(p.get_text() for p in doc)
        except Exception:
            txt = "<err>"
        parts.append(pdf.name + "\x00" + re.sub(r"\s+", " ", txt).strip())
    return hashlib.sha256("\x01".join(parts).encode("utf-8")).hexdigest()


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
        step_state = state.state["steps"].get("generate_card_images", {})
        prior_signatures = step_state.get("card_text_signatures", {})
        try:
            entries = _team_card_entries(team)
        except Exception as e:
            logger.error(f"  Error: {e}")
            failed += 1
            continue

        stale_images = _stale_card_images(
            paths.team_output(team) / "cards",
            _expected_card_image_paths(team, entries),
        )
        if not force and not stale_images and prior_signatures and len(prior_signatures) == len(entries) \
                and state.can_skip("generate_card_images", inputs, force):
            logger.info("  unchanged, skip")
            skipped += 1
            continue

        try:
            rendered, reused, card_signatures, entry_count = _process_team(
                team, prior_signatures, force
            )
        except Exception as e:
            logger.error(f"  Error: {e}")
            failed += 1
            continue

        if card_signatures:
            processed += int(rendered > 0)
            skipped += int(rendered == 0 and reused > 0)
            failed += int(len(card_signatures) < entry_count)
            cards_root = paths.team_output(team) / "cards"
            step_state = state.state["steps"].setdefault("generate_card_images", {})
            step_state["outputs"] = {}
            for f in sorted(cards_root.rglob("*.jpg")):
                state.record_output("generate_card_images", f"cards/{f.relative_to(cards_root).as_posix()}", f)
            state.record_inputs("generate_card_images", inputs)
            state.state["steps"]["generate_card_images"]["text_signature"] = _text_signature(team)
            state.state["steps"]["generate_card_images"]["card_text_signatures"] = card_signatures
            state.mark_complete("generate_card_images")
            state.save()
        else:
            failed += 1

    StateIndex().rebuild_and_save()
    logger.info(f"generate_card_images done: processed={processed} skipped={skipped} failed={failed}")
    return {"processed": processed, "skipped": skipped, "failed": failed}

