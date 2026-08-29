"""Icon + artwork extraction — runs on the RAW source, writes the shared artwork layer.

raw source  ->  layers/integration/{team}/artwork/{icons/,*.jpeg}
  - kt-app:  input/*.pdf                              (UUID-named; team by content)
  - warcom:  layers/warcom/staging/{team}-datacards.pdf (team by filename)

Both tracks write the SAME per-team artwork layer. The heavy pixel work lives in
``pipeline.utils.artwork`` so the two tracks can never drift apart — this module
only resolves *where the raw PDF is* and *which team it belongs to*.

Downstream (dice / box texture / backsides / TTS) consumes only the token icon
and its transparent variant, so both tracks always produce those. The warcom
datacards PDF additionally has page-0 card-back icons (portrait/landscape); we
emit them too when present, but the integrated pipeline does not require them.
"""
from __future__ import annotations

import logging
from typing import Optional

import fitz  # PyMuPDF

from ..utils import artwork, paths, team_config
from ..utils.state import StateIndex, StateManager
from ..utils.team_identification import TeamIdentifier, normalize_name

logger = logging.getLogger(__name__)

# Generic-background hashes for artwork dedup (optional — skipped if absent).
GENERIC_DIR = paths.LAYERS / "warcom" / "extracted" / "_generic"


# ---------------------------------------------------------------------------
# Team resolution
# ---------------------------------------------------------------------------
# The team symbol lives on the "KILL TEAM" selection page of the *designed*
# supplement layout (large page, ~609pt wide). The compact app export also has a
# "KILL TEAM" page but it is text-only at the icon crop (small page, ~198pt), so
# it must never win when a designed page exists.
MIN_DESIGNED_PAGE_WIDTH = 400.0


def _classify_source(doc: fitz.Document, identifier: TeamIdentifier) -> tuple[Optional[str], int]:
    """Resolve (team slug, icon-source rank) for a supplementary PDF.

    Slug comes from an "<NAME> UPDATE LOG" or "<NAME> KILL TEAM" title. Icon rank
    depends only on whether the PDF actually carries the icon-bearing KILL TEAM
    page (a mere UPDATE LOG errata page has no icon):
      2 = KILL TEAM page in the designed large format (has the team symbol)
      1 = KILL TEAM page only in the compact app export (text-only at the crop)
      0 = no KILL TEAM page (never an icon source)
    """
    slug: Optional[str] = None
    for page in doc:
        lines = [ln.strip() for ln in page.get_text().split("\n") if ln.strip()]
        for i, line in enumerate(lines):
            upper = line.upper()
            candidate: Optional[str] = None
            if "UPDATE LOG" in upper:
                candidate = upper.split(":")[0].replace("UPDATE LOG", "").strip()
            elif upper == "KILL TEAM" and i > 0:
                candidate = lines[i - 1]
            elif "KILL TEAM" in upper:
                candidate = upper.replace("KILL TEAM", "").replace("SELECTION", "").strip()
            if candidate and slug is None:
                team = identifier.identify_team(candidate)
                if team:
                    slug = team.name
        if slug:
            break

    kt = artwork.find_kill_team_page(doc)
    if kt == -1:
        rank = 0
    else:
        rank = 2 if doc[kt].rect.width >= MIN_DESIGNED_PAGE_WIDTH else 1
    return slug, rank


def _canonical_name(identifier: TeamIdentifier, slug: str) -> str:
    team = identifier.teams.get(slug)
    if team:
        return team.metadata.get("canonical_name", "") or ""
    return ""


# ---------------------------------------------------------------------------
# Per-source drivers
# ---------------------------------------------------------------------------
def _process_kt_app(teams: Optional[list], force: bool) -> dict:
    identifier = TeamIdentifier()
    generic_exact, generic_perceptual = artwork.load_generic_hashes(GENERIC_DIR)

    # Pass 1: resolve each PDF to (team, rank) and keep the best source per team.
    # Several PDFs can resolve to the same team (compact selection page + the
    # designed supplement) — the highest rank wins so the icon is deterministic.
    best: dict = {}  # slug -> (rank, pdf_path)
    identified_no_icon: dict = {}  # slug -> pdf_path (identified but no icon page)
    results = {"processed": [], "skipped": [], "unidentified": 0, "no_icon_source": []}

    for pdf in sorted(paths.INPUT.glob("*.pdf")):
        doc = fitz.open(pdf)
        try:
            slug, rank = _classify_source(doc, identifier)
        finally:
            doc.close()
        if not slug:
            results["unidentified"] += 1
            continue
        if teams and slug not in teams:
            continue
        if rank == 0:
            # Identified (e.g. an UPDATE LOG errata PDF) but this PDF carries no
            # icon-bearing KILL TEAM page. Remember it in case no better source
            # for the team turns up.
            identified_no_icon.setdefault(slug, pdf)
            continue
        if slug not in best or rank > best[slug][0]:
            best[slug] = (rank, pdf)

    # Teams we saw but never found an icon-bearing page for -> report the gap.
    for slug, pdf in sorted(identified_no_icon.items()):
        if slug not in best:
            logger.warning(f"  ! {slug}: identified but no KILL TEAM icon page in input ({pdf.name})")
            results["no_icon_source"].append(slug)

    # Pass 2: extract from the chosen source per team.
    for slug, (_rank, pdf) in sorted(best.items()):
        if team_config.asset_ready(slug, "artwork") and not force:
            logger.info(f"  = {slug}: artwork_ready in config, skip")
            results["skipped"].append(slug)
            paths.archive_input(pdf)
            continue
        out = paths.artwork_team_dir(slug)
        icons_dir = out / "icons"
        token_jpg = icons_dir / f"{slug}-icon-token.jpg"

        # The chosen source PDF is archived after extraction, so gate on its
        # *content* hash: a re-dropped byte-identical supplement is skipped while
        # its icon/artwork outputs are still on disk. A changed source re-extracts
        # even if a stale token icon exists.
        state = StateManager(slug)
        pdf_hash = StateManager._compute_hash(pdf)
        if token_jpg.exists() and state.source_can_skip("extract_artwork", "artwork", pdf_hash, force):
            logger.info(f"  = {slug}: unchanged (skip)")
            results["skipped"].append(slug)
            paths.archive_input(pdf)
            continue

        doc = fitz.open(pdf)
        try:
            icons = artwork.extract_token_icon(doc, icons_dir, slug, _canonical_name(identifier, slug))
            images = artwork.extract_artwork(
                doc, out, slug, generic_exact, generic_perceptual
            )
            artwork.write_artwork_metadata(out, slug, images)
        finally:
            doc.close()

        n_icons = sum(1 for v in icons.values() if v)
        logger.info(f"  + {slug}: {n_icons} icon files, {len(images)} artwork  ({pdf.name})")
        results["processed"].append(slug)
        state.record_source("extract_artwork", "artwork", pdf_hash,
                            [p for p in out.rglob("*") if p.is_file()])
        state.mark_complete("extract_artwork")
        state.save()
        # Consumed: move the supplement out of the inbox into input_archive/.
        paths.archive_input(pdf)

    StateIndex().rebuild_and_save()
    return results


