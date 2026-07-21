"""Integration — shared merge point. Copy + rename extracted PDFs into one folder.

layers/{track}/extracted + layers/{track}/structure/{team}-structure.json
   ->  layers/integration/{team}/{team}-{type}-{name}.pdf   (no -front/-back postfix)

Both tracks emit the IDENTICAL file set here. This is the dedup/merge point: run
whichever source GW updated and downstream is source-agnostic.

Uses the structure manifest to map each track's (differently named) extracted PDF
to its canonical classified filename. Each card becomes ONE classified PDF: a
front-only card is a 1-page PDF; a front+back card is a 2-page PDF (front, back).

When an entity has more than one physical card (e.g. a datacard whose actions are
on their own cards, or a multi-card faction rule), the card number is appended to
keep filenames unique: {team}-{type}-{name}-{card_number}.pdf.

SOURCE-DECISION: source only selects which track's structure/extracted to read.
OPEN: conflict policy when both tracks ran a team (currently last-run-wins —
files are simply overwritten).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from ..utils import naming, paths
from ..utils.stable_io import stable_write
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

# Type keys in deterministic order (matches build_structure output).
TYPE_KEYS = [
    "datacards",
    "equipment",
    "faction_rules",
    "token_guide",
    "firefight_ploys",
    "operatives_selection",
    "strategy_ploys",
]


def _merge_card(front: Path, back: Optional[Path], out_path: Path) -> None:
    """Write a classified PDF: front page first, optional back page second.

    The save is made deterministic (metadata cleared, no fresh random /ID) so a
    re-merge of unchanged source pages is byte-identical; combined with
    ``stable_write`` the file's mtime is preserved too, keeping re-runs free of
    spurious churn in this tracked layer.
    """
    doc = fitz.open(front)
    if back is not None:
        with fitz.open(back) as back_doc:
            doc.insert_pdf(back_doc)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({})
    with stable_write(out_path):
        doc.save(out_path, garbage=4, deflate=True, no_new_id=True)
    doc.close()


def _referenced_pdfs(structure: Dict) -> List[Path]:
    """Absolute paths of every extracted front/back PDF the structure references —
    the true source inputs for this team's integration."""
    refs: List[Path] = []
    for key in TYPE_KEYS:
        for entity in structure.get(key, []):
            for card in entity.get("cards", []):
                for rel in (card.get("front"), card.get("back")):
                    if rel:
                        refs.append(paths.ROOT / rel)
    return refs


def _integrate_team(team: str, structure: Dict) -> Dict:
    stats: Dict = {"written": 0, "missing": 0, "paths": []}
    team_dir = paths.integration_team_dir(team)
    team_dir.mkdir(parents=True, exist_ok=True)

    for key in TYPE_KEYS:
        entities = structure.get(key, [])
        card_type = naming.STRUCTURE_KEY_TO_TYPE.get(key, key)

        for entity in entities:
            name = entity.get("name") or "unknown"
            cards = entity.get("cards", [])
            multi = len(cards) > 1

            for card in cards:
                base = naming.classified_name(team, card_type, name)
                if multi:
                    base = f"{base}-{card['card_number']}"
                out_path = team_dir / f"{base}.pdf"

                front_rel = card.get("front")
                back_rel = card.get("back")
                if not front_rel:
                    logger.warning(f"  {base}: no front path, skipping")
                    stats["missing"] += 1
                    continue

                front = paths.ROOT / front_rel
                back = paths.ROOT / back_rel if back_rel else None
                if not front.exists():
                    logger.warning(f"  {base}: front missing on disk: {front}")
                    stats["missing"] += 1
                    continue
                if back is not None and not back.exists():
                    logger.warning(f"  {base}: back missing on disk: {back}")
                    back = None

                _merge_card(front, back, out_path)
                stats["written"] += 1
                stats["paths"].append(out_path)

    return stats


def run(teams=None, source=None, force=False):
    if source not in ("kt-app", "warcom"):
        raise SystemExit("integrate_classified requires --source kt-app|warcom")

    import json

    structure_dir = paths.structure_dir(source)
    if not structure_dir.exists():
        logger.error(f"No structure directory: {structure_dir}")
        return {"teams": 0, "written": 0}

    if teams:
        structure_files = [structure_dir / f"{t}-structure.json" for t in teams]
        structure_files = [f for f in structure_files if f.exists()]
    else:
        structure_files = sorted(structure_dir.glob("*-structure.json"))

    paths.INTEGRATION.mkdir(parents=True, exist_ok=True)

    totals = {"teams": 0, "written": 0, "missing": 0, "skipped": 0}
    for sf in structure_files:
        with open(sf, "r", encoding="utf-8") as f:
            structure = json.load(f)
        team = structure.get("team") or sf.stem.replace("-structure", "")

        state = StateManager(team)
        inputs = [sf] + _referenced_pdfs(structure)
        if state.can_skip("integrate_classified", inputs, force):
            logger.info(f"Integrating: {team} — unchanged, skip")
            totals["skipped"] += 1
            continue

        logger.info(f"Integrating: {team} (source={source})")
        stats = _integrate_team(team, structure)
        # Emit a source-agnostic manifest so downstream shared steps (content
        # analysis, etc.) can group entities without knowing which track ran.
        manifest_path = paths.integration_manifest_file(team)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(structure, mf, indent=2, ensure_ascii=False)
        logger.info(f"  wrote {stats['written']} classified PDFs (missing {stats['missing']})")

        state.record_output("integrate_classified", "manifest.json", manifest_path)
        for out_path in stats["paths"]:
            state.record_output("integrate_classified", out_path.name, out_path)
        state.record_inputs("integrate_classified", inputs)
        state.mark_complete("integrate_classified")
        state.save()

        totals["teams"] += 1
        totals["written"] += stats["written"]
        totals["missing"] += stats["missing"]

    StateIndex().rebuild_and_save()
    logger.info(
        f"integrate_classified done: teams={totals['teams']} "
        f"written={totals['written']} missing={totals['missing']} skipped={totals['skipped']}"
    )
    return totals
