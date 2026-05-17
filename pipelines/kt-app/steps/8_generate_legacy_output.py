"""
Step 8: Generate Legacy Output (output_v2 / tts_objects compatibility)

Copies card images and TTS assets from output/{team}/ to output_v2/{faction}/{team}/
using the legacy naming convention expected by old TTS boxes. Also rewrites embedded
URLs in the TTS object JSONs and writes them to tts_objects/{team}/ so old boxes
can continue to load without changes.

This step runs fully every time — no hash/timestamp incremental tracking.
Remove this step (and output_v2/, tts_objects/) once old TTS boxes are deprecated.

Input:
    output/{team}/cards/{card_type}/*.jpg
    output/{team}/cardbox/*.jpg, *.obj
    output/{team}/tokens/
    output/{team}/tts_objects/{Name} Box.json
    config/team-config.yaml

Output:
    output_v2/{faction}/{team}/{card_type}/*.jpg  (legacy naming)
    output_v2/{faction}/{team}/tts/               (box mesh, texture, tokens)
    output_v2/datacards-urls.json                 (flat array)
    output_v2/tts-card-boxes.json                 (team -> tts_objects URL index)
    tts_objects/{team}/{Name} Cards.json          (URL-rewritten TTS save file)
"""

import argparse
import json
import logging
import re
import shutil
import time
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"

# Maps new pipeline card type folder names -> legacy folder names used in output_v2
CARD_TYPE_MAP = {
    "datacards": "datacards",
    "faction_rules": "faction-rules",
    "firefight_ploys": "firefight-ploys",
    "operatives_selection": "operative-selection",
    "strategy_ploys": "strategy-ploys",
    "equipment": "equipment",
    "token_guide": "faction-rules",  # token guide merges into faction-rules in legacy
}

