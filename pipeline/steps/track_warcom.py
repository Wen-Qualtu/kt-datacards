"""Front-end (warcom track): scrape + coordinate-map per-card split.

scrape site  ->  layers/warcom/staging/*.pdf          (an inbox)
                 ->  layers/warcom/extracted/{team}/cards/*.pdf  (per-card split)
                 ->  layers/warcom/staging_archive/*.pdf         (processed source)

``staging`` is treated as an inbox: a PDF is downloaded, split, then moved to
``staging_archive`` so the inbox only ever holds not-yet-processed files. A
re-run skips downloading anything already in staging or the archive, so an
unchanged team is never re-fetched; only a new/renamed dataslate PDF flows in.
``extract_artwork`` reads from staging AND the archive so art extraction still
finds each team's source after the split has archived it.

Standalone implementation. The low-level work lives in the local
``warcom`` package:

  - scrape:  warcom.scraper        (Playwright + requests)
  - split:   warcom.card_extractor (template/marker per-card PDF split, PDF only)

The scrape downloads ALL team-rules PDFs from the kill-team page; team identity is
read from PDF content afterwards. When --teams is given we filter the scraped URLs
by team slug (the slug appears in the PDF filename) to avoid pulling every team.

Token extraction is intentionally NOT done here. Tokens are produced once per team
by the shared ``extract_tokens`` step.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from ..utils import naming, paths
from ..utils.parallel import map_items
from ..utils.state import StateIndex, StateManager
from .warcom import card_extractor, scraper

logger = logging.getLogger(__name__)

TRACK = "warcom"

TEMPLATES_FILE = paths.CONFIG / "pipelines" / "warcom" / "card_templates.json"
DEFAULT_URL = scraper.DOWNLOADS_URL


def _slug(value: str) -> str:
    return naming.slug(value)


def _team_from_filename(pdf: Path, team_config: dict) -> Optional[str]:
    """Identify the team from the staging PDF filename via team-config slugs.

    The scrape names each download after its team (``..._teamrules_sanctifiers-…``),
    so the filename is a far more reliable identity than the in-PDF font heuristic
    (which mis-read e.g. "Sanctifiers" as "sanctifiers-update-log"). Returns the
    config-key slug of the longest matching team, or None.
    """
    fname = _slug(pdf.stem)
    best: Optional[str] = None
    for config_key, config_data in team_config.items():
        candidates = [config_key, config_data.get("canonical_name", "")]
        candidates += config_data.get("aliases", []) or []
        for candidate in candidates:
            cand = _slug(candidate)
            if cand and cand in fname:
                key = _slug(config_key)
                if best is None or len(key) > len(best):
                    best = key
    return best


def recent_team_slugs(teams: Optional[List[str]] = None) -> List[str]:
    """Team slugs whose rules appear in the site's "Recently Added" section.

    Scrapes only the Recently Added accordion and maps each PDF filename to a
    team-config slug (non-team files — update logs, mission packs, companions —
    map to None and are dropped). When ``teams`` is given, the result is
    intersected with it. Used to drive a "process only the latest dataslate"
    pipeline run without hand-listing the changed teams.
    """
    team_config = card_extractor.load_team_config(paths.TEAM_CONFIG)
    try:
        urls = asyncio.run(
            scraper.extract_pdf_urls_from_page(DEFAULT_URL, section="Recently Added")
        )
    except Exception as e:
        logger.error(f"Recently Added scrape failed: {e}")
        return []

    slugs: List[str] = []
    for url in urls:
        team = _team_from_filename(Path(url), team_config)
        if team:
            slugs.append(team)
    result = sorted(set(slugs))

    if teams:
        wanted = {_slug(t) for t in teams}
        result = [s for s in result if s in wanted]
    return result


def _purge_stale_staging(staging: Path, keep: List[Path], team_config: dict) -> int:
    """Delete staging PDFs superseded by a freshly-downloaded one for the same team.

    GW renames a team's download between releases (``eng_28-01_kt_teamrules_x`` →
    ``eng_x_online_rules``), so the new file does not overwrite the old and both
    linger — front_end would then split the stale one. For every team that has a
    kept (current) PDF, remove any other staging PDF mapping to that team.
    """
    keep_set = {p.resolve() for p in keep}
    kept_teams = {}
    for p in keep:
        t = _team_from_filename(p, team_config)
        if t:
            kept_teams[t] = p
    removed = 0
    for pdf in staging.glob("*.pdf"):
        if pdf.resolve() in keep_set:
            continue
        t = _team_from_filename(pdf, team_config)
        if t and t in kept_teams:
            try:
                pdf.unlink()
                removed += 1
                logger.info(f"  purged stale staging (superseded): {pdf.name}")
            except OSError:
                pass
    return removed


def _scrape(teams: Optional[List[str]], force: bool, section: str = "Team Rules") -> List[Path]:
    """Scrape + download team-rules PDFs into the staging dir.

    ``section`` selects the downloads-page accordion to read: ``"Team Rules"``
    (all teams) or ``"Recently Added"`` (only the latest balance/dataslate PDFs).
    After downloading, stale same-team PDFs from prior releases are purged so
    exactly one staging PDF per team remains.
    Returns the list of staging PDF paths relevant to this run.
    """
    staging = paths.staging_dir(TRACK)
    staging.mkdir(parents=True, exist_ok=True)

    try:
        urls = asyncio.run(scraper.extract_pdf_urls_from_page(DEFAULT_URL, section=section))
    except Exception as e:
        logger.error(f"Scrape failed: {e}")
        return []

    if teams:
        wanted = {_slug(t) for t in teams}
        filtered = []
        for url in urls:
            fname = _slug(Path(url).stem)
            if any(w in fname for w in wanted):
                filtered.append(url)
        logger.info(f"Filtered {len(urls)} scraped URLs down to {len(filtered)} for teams={sorted(wanted)}")
        urls = filtered

    downloaded: List[Path] = []
    archive = paths.staging_archive_dir(TRACK)
    for url in urls:
        name = Path(url).name
        out = staging / name
        archived = archive / name
        if out.exists() and not force:
            logger.info(f"  staging exists, skipping download: {name}")
            downloaded.append(out)
            continue
        if archived.exists() and not force:
            # Already processed in a prior run — don't re-download. Still hand it
            # to _extract so its change-detection gate can heal a missing split.
            logger.info(f"  already processed (archived), skipping download: {name}")
            downloaded.append(archived)
            continue
        logger.info(f"  downloading {name}")
        if scraper.download_pdf(url, out):
            downloaded.append(out)
        else:
            logger.warning(f"  failed to download {url}")

    if downloaded:
        team_config = card_extractor.load_team_config(paths.TEAM_CONFIG)
        _purge_stale_staging(staging, downloaded, team_config)
    return downloaded


def _extract(staging_pdfs: List[Path], teams: Optional[List[str]], force: bool, jobs: int = 1) -> dict:
    """Split each staging PDF into per-card PDFs under extracted/{team}/cards.

    One staging PDF per team, so the per-PDF workers never touch the same team
    state file — safe to fan out across a thread pool.
    """
    templates = card_extractor.load_templates(TEMPLATES_FILE)
    team_config = card_extractor.load_team_config(paths.TEAM_CONFIG)
    extracted_root = paths.extracted_dir(TRACK)

    wanted = {_slug(t) for t in teams} if teams else None

    def worker(pdf: Path) -> dict:
        stat = {"processed": 0, "skipped": 0, "failed": 0, "cards": 0}
        try:
            # Team identity comes from the filename (reliable) first; the in-PDF
            # font heuristic is only a last resort.
            team_name = _team_from_filename(pdf, team_config)
            if not team_name:
                extracted_name = card_extractor.extract_team_name_from_pdf(pdf)
                if not extracted_name:
                    logger.warning(f"  no team name from {pdf.name}")
                    stat["failed"] = 1
                    return stat
                team_name = card_extractor.match_team_name(extracted_name, team_config) or _slug(extracted_name)
            if wanted and team_name not in wanted:
                stat["skipped"] = 1
                return stat

            # The staging PDF is the durable source; gate on its content hash so a
            # re-scrape of the byte-identical rules PDF is not re-split while its
            # extracted cards are still on disk. (A fresh run has no baseline, so
            # this always processes on the first run.)
            state = StateManager(team_name)
            pdf_hash = StateManager._compute_hash(pdf)
            if state.source_can_skip("front_end", "cards", pdf_hash, force):
                logger.info(f"  = {team_name}: unchanged (skip split)")
                paths.archive_staging(pdf, TRACK)  # inbox: processed, move out of staging
                stat["skipped"] = 1
                return stat

            team_cards_dir = extracted_root / team_name / "cards"
            if team_cards_dir.exists():
                shutil.rmtree(team_cards_dir, ignore_errors=True)

            result = card_extractor.extract_cards(
                pdf, templates, team_cards_dir, team_name=team_name, dpi=150
            )
            logger.info(
                f"  {team_name}: {result['total_cards']} cards from "
                f"{result['pages_processed']} pages -> {team_cards_dir}"
            )
            state.record_source("front_end", "cards", pdf_hash,
                                sorted(team_cards_dir.glob("*.pdf")))
            state.mark_complete("front_end")
            state.save()
            paths.archive_staging(pdf, TRACK)  # inbox: processed, move out of staging
            stat["processed"] = 1
            stat["cards"] = result["total_cards"]
        except Exception as e:
            logger.error(f"  failed on {pdf.name}: {e}", exc_info=True)
            stat["failed"] = 1
        return stat

    stats = {"processed": 0, "skipped": 0, "failed": 0, "cards": 0}
    for stat in map_items(worker, staging_pdfs, jobs=jobs):
        for k in stats:
            stats[k] += stat[k]

    # Keep the archive an at-most-one-per-team store (drop superseded versions).
    archive = paths.staging_archive_dir(TRACK)
    archived = [archive / p.name for p in staging_pdfs if (archive / p.name).exists()]
    if archived:
        _purge_stale_staging(archive, archived, team_config)

    StateIndex().rebuild_and_save()
    return stats


def run(teams=None, source=None, force=False, jobs=1):
    if not TEMPLATES_FILE.exists():
        raise SystemExit(f"warcom templates not found: {TEMPLATES_FILE}")

    staging_pdfs = _scrape(teams, force)
    if not staging_pdfs:
        logger.error("No staging PDFs available after scrape")
        return {"processed": 0, "skipped": 0, "failed": 0, "cards": 0}

    stats = _extract(staging_pdfs, teams, force, jobs=jobs)
    logger.info(
        f"warcom front-end done: processed={stats['processed']} cards={stats['cards']} "
        f"skipped={stats['skipped']} failed={stats['failed']}"
    )
    return stats
