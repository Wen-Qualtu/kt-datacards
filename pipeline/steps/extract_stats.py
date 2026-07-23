"""Stats / team data — from the content map.

layers/integration/{team}/content/{team}-content.json
   ->  output/{team}/data/{team}-team-data.json

The content map produced by ``content_analysis`` already has the exact team-data
schema (datacards, equipment, faction_rules, ploys, operatives_selection). This
step simply relocates it into the ``output`` tree for the TTS step to consume,
writing byte-stably: if the content (excluding the volatile ``generated_at``
timestamp) is unchanged, the prior file's bytes + mtime are restored so
downstream cache-busters do not spuriously bump.

Source-agnostic (reads the shared content map).
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Optional

from ..utils import paths
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)


def _save_stable(team_data: dict, output_path) -> bool:
    """Write team_data as JSON; restore prior bytes+mtime when nothing but the
    ``generated_at`` timestamp changed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        prior_bytes = None
        prior_mtime = None
        if output_path.exists():
            try:
                prior_bytes = output_path.read_bytes()
                prior_mtime = output_path.stat().st_mtime
            except OSError:
                prior_bytes = None

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(team_data, f, indent=2, ensure_ascii=False)

        if prior_bytes is not None:
            try:
                prior_obj = json.loads(prior_bytes.decode("utf-8-sig"))
                prior_snap = copy.deepcopy(prior_obj)
                new_snap = copy.deepcopy(team_data)
                for snap in (prior_snap, new_snap):
                    if isinstance(snap, dict) and "generated_at" in snap:
                        snap["generated_at"] = ""
                if json.dumps(prior_snap, sort_keys=True) == json.dumps(new_snap, sort_keys=True):
                    output_path.write_bytes(prior_bytes)
                    if prior_mtime is not None:
                        os.utime(output_path, (prior_mtime, prior_mtime))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                pass  # keep the freshly-written file

        logger.info(f"  Saved: {output_path.name}")
        return True
    except Exception as e:
        logger.error(f"  Failed to save team data: {e}")
        return False


def get_all_teams() -> list[str]:
    """All teams that have a content map."""
    if not paths.INTEGRATION.exists():
        return []
    return sorted(
        d.name for d in paths.INTEGRATION.iterdir()
        if d.is_dir() and paths.content_file(d.name).exists()
    )


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No teams with a content map found (run content_analysis first)")
        return {"processed": 0, "skipped": 0, "failed": 0}

    logger.info(f"extract_stats: {len(teams)} team(s)")

    processed = skipped = failed = 0
    for team in teams:
        content_path = paths.content_file(team)
        if not content_path.exists():
            logger.warning(f"  {team}: no content map, skipping")
            skipped += 1
            continue

        state = StateManager(team)
        inputs = [content_path]
        if state.can_skip("extract_stats", inputs, force):
            logger.info(f"  {team}: unchanged, skip")
            skipped += 1
            continue

        try:
            with open(content_path, "r", encoding="utf-8") as f:
                team_data = json.load(f)
        except Exception as e:
            logger.error(f"  {team}: failed to read content map: {e}")
            failed += 1
            continue

        out_path = paths.team_output(team) / "data" / f"{team}-team-data.json"
        if _save_stable(team_data, out_path):
            processed += 1
            state.record_output("extract_stats", "team-data.json", out_path)
            state.record_inputs("extract_stats", inputs)
            state.mark_complete("extract_stats")
            state.save()
        else:
            failed += 1

    StateIndex().rebuild_and_save()
    logger.info(
        f"extract_stats done: processed={processed} skipped={skipped} failed={failed}"
    )
    return {"processed": processed, "skipped": skipped, "failed": failed}
