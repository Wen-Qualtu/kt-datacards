"""TTS assets + objects — LAST step. Consumes cards, stats, tokens, dice, box texture.

output/{team}/{cards,data,tokens,dice,cardbox}  ->  output/{team}/tts_objects/{Team}.json

Emits the bare/legacy dual box format: embedded stats + Lua, stable hashing, and
persistent GUIDs.

Behaviour notes:
  - Token tags: honour config token `type: both` -> ["KTUIToken", "KTUIMarker",
    "KTUITokenSimple"] (a marker that can also be picked up / attached to a model),
    alongside the existing marker/token/custom mappings (_build_token_tags_map).
  - GMNotes: when an operative has a `base_size` (extracted by content_analysis),
    surface it as stats['Base'] in _build_gm_notes.
  - KTUI enhanced stat-loading: the ktui-mini-modelscript.lua extender is embedded
    via a KTUI_MODELSCRIPT prefix on each datacard's Lua, so "Load stats to model"
    can turn any plain model into a KTUI-compatible mini on the fly.

IMPLEMENTATION NOTES:
  - The heavy lifting lives in pipeline/steps/tts_impl.py + pipeline/steps/templates/.
  - Scope: per-team {Team}.json (clean bare box) + individual card/dice JSONs.
    Also finalizes the hosting
    metadata: per-team {team}-object-urls.json + a global team-urls.json summary
    (content-hashed for stable in-game update checks). The cross-team manager bag
    is still left out for now (production-hosting concern; portable later).
  - Cardbox mesh + texture come from generate_box_texture (output/{team}/cardbox).
  - Token BAGS need per-token .obj meshes. The pipeline does not yet produce token
    meshes, so load_token_bag gracefully returns None and the box ships with card
    decks + dice only.
  - Image URLs default to the repo-root host path (…/output);
    override via KT_DATACARDS_URL_BASE / KT_DATACARDS_URL_BRANCH.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..utils import paths
from ..utils.state import StateIndex, StateManager
from . import tts_impl

logger = logging.getLogger(__name__)


def get_all_teams() -> list[str]:
    """Teams that have rendered card images (a prerequisite for a TTS box)."""
    if not paths.OUTPUT.exists():
        return []
    return sorted(
        d.name for d in paths.OUTPUT.iterdir()
        if d.is_dir() and (d / "cards").exists()
    )


def _inputs_for(team: str) -> list:
    """Every upstream asset the TTS box embeds: the team's rendered cards, box
    texture/mesh, tokens, dice, and stats, plus the config (guids/token defs) and
    the TTS Lua/mesh/image defaults. If none changed, the box is already current."""
    out = paths.team_output(team)
    inputs = [paths.TEAM_CONFIG, paths.CONFIG / "team-guids.json"]
    for sub in ("cards", "cardbox", "tokens", "dice", "data"):
        d = out / sub
        if d.exists():
            inputs.extend(sorted(p for p in d.rglob("*") if p.is_file()))
    for sub in ("tts-script", "tts-image", "tts-token"):
        d = paths.DEFAULTS / sub
        if d.exists():
            inputs.extend(sorted(p for p in d.rglob("*") if p.is_file()))
    return inputs


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No teams with rendered cards found (run generate_card_images first)")
        return {"processed": 0, "skipped": 0}

    branch = tts_impl.URL_BRANCH
    logger.info(f"generate_tts: {len(teams)} team(s) (url branch={branch})")

    # Input-hash gate: only (re)build boxes for teams whose upstream assets changed.
    pending: dict = {}
    skipped = 0
    for team in teams:
        state = StateManager(team)
        inputs = _inputs_for(team)
        if state.can_skip("generate_tts", inputs, force):
            logger.info(f"  [skip] {team} (unchanged)")
            skipped += 1
            continue
        pending[team] = (state, inputs)

    count = 0
    processed = 0
    if pending:
        # Flat URL list scanned from output/{team}/{cards,cardbox}.
        urls_data = tts_impl.generate_urls_json_v3(branch)
        logger.info(f"  scanned {len(urls_data)} card/asset entries")

        count = tts_impl.generate_all_tts_objects(
            urls_data,
            config_dir=paths.CONFIG,
            output_dir=paths.OUTPUT,
            team_filter=list(pending),
            repo_branch=branch,
        )

        for team, (state, inputs) in pending.items():
            tts_dir = paths.team_output(team) / "tts_objects"
            if not tts_dir.exists():
                continue
            box_files = list(tts_dir.glob("*.json"))
            if not box_files:
                continue
            processed += 1
            for f in sorted(box_files):
                state.record_output("generate_tts", f"tts_objects/{f.name}", f)
            state.record_inputs("generate_tts", inputs)
            state.mark_complete("generate_tts")
            state.save()

    # Finalization (runs across ALL output teams, not just the filtered set):
    # per-team {team}-object-urls.json + a global team-urls.json summary. These
    # drive the in-game update/lag check (each entry carries a content hash so
    # unchanged assets keep their prior url/modified stamp).
    _write_object_urls(branch)

    StateIndex().rebuild_and_save()
    logger.info(f"generate_tts done: processed={processed} skipped={skipped} (generated={count})")
    return {"processed": processed, "skipped": skipped}


def _write_object_urls(branch: str) -> None:
    """Generate per-team object-urls.json files + the global team-urls.json summary."""
    import json

    teams_data = tts_impl.generate_object_urls_json(branch)
    summary = tts_impl.generate_object_urls_summary(teams_data, branch)

    summary_file = paths.OUTPUT / "team-urls.json"
    with open(summary_file, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    logger.info(f"  wrote team-urls.json summary ({len(summary)} teams)")

    written = tts_impl.save_object_urls_team_files(teams_data, paths.OUTPUT)
    logger.info(f"  wrote {len(written)} team object-urls.json files")
