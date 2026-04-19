"""
Embed operative stats (GMNotes + Lua) into existing TTS datacard objects.

For each team:
  1. Reads roster.json (produced by extract_statlines.py) as sole data source
  2. Patches every datacard in tts_objects/{team}/*.json with GMNotes + LuaScript

Usage:
    python script/embed_datacard_stats.py [--teams team1,team2] [--dry-run]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
LUA_SCRIPT_PATH = ROOT / "config" / "defaults" / "tts-script" / "datacard-load-stats.lua"
WEAPON_RULES_PATH = ROOT / "config" / "weapon_rules.json"
OUTPUT_DIR = ROOT / "output"
TTS_DIR = ROOT / "tts_objects"
TEAM_CONFIG_PATH = ROOT / "config" / "team-config.yaml"

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── Team config helpers ──

def _load_team_config() -> dict:
    """Load team-config.yaml"""
    with open(TEAM_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_team_faction(team: str) -> str:
    """Get faction for a team from team-config.yaml"""
    config = _load_team_config()
    team_data = config.get("teams", {}).get(team, {})
    return team_data.get("faction", "xenos")  # default to xenos if not found


# ── Weapon type classification ──

_RANGED_RULES_PAT = re.compile(r"(range\s*\d|blast|torrent|silent)", re.IGNORECASE)
_RANGED_NAME_PAT = re.compile(
    r"(pistol|rifle|carbine|blaster|bolter|cannon|gun|launcher|"
    r"flamer|melta|plasma|las(?:cutter|gun|cannon)|auto|bolt|stubber|grenade|"
    r"needle|sniper|mortar|missile|photon|radium|phosphor|igniter|"
    r"scattergun|bow|fusil|jezzail|splinter|shuriken|starcannon|"
    r"deathspitter|strangler|devourer|fleshborer|spinefist)",
    re.IGNORECASE,
)
_MELEE_NAME_PAT = re.compile(
    r"(sword|blade|claw|fist|axe|hammer|mace|glaive|talons?|"
    r"pincer|pike|spear|staff|whip|maul|scythe|gauntlet|"
    r"bayonet|knife|dagger|spike|club|choppa|stave|fangs|"
    r"halberd|trident|sabre|falchion|cleaver|maw|beak|sabres|"
    r"claws|pincers|bonesword|lash|tendril|proboscis|crusher)",
    re.IGNORECASE,
)


def classify_weapon(weapon: dict) -> str:
    rules = weapon.get("special_rules", "")
    name = weapon.get("name", "")
    if _MELEE_NAME_PAT.search(name) and not _RANGED_RULES_PAT.search(rules):
        return "melee"
    if _RANGED_RULES_PAT.search(rules):
        return "ranged"
    if _RANGED_NAME_PAT.search(name):
        return "ranged"
    return "melee"


def tts_weapon_prefix(weapon: dict) -> str:
    if classify_weapon(weapon) == "melee":
        return "[F4641D]M[-]"
    return "[1E87FF]R[-]"


# ── Stat helpers ──

def parse_move(s: str) -> int:
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 6


def parse_save(s: str) -> int:
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 5


def match_weapon_rules(special_rules: str, all_rules: dict) -> dict:
    if not special_rules:
        return {}
    matched = {}
    for rule_name, desc in all_rules.items():
        base = rule_name.replace(" x", "").replace(" x+", "")
        if re.search(re.escape(base), special_rules, re.IGNORECASE):
            matched[rule_name] = desc
    return matched


# ── Roster ability helpers ──

# Unicode chars commonly found in Kill Team PDFs
_UNICODE_NORMALIZE = {
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK (T'au)
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u201c": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u2010": "-",   # HYPHEN
    "\u2011": "-",   # NON-BREAKING HYPHEN
    "\u2012": "-",   # FIGURE DASH
    "\u2013": "-",   # EN DASH
    "\u2014": "-",   # EM DASH
    "\u2033": '"',   # DOUBLE PRIME (inches)
    "\u2032": "'",   # PRIME
    "\u00e2": "a",   # â
    "\u00f4": "o",   # ô
}


def _normalize_text(s: str) -> str:
    """Strip control characters and normalize Unicode to ASCII equivalents."""
    s = re.sub(r"[\x07\x08]", "", s)
    for uchar, replacement in _UNICODE_NORMALIZE.items():
        s = s.replace(uchar, replacement)
    return s.strip()


def _abilities_from_roster(op: dict) -> tuple[list, list]:
    """Extract abilities and actions from a roster operative entry."""
    abilities = []
    actions = []
    for pa in op.get("passive_abilities", []):
        name = _normalize_text(pa.get("name", ""))
        text = _normalize_text(pa.get("description", ""))
        if name:
            abilities.append({"name": name, "text": text})
    for ua in op.get("unique_actions", []):
        name = _normalize_text(ua.get("name", ""))
        text = _normalize_text(ua.get("description", ""))
        if name:
            actions.append({"name": name, "text": text})
    return abilities, actions


# ── TTS Description builder ──

def build_description(name: str, stats: dict, keywords: list,
                      weapons: list, abilities: list, actions: list) -> str:
    lines = []
    lines.append(
        f'[D36B3E]'
        f'[[84E680]APL[-] [ffffff]{stats["APL"]}[-]] '
        f'[[84E680]MOVE[-] [ffffff]{stats["Move"]}"[-]]'
    )
    lines.append(
        f'[[84E680]SAVE[-] [ffffff]{stats["Save"]}+[-]] '
        f'[[84E680]WOUNDS[-] [ffffff]{stats["Wounds"]}[-]][-]'
    )
    lines.append(f'[C5C5C5]{", ".join(keywords)}[-]')
    lines.append("[31B32B]Weapons[-]")
    for w in weapons:
        s = w["stats"]
        lines.append(f'{w["name"]}')
        lines.append(
            f'[84E680]ATK[-] {s["ATK"]} '
            f'[84E680]HIT[-] {s["HIT"]} '
            f'[84E680]DMG[-] {s["DMG"]}'
        )
        wr = s.get("WR", "")
        if wr:
            lines.append(f"[84E680]WR[-]: {wr}")
        lines.append("")
    if abilities:
        lines.append("---")
        lines.append("[31B32B]Abilities[-]")
        for ab in abilities:
            lines.append(f'- [EF8450]{ab["name"]}[-]')
    if actions:
        lines.append("[31B32B]Actions[-]")
        for ac in actions:
            lines.append(f'- [D46D6C]{ac["name"]}[-]')
    return "\n".join(lines)


def _build_selection_for_gmnotes(
    selection_groups: list[list[str]], weapons: list[dict]
) -> dict | None:
    """Transform selection groups into indexed format for TTS GMNotes.

    Returns {"groups": [[{"label": str, "weapons": [int]}]], "fixed": [int]}
    where weapon indices are 0-based into the weapons list.
    """
    if not selection_groups or not weapons:
        return None

    weapon_names_lower = [(w.get("plain_name") or w.get("name", "")).lower() for w in weapons]
    all_matched: set[int] = set()
    result_groups = []

    for group in selection_groups:
        group_options = []
        for option_label in group:
            # Split "; " combos into individual weapon fragments
            fragments = [f.strip().lower() for f in option_label.split(";")]
            matched: set[int] = set()
            for frag in fragments:
                # Handle "X or Y" alternatives within a fragment
                sub_frags = [sf.strip() for sf in frag.split(" or ")]
                for sf in sub_frags:
                    for i, wname in enumerate(weapon_names_lower):
                        if wname.startswith(sf):
                            matched.add(i)
            all_matched.update(matched)
            group_options.append({"label": option_label, "weapons": sorted(matched)})
        result_groups.append(group_options)

    # Weapons not covered by any option are always included
    fixed = [i for i in range(len(weapons)) if i not in all_matched]

    return {"groups": result_groups, "fixed": fixed}


# ── Per-operative data builder ──

def build_operative_data(
    op: dict,
    all_rules: dict,
    abilities: list,
    actions: list,
    selection: list | None = None,
) -> dict:
    stats = {
        "APL": op["apl"],
        "Move": parse_move(op["movement"]),
        "Save": parse_save(op["save"]),
        "Wounds": op["wounds"],
    }
    keywords = ["Operative"] + [_normalize_text(k) for k in op["keywords"]]
    weapons = []
    weapon_rules = {}
    for w in op["weapons"]:
        wr_text = w.get("special_rules", "")
        prefix = tts_weapon_prefix(w)
        weapons.append({
            "name": f'{prefix} {w["name"]}',
            "plain_name": w["name"],
            "stats": {
                "ATK": w["attacks"],
                "HIT": w["hit"],
                "DMG": w["damage"],
                "WR": wr_text,
            },
        })
        matched = match_weapon_rules(wr_text, all_rules)
        weapon_rules.update(matched)

    # Operative display name: strip team prefix from roster name
    # e.g. "KROOT KILL-BROKER" -> take last meaningful parts
    name_parts = op["name"].split()
    # The card nickname already has the right name, but we need a display name
    # Use title-case of the full name
    display_name = _normalize_text(op["name"].title())

    description = build_description(display_name, stats, keywords, weapons, abilities, actions)

    result = {
        "name": display_name,
        "stats": stats,
        "keywords": keywords,
        "weapons": weapons,
        "abilities": abilities,
        "actions": actions,
        "weapon_rules": weapon_rules,
        "description": description,
    }
    if selection:
        indexed = _build_selection_for_gmnotes(selection, weapons)
        if indexed:
            result["selection"] = indexed
    return result


# ── Roster slug to card nickname matching ──

def roster_slug(op_name: str) -> str:
    """Slugify an operative name, stripping non-ASCII chars to match TTS card nicknames."""
    s = op_name.lower().replace(" ", "-")
    # Strip all non-ASCII chars (ô, â, ', ‑, etc.) to match card nickname generation
    s = re.sub(r"[^\x00-\x7f]", "", s)
    return s


def build_roster_lookup(roster: dict) -> dict[str, dict]:
    """Build a lookup from slug to operative data."""
    result = {}
    for op in roster["operatives"]:
        slug = roster_slug(op["name"])
        result[slug] = op
    return result


def match_card_to_roster(card_nickname: str, team: str, roster_lookup: dict) -> dict | None:
    """Match a TTS card nickname to a roster operative.
    
    Card nicknames are like: team-operative-slug (e.g. farstalker-kinband-kroot-stalker)
    Roster slugs are like: kroot-stalker (operative name slugified)
    """
    # Try: card_nickname == roster_slug (kasrkin case)
    if card_nickname in roster_lookup:
        return roster_lookup[card_nickname]
    # Try: strip team prefix
    prefix = team + "-"
    if card_nickname.startswith(prefix):
        suffix = card_nickname[len(prefix):]
        if suffix in roster_lookup:
            return roster_lookup[suffix]
    # Fuzzy: check if any roster slug is a suffix of card nickname
    for slug, op in roster_lookup.items():
        if card_nickname.endswith("-" + slug) or card_nickname.endswith(slug):
            return op
    return None


# ── Main patching logic ──

def find_datacards_in_tts(tts_data: dict) -> list[dict]:
    """Find all datacard objects in a TTS save, traversing decks and bags."""
    datacards = []
    
    def recurse(obj):
        tags = obj.get("Tags", [])
        nickname = obj.get("Nickname", "")
        name = obj.get("Name", "")
        
        if name == "Deck" and nickname == "Datacards":
            for card in obj.get("ContainedObjects", []):
                datacards.append(card)
        elif name == "Card" and any("KTCardsDatacard" in t for t in tags):
            datacards.append(obj)
        
        # Recurse into contained objects (bags, etc.)
        for child in obj.get("ContainedObjects", []):
            recurse(child)
    
    for obj in tts_data.get("ObjectStates", []):
        recurse(obj)
    
    return datacards


def patch_team(
    team: str,
    all_rules: dict,
    lua_script: str,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Patch all datacards for a team. Returns (patched_count, total_count)."""
    
    roster_path = OUTPUT_DIR / team / "statlines" / "roster.json"
    tts_team_dir = TTS_DIR / team
    
    if not roster_path.exists():
        log.warning("%s: no roster.json, skipping", team)
        return 0, 0
    if not tts_team_dir.exists():
        log.warning("%s: no tts_objects dir, skipping", team)
        return 0, 0
    
    # Load roster
    with open(roster_path, "r", encoding="utf-8") as f:
        roster = json.load(f)
    roster_lookup = build_roster_lookup(roster)
    selection_lookup = roster.get("selection", {})
    
    # Find TTS card box JSON files
    tts_files = list(tts_team_dir.glob("*.json"))
    
    total_patched = 0
    total_cards = 0
    
    for tts_file in tts_files:
        with open(tts_file, "r", encoding="utf-8") as f:
            tts_data = json.load(f)
        
        datacards = find_datacards_in_tts(tts_data)
        if not datacards:
            continue
        
        modified = False
        for card in datacards:
            nickname = card.get("Nickname", "")
            total_cards += 1
            
            # Match card to roster operative
            op = match_card_to_roster(nickname, team, roster_lookup)
            if op is None:
                log.debug("%s: no roster match for card '%s'", team, nickname)
                continue
            
            # Get abilities from roster
            abilities, actions = _abilities_from_roster(op)
            
            # Build GMNotes data
            op_selection = selection_lookup.get(op["name"], [])
            data = build_operative_data(op, all_rules, abilities, actions, op_selection)
            gmnotes_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
            # Normalize any remaining Unicode chars (from weapon names, WR text, etc.)
            for uchar, replacement in _UNICODE_NORMALIZE.items():
                gmnotes_json = gmnotes_json.replace(uchar, replacement)
            
            card["GMNotes"] = gmnotes_json
            card["LuaScript"] = lua_script
            modified = True
            total_patched += 1
        
        if modified and not dry_run:
            with open(tts_file, "w", encoding="utf-8") as f:
                json.dump(tts_data, f, indent=2, ensure_ascii=False)
            log.info("%s: patched %s", team, tts_file.name)
    
    return total_patched, total_cards