# Override the base filename stem for certain card types that use fixed legacy names
CARD_NAME_OVERRIDES = {
    "operatives_selection": "{team}-operatives",
    "token_guide": "{team}-markertoken-guide",
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_team_config() -> dict:
    config_path = PROJECT_ROOT / "config" / "team-config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get("teams", data)


def _legacy_filename(src_name: str, team: str, card_type: str) -> str:
    """
    Convert new-style filename to legacy filename.

    New format:  {name}-front.jpg / {name}-back.jpg
    Legacy:      {team}-{name}_front.jpg / {team}-{name}_back.jpg
                 (datacards have no team prefix in new format, others do)

    Some card types use a fixed legacy name regardless of the PDF-derived name.
    """
    stem, ext = src_name.rsplit('.', 1)

    if stem.endswith('-front'):
        side = '_front'
    elif stem.endswith('-back'):
        side = '_back'
    else:
        return src_name  # unrecognised pattern, keep as-is

    if card_type in CARD_NAME_OVERRIDES:
        base = CARD_NAME_OVERRIDES[card_type].format(team=team)
    else:
        base = stem[:-6] if side == '_front' else stem[:-5]
        if card_type == 'datacards' and not base.startswith(f"{team}-"):
            base = f"{team}-{base}"

    return f"{base}{side}.{ext}"


def copy_card_images(team: str, faction: str, ts: int) -> list:
    """Copy card images for one team; return list of datacards-urls entries."""
    entries = []
    cards_dir = PROJECT_ROOT / "output" / team / "cards"
    if not cards_dir.exists():
        return entries

    # Clear legacy card type dirs once before writing (multiple new types may share one)
    cleared_dirs: set = set()
    for new_type, legacy_type in CARD_TYPE_MAP.items():
        src_dir = cards_dir / new_type
        if not src_dir.exists():
            continue
        dst_dir = PROJECT_ROOT / "output_v2" / faction / team / legacy_type
        if dst_dir not in cleared_dirs:
            if dst_dir.exists():
                for f in dst_dir.iterdir():
                    if f.is_file():
                        f.unlink()
            dst_dir.mkdir(parents=True, exist_ok=True)
            cleared_dirs.add(dst_dir)

    for new_type, legacy_type in CARD_TYPE_MAP.items():
        src_dir = cards_dir / new_type
        if not src_dir.exists():
            continue

        dst_dir = PROJECT_ROOT / "output_v2" / faction / team / legacy_type
        dst_dir.mkdir(parents=True, exist_ok=True)

        for src_file in sorted(src_dir.iterdir()):
            if src_file.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
                continue

            legacy_name = _legacy_filename(src_file.name, team, new_type)
            shutil.copy2(src_file, dst_dir / legacy_name)

            name_no_ext = legacy_name.rsplit('.', 1)[0]
            rel = f"output_v2/{faction}/{team}/{legacy_type}/{legacy_name}"
            entries.append({
                "faction": faction,
                "team": team,
                "type": legacy_type,
                "name": name_no_ext,
                "url": f"{GITHUB_RAW_BASE}/{rel}?v={ts}",
            })

    return entries


def copy_tts_assets(team: str, faction: str, ts: int) -> list:
    """Copy box texture, mesh, icon and tokens to legacy tts/ folder."""
    entries = []
    tts_dst = PROJECT_ROOT / "output_v2" / faction / team / "tts"
    tts_dst.mkdir(parents=True, exist_ok=True)
    token_dst = tts_dst / "token"

    cardbox_dir = PROJECT_ROOT / "output" / team / "cardbox"

    # Box texture
    texture_src = cardbox_dir / f"{team}-card-box-texture.jpg"
    if texture_src.exists():
        shutil.copy2(texture_src, tts_dst / texture_src.name)
        rel = f"output_v2/{faction}/{team}/tts/{texture_src.name}"
        entries.append({
            "faction": faction, "team": team, "type": "tts",
            "name": f"{team}-card-box-texture",
            "url": f"{GITHUB_RAW_BASE}/{rel}?v={ts}",
        })

    # Box mesh (no cache-busting for obj)
    obj_src = cardbox_dir / f"{team}-card-box.obj"
    if obj_src.exists():
        shutil.copy2(obj_src, tts_dst / obj_src.name)
        rel = f"output_v2/{faction}/{team}/tts/{obj_src.name}"
        entries.append({
            "faction": faction, "team": team, "type": "tts",
            "name": f"{team}-card-box.obj",
            "url": f"{GITHUB_RAW_BASE}/{rel}",
        })

    # Team icon
    icon_src = PROJECT_ROOT / "config" / "teams" / team / "icon.png"
    if icon_src.exists():
        shutil.copy2(icon_src, tts_dst / f"{team}-icon.png")

    # Token bag mesh + icon (tokenbag/ -> tts/ root)
    tokenbag_dir = PROJECT_ROOT / "output" / team / "tokens" / "tokenbag"
    token_bag_obj = tokenbag_dir / f"{team}-token-bag.obj"
    if token_bag_obj.exists():
        shutil.copy2(token_bag_obj, tts_dst / token_bag_obj.name)
        rel = f"output_v2/{faction}/{team}/tts/{token_bag_obj.name}"
        entries.append({
            "faction": faction, "team": team, "type": "tts",
            "name": f"{team}-token-bag.obj",
            "url": f"{GITHUB_RAW_BASE}/{rel}",
        })
    token_bag_icon = tokenbag_dir / f"{team}-token-bag-icon.png"
    if token_bag_icon.exists():
        shutil.copy2(token_bag_icon, tts_dst / token_bag_icon.name)

    # Individual tokens (obj + png, skip tokenbag subdir and icon.png)
    tokens_dir = PROJECT_ROOT / "output" / team / "tokens"
    if tokens_dir.exists():
        token_files = [
            f for f in tokens_dir.iterdir()
            if f.is_file() and f.suffix.lower() in ('.obj', '.png')
            and f.name != f"{team}-icon.png"
        ]
        if token_files:
            token_dst.mkdir(parents=True, exist_ok=True)
            for f in sorted(token_files):
                shutil.copy2(f, token_dst / f.name)

    return entries


def _rewrite_urls(text: str, team: str, faction: str, ts: int) -> str:
    """
    Rewrite embedded GitHub raw URLs in a TTS JSON from new output/ paths to
    legacy output_v2/ paths. Also normalises the branch to 'main'.

    Handles:
      output/{team}/cards/{card_type}/{name}-{side}.jpg
        -> output_v2/{faction}/{team}/{legacy_type}/{team}-{name}_{side}.jpg
      output/{team}/cardbox/{team}-card-box-texture.jpg
        -> output_v2/{faction}/{team}/tts/{team}-card-box-texture.jpg
      output/{team}/cardbox/{team}-card-box.obj
        -> output_v2/{faction}/{team}/tts/{team}-card-box.obj
    """
    base_re = r'https://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+'

    def replace_card(m):
        ct, name, side = m.group(1), m.group(2), m.group(3)
        if ct not in CARD_TYPE_MAP:
            return m.group(0)  # no legacy equivalent, keep as-is
        legacy_type = CARD_TYPE_MAP[ct]
        if ct in CARD_NAME_OVERRIDES:
            name = CARD_NAME_OVERRIDES[ct].format(team=team)
        elif ct == 'datacards' and not name.startswith(f"{team}-"):
            name = f"{team}-{name}"
        return f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/{legacy_type}/{name}_{side}.jpg?v={ts}"

    # Card images
    text = re.sub(
        base_re + rf'/output/{re.escape(team)}/cards/(\w+)/([^"]+)-(front|back)\.jpg[^"]*',
        replace_card,
        text,
    )

    # Box texture
    text = re.sub(
        base_re + rf'/output/{re.escape(team)}/cardbox/({re.escape(team)}-card-box-texture\.jpg)[^"]*',
        lambda m: f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/{m.group(1)}?v={ts}",
        text,
    )

    # Box mesh (no cache-busting for obj)
    text = re.sub(
        base_re + rf'/output/{re.escape(team)}/cardbox/({re.escape(team)}-card-box\.obj)[^"]*',
        lambda m: f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/{m.group(1)}",
        text,
    )

    # Token bag (tokenbag/ subdir -> tts/ root)
    text = re.sub(
        base_re + rf'/output/{re.escape(team)}/tokens/tokenbag/([^"?]+)(\?[^"]*)?',
        lambda m: f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/{m.group(1)}?v={ts}"
        if m.group(1).endswith('.png') else
        f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/{m.group(1)}",
        text,
    )

    # Individual tokens (tokens/ root -> tts/token/)
    text = re.sub(
        base_re + rf'/output/{re.escape(team)}/tokens/([^/"]+)(\?[^"]*)?',
        lambda m: f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/token/{m.group(1)}?v={ts}"
        if m.group(1).endswith('.png') else
        f"{GITHUB_RAW_BASE}/output_v2/{faction}/{team}/tts/token/{m.group(1)}",
        text,
    )

    # Normalise any remaining branch references to main
    text = re.sub(
        r'https://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/',
        r'https://raw.githubusercontent.com/\1/main/',
        text,
    )

    return text


def write_tts_object(team: str, faction: str, canonical_name: str, ts: int) -> dict | None:
    """
    Read the new TTS box JSON, rewrite all embedded URLs to output_v2 paths,
    and write it to tts_objects/{team}/{Name} Cards.json (legacy location/naming).
    Returns a tts-card-boxes entry, or None if the source doesn't exist.
    """
    src = PROJECT_ROOT / "output" / team / "tts_objects" / f"{canonical_name} Box.json"
    if not src.exists():
        return None

    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()

    content = _rewrite_urls(content, team, faction, ts)

    dst_dir = PROJECT_ROOT / "tts_objects" / team
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_name = f"{canonical_name} Cards.json"
    with open(dst_dir / dst_name, 'w', encoding='utf-8') as f:
        f.write(content)

    encoded_name = dst_name.replace(' ', '%20')
    rel = f"tts_objects/{team}/{encoded_name}"
    return {
        "team": team,
        "name": canonical_name,
        "url": f"{GITHUB_RAW_BASE}/{rel}",
    }


def generate_legacy_output(teams: list, team_config: dict) -> int:
    """Run the legacy output generation for given teams. Returns count processed."""
    ts = int(time.time())
    all_entries = []
    card_box_entries = []
    processed = 0

    for team in teams:
        cfg = team_config.get(team, {})
        faction = cfg.get("faction", "")
        if not faction:
            logger.warning(f"  {team}: no faction in config, skipping")
            continue

        canonical_name = cfg.get("canonical_name", team.replace("-", " ").title())

        logger.info(f"Processing {team} ({faction})")

        card_entries = copy_card_images(team, faction, ts)
        tts_entries = copy_tts_assets(team, faction, ts)
        all_entries.extend(card_entries + tts_entries)

        box_entry = write_tts_object(team, faction, canonical_name, ts)
        if box_entry:
            card_box_entries.append(box_entry)

        if card_entries or tts_entries:
            processed += 1
            logger.info(f"  {len(card_entries)} card entries, {len(tts_entries)} tts entries, tts_object: {box_entry is not None}")
        else:
            logger.warning(f"  {team}: no output found in output/{team}/")

    # Rebuild datacards-urls.json
    urls_file = PROJECT_ROOT / "output_v2" / "datacards-urls.json"
    with open(urls_file, 'w', encoding='utf-8') as f:
        json.dump(all_entries, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(all_entries)} entries to {urls_file.relative_to(PROJECT_ROOT)}")

    # Rebuild tts-card-boxes.json
    boxes_file = PROJECT_ROOT / "output_v2" / "tts-card-boxes.json"
    with open(boxes_file, 'w', encoding='utf-8') as f:
        json.dump(card_box_entries, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote {len(card_box_entries)} entries to {boxes_file.relative_to(PROJECT_ROOT)}")

    return processed


def main():
    parser = argparse.ArgumentParser(description='Step 8: Generate legacy output_v2 files')
    parser.add_argument('--teams', help='Comma-separated list of team slugs (default: all)')
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Step 8: Generate Legacy Output (output_v2 compatibility)")
    logger.info("=" * 70)

    team_config = load_team_config()

    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    else:
        output_dir = PROJECT_ROOT / "output"
        teams = sorted([
            d.name for d in output_dir.iterdir()
            if d.is_dir() and (d / "cards").exists()
        ])

    logger.info(f"Teams to process: {len(teams)}")

    processed = generate_legacy_output(teams, team_config)

    logger.info("")
    logger.info("=" * 70)
    logger.info("Step 8 Complete!")
    logger.info(f"  Processed: {processed}/{len(teams)}")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
