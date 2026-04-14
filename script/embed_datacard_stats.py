"""
Embed operative stats (GMNotes + Lua) into existing TTS datacard objects.

For each team:
  1. Reads roster.json for stats/weapons
  2. Reads extraction_metadata.json for abilities (front-side OCR)  
  3. Reads the datacards PDF for back-side abilities (when front says "RULES CONTINUE")
  4. Patches every datacard in tts_objects/{team}/*.json with GMNotes + LuaScript

Usage:
    python script/embed_datacard_stats.py [--teams team1,team2] [--dry-run]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import yaml

ROOT = Path(__file__).resolve().parent.parent
LUA_SCRIPT_PATH = ROOT / "config" / "defaults" / "tts-script" / "datacard-load-stats.lua"
WEAPON_RULES_PATH = ROOT / "config" / "weapon_rules.json"
OUTPUT_DIR = ROOT / "output"
OUTPUT_V2_DIR = ROOT / "output_v2"
METADATA_DIR = ROOT / "metadata"
TTS_DIR = ROOT / "tts_objects"
PROCESSED_DIR = ROOT / "processed"
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


# ── Ability extraction from OCR / PDF ──

def _clean_ocr(s: str) -> str:
    s = re.sub(r"[\x07\x08]", "", s)
    s = s.replace("\u00e2\u20ac\u2122", "'").replace("â\u20ac\u2122", "'")
    return s.strip()


def _strip_stat_block_suffix(text: str) -> str:
    """Remove the operative stat block at the end of OCR text (keywords + name + numbers)."""
    # Pattern: OPERATIVE NAME\nN\nAPL\nWOUNDS\nSAVE\nMOVE... at end
    m = re.search(r"\n[A-Z][\w\s-]+\n\s*\d+\s*\nAPL\nWOUNDS", text)
    if m:
        return text[: m.start()].strip()
    # Inline pattern: TEAM_KEYWORD, ... OPERATIVE NAME N APL WOUNDS SAVE MOVE
    m = re.search(r"\d+\s+APL\s+WOUNDS\s+SAVE\s+MOVE", text)
    if m:
        # Go back to find the start of the keyword block  
        prefix = text[: m.start()]
        # Find last sentence ending before the keywords
        kw_start = prefix.rfind(". ")
        if kw_start > 0:
            return text[: kw_start + 1].strip()
        return prefix.strip()
    return text


def _extract_rules_from_front(full_text: str, known_rule_names: list[str]) -> str:
    """Extract ability/action text from front-side OCR, stripping weapon stats and keywords."""
    text = _clean_ocr(full_text)
    # Remove trailing "RULES CONTINUE ON OTHER SIDE"
    text = re.sub(r"\s*RULES CONTINUE ON OTHER SIDE\s*$", "", text, flags=re.IGNORECASE)
    # Strip keyword/stat block at end (inline format from extraction_metadata)
    # Find the last digit-stat pattern then the team keyword block
    # Generic: find "N APL WOUNDS SAVE MOVE" 
    m = re.search(r"\d+\s+APL\s+WOUNDS\s+SAVE\s+MOVE", text)
    if m:
        # Back up to find start of keyword section
        prefix = text[: m.start()]
        # Keywords usually start with TEAM_NAME comma-separated
        # Find the last occurrence of a comma-separated uppercase block
        kw = re.search(r"[A-Z][A-Z\s]+,\s*[A-Z]", prefix[max(0, len(prefix) - 200) :])
        if kw:
            cut = len(prefix) - 200 + kw.start() if len(prefix) > 200 else kw.start()
            text = text[:cut].strip()
        else:
            text = prefix.strip()

    # Find end of last weapon stat (ATK HIT DMG pattern)
    last_stat = 0
    for m in re.finditer(r"\d\s+\d\+\s+\d/\d", text):
        last_stat = m.end()
    if last_stat == 0:
        return ""
    remainder = text[last_stat:].strip()
    # Strip leading weapon rule names and dashes
    remainder = re.sub(r"^[\s\-]+", "", remainder)
    rule_pat = "|".join(re.escape(r) for r in known_rule_names)
    while True:
        m = re.match(
            r'^(?:Range\s+\d+"?|' + rule_pat + r")[\s,]*",
            remainder,
            re.IGNORECASE,
        )
        if m:
            remainder = remainder[m.end() :].strip()
        else:
            break
    remainder = re.sub(r"^\*\s*", "", remainder).strip()
    return remainder


def _extract_rules_from_backpage(page_text: str) -> str:
    """Extract ability/action text from a PDF back-side page."""
    text = _clean_ocr(page_text)
    # Normalize newlines to spaces for consistent parsing
    text = re.sub(r"\s*\n\s*", " ", text)
    text = _strip_stat_block_suffix(text)
    return text.strip()


def _parse_ability_entries(rules_text: str):
    """Parse abilities and actions from rules text."""
    if not rules_text:
        return [], []
    abilities = []
    actions = []
    entries = []
    # Actions: UPPERCASE WORDS (possibly hyphenated) NAP
    for m in re.finditer(r"([A-Z][A-Z\s\-]{2,}?)\s+(\d+AP)\b", rules_text):
        entries.append((m.start(), "action", m.group(1).strip().title(), m.group(2), m.end()))
    # Abilities: TitleCase Name:
    for m in re.finditer(r"([A-Z][a-z][\w\s'-]*?):\s", rules_text):
        entries.append((m.start(), "ability", m.group(1).strip(), None, m.end()))
    entries.sort(key=lambda e: e[0])
    for i, (start, etype, name, ap, text_start) in enumerate(entries):
        text_end = entries[i + 1][0] if i + 1 < len(entries) else len(rules_text)
        text = rules_text[text_start:text_end].strip()
        if etype == "action":
            actions.append({"name": f"{name} ({ap})", "text": text})
        else:
            abilities.append({"name": name, "text": text})
    return abilities, actions


def _find_backside_pages(pdf_path: Path) -> dict[str, str]:
    """Find back-side pages in a datacards PDF.
    
    Returns dict mapping operative slug to back-page text.
    Back pages don't start with 'NAME' and have an operative name in their stat block.
    """
    if fitz is None or not pdf_path.exists():
        return {}
    doc = fitz.open(str(pdf_path))
    backpages = {}
    for i in range(len(doc)):
        text = doc[i].get_text().strip()
        # Back pages don't start with 'NAME' (the header row of the stats table)
        if text.startswith("NAME"):
            continue
        # Must have a stat block to identify the operative
        name_match = re.search(r"([A-Z][\w\s'-]+?)\n\s*\d+\s*\nAPL\nWOUNDS", text)
        if not name_match:
            continue
        op_name = name_match.group(1).strip()
        slug = roster_slug(op_name)
        backpages[slug] = _clean_ocr(text)
    doc.close()
    return backpages


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


# ── Per-operative data builder ──

def build_operative_data(
    op: dict,
    all_rules: dict,
    abilities: list,
    actions: list,
) -> dict:
    stats = {
        "APL": op["apl"],
        "Move": parse_move(op["movement"]),
        "Save": parse_save(op["save"]),
        "Wounds": op["wounds"],
    }
    keywords = ["Operative"] + op["keywords"]
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
    display_name = op["name"].title()

    description = build_description(display_name, stats, keywords, weapons, abilities, actions)

    return {
        "name": display_name,
        "stats": stats,
        "keywords": keywords,
        "weapons": weapons,
        "abilities": abilities,
        "actions": actions,
        "weapon_rules": weapon_rules,
        "description": description,
    }


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
    
    # Read from old output location (where TTS currently uses)
    roster_path = OUTPUT_DIR / team / "statlines" / "roster.json"
    meta_path = METADATA_DIR / team / "extraction_metadata.json"
    pdf_path = PROCESSED_DIR / team / f"{team}-datacards.pdf"
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
    
    # Load metadata abilities (front-side)
    meta_abilities = {}
    known_rule_names = sorted(
        set(k.split()[0] for k in all_rules.keys()),
        key=len, reverse=True,
    )
    if meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            dc = meta.get("card_types", {}).get("datacards", {})
            for slug, card in dc.items():
                ft = card.get("extraction", {}).get("full_text", "")
                rules = _extract_rules_from_front(ft, known_rule_names)
                abilities, actions = _parse_ability_entries(rules)
                meta_abilities[slug] = {"abilities": abilities, "actions": actions}
        except (json.JSONDecodeError, KeyError) as e:
            log.warning("%s: failed to parse extraction_metadata.json: %s", team, e)
    
    # Load back-side abilities from PDF
    backpages = _find_backside_pages(pdf_path)
    for slug, back_text in backpages.items():
        rules = _extract_rules_from_backpage(back_text)
        back_abilities, back_actions = _parse_ability_entries(rules)
        if slug in meta_abilities:
            meta_abilities[slug]["abilities"].extend(back_abilities)
            meta_abilities[slug]["actions"].extend(back_actions)
        else:
            meta_abilities[slug] = {"abilities": back_abilities, "actions": back_actions}
    
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
            
            # Match card to metadata key (for abilities)
            meta_key = nickname  # direct match first
            if meta_key not in meta_abilities:
                prefix = team + "-"
                if nickname.startswith(prefix):
                    meta_key = nickname[len(prefix):]
            
            # Match card to roster operative (for stats/weapons)
            op = match_card_to_roster(nickname, team, roster_lookup)
            if op is None:
                log.debug("%s: no roster match for card '%s'", team, nickname)
                continue
            
            # Get abilities
            entry = meta_abilities.get(meta_key, {})
            abilities = entry.get("abilities", [])
            actions = entry.get("actions", [])
            
            # Build GMNotes data
            data = build_operative_data(op, all_rules, abilities, actions)
            gmnotes_json = json.dumps(data, separators=(",", ":"))
            
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
    if fitz is None:
        log.warning("PyMuPDF not installed — back-side abilities will be skipped")
    
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