def _team_from_warcom_filename(pdf, identifier: TeamIdentifier) -> Optional[str]:
    """Resolve the team slug from a scraped warcom staging filename.

    The scrape names each download after its team (``..._team_rules_kasrkin_…``),
    so the filename is the reliable identity (mirrors track_warcom._team_from_filename).
    Returns the config-key slug of the longest matching team, or None.
    """
    fname = normalize_name(pdf.stem)
    best: Optional[str] = None
    for slug, team in identifier.teams.items():
        for candidate in [slug, *(team.aliases or [])]:
            cand = normalize_name(candidate)
            if cand and cand in fname:
                if best is None or len(slug) > len(best):
                    best = slug
    return best


def _process_warcom(teams: Optional[list], force: bool) -> dict:
    identifier = TeamIdentifier()
    generic_exact, generic_perceptual = artwork.load_generic_hashes(GENERIC_DIR)

    staging = paths.staging_dir("warcom")
    archive = paths.staging_archive_dir("warcom")
    # front_end moves processed PDFs from staging into staging_archive, so read
    # both; an unprocessed inbox file wins over its archived copy for a team.
    pdfs = []
    seen: set = set()
    for pdf in sorted(staging.glob("*.pdf")) + sorted(archive.glob("*.pdf")):
        slug = _team_from_warcom_filename(pdf, identifier)
        if slug and slug in seen:
            continue
        if slug:
            seen.add(slug)
        pdfs.append(pdf)
    results = {"processed": [], "skipped": [], "unidentified": 0}

    for pdf in pdfs:
        slug = _team_from_warcom_filename(pdf, identifier)
        if not slug:
            results["unidentified"] += 1
            continue
        if teams and slug not in teams:
            continue
        if team_config.asset_ready(slug, "artwork") and not force:
            logger.info(f"  = {slug}: artwork_ready in config, skip")
            results["skipped"].append(slug)
            continue

        out = paths.artwork_team_dir(slug)
        icons_dir = out / "icons"
        token_jpg = icons_dir / f"{slug}-icon-token.jpg"

        state = StateManager(slug)
        pdf_hash = StateManager._compute_hash(pdf)
        if token_jpg.exists() and state.source_can_skip("extract_artwork", "artwork", pdf_hash, force):
            logger.info(f"  = {slug}: unchanged (skip)")
            results["skipped"].append(slug)
            continue

        doc = fitz.open(pdf)
        try:
            icons = artwork.extract_backside_icons(doc, icons_dir, slug)
            icons.update(artwork.extract_token_icon(doc, icons_dir, slug, _canonical_name(identifier, slug)))
            images = artwork.extract_artwork(
                doc, out, slug, generic_exact, generic_perceptual
            )
            artwork.write_artwork_metadata(out, slug, images)
        finally:
            doc.close()

        n_icons = sum(1 for v in icons.values() if v)
        logger.info(f"  + {slug}: {n_icons} icon files, {len(images)} artwork  ({pdf.name})")
        results["processed"].append(slug)
        state.record_source("extract_artwork", "artwork", pdf_hash,
                            [p for p in out.rglob("*") if p.is_file()])
        state.mark_complete("extract_artwork")
        state.save()

    StateIndex().rebuild_and_save()
    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run(teams=None, source=None, force=False):
    source = source or "kt-app"
    logger.info(f"extract_artwork: source={source} teams={teams or 'ALL'} force={force}")

    if source == "warcom":
        results = _process_warcom(teams, force)
    else:
        results = _process_kt_app(teams, force)

    # Flag every team whose artwork is now complete (freshly extracted or already
    # present) so later runs skip it. Written once here (both track loops done).
    ready = set(results.get("processed", [])) | set(results.get("skipped", []))
    n = team_config.mark_ready((t, "artwork") for t in ready)
    if n:
        logger.info(f"  set artwork_ready for {n} team(s)")

    logger.info(
        f"extract_artwork done: processed={len(results['processed'])} "
        f"skipped={len(results['skipped'])} unidentified={results['unidentified']}"
    )
    no_icon = results.get("no_icon_source")
    if no_icon:
        logger.warning(
            f"extract_artwork: {len(no_icon)} team(s) identified with no icon page in input: "
            + ", ".join(no_icon)
        )
    return results