def discover_teams() -> list[str]:
    """Discover all teams that have both roster.json and tts_objects."""
    teams = []
    if not OUTPUT_DIR.exists():
        return teams
    
    # Scan team folders directly (old structure)
    for team_dir in sorted(OUTPUT_DIR.iterdir()):
        if not team_dir.is_dir():
            continue
        team = team_dir.name
        if (team_dir / "statlines" / "roster.json").exists() and (TTS_DIR / team).exists():
            teams.append(team)
    
    return teams


def main():
    parser = argparse.ArgumentParser(description="Embed stats into TTS datacards")
    parser.add_argument("--teams", help="Comma-separated team list (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = parser.parse_args()
    
    # Load shared resources
    with open(WEAPON_RULES_PATH, "r", encoding="utf-8") as f:
        all_rules = json.load(f)
    lua_script = LUA_SCRIPT_PATH.read_text(encoding="utf-8")
    
    if args.teams:
        teams = [t.strip() for t in args.teams.split(",")]
    else:
        teams = discover_teams()
    
    log.info("Teams to process: %d", len(teams))
    
    total_patched = 0
    total_cards = 0
    teams_ok = 0
    
    for team in teams:
        patched, cards = patch_team(team, all_rules, lua_script, dry_run=args.dry_run)
        if cards > 0:
            log.info(
                "  %-35s %2d/%2d cards patched",
                team, patched, cards,
            )
            teams_ok += 1
        total_patched += patched
        total_cards += cards
    
    mode = " (DRY RUN)" if args.dry_run else ""
    log.info("")
    log.info("Done%s: %d/%d cards patched across %d teams", mode, total_patched, total_cards, teams_ok)


if __name__ == "__main__":
    main()
