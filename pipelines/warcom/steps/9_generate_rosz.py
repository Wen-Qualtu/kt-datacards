"""
Step 9: Generate .rosz (BattleScribe XML) from roster.json

Reads the statline data produced by step 6 and generates a .rosz file
(ZIP containing a .ros BattleScribe XML file) that can be imported into
TTS Command Node, New Recruit, or other BattleScribe-compatible tools.

Input:  output/{team}/statlines/roster.json
        config/weapon_rules.json (rule descriptions)
        config/team-config.yaml (canonical names, faction)
        config/team-guids.json (deterministic team GUIDs)
Output: output/{team}/{team}.rosz

Usage:
    python pipelines/warcom/steps/9_generate_rosz.py --team battleclade
    python pipelines/warcom/steps/9_generate_rosz.py              # all teams
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import yaml

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# Constants — BattleScribe type IDs (from reference .ros files)
# ============================================================================

GAME_SYSTEM_ID = "c521-ad27-44df-f959"
GAME_SYSTEM_NAME = "Warhammer 40,000: Kill Team (2024)"
GAME_SYSTEM_REV = "9"
BS_VERSION = "2.03"
GENERATED_BY = "kt-datacards"

# Profile typeIds
TYPE_OPERATIVE = "5156-3fb9-39ce-7bdb"
TYPE_ABILITIES = "f887-5881-0e6d-755c"
TYPE_UNIQUE_ACTIONS = "8f2a-d3d6-1a0c-7fa3"
TYPE_WEAPONS = "f25f-4b13-b724-d5a8"

# Characteristic typeIds for Operative
CHAR_APL = "bc83-42aa-b7c1-f0b1"
CHAR_MOVE = "c996-ffb3-e0b4-ecfa"
CHAR_SAVE = "3241-5548-12d6-f103"
CHAR_WOUNDS = "74f9-f91c-b8fd-89d9"

# Characteristic typeIds for Weapons
CHAR_ATK = "6056-b741-7cf3-5b43"
CHAR_HIT = "8044-2517-4ef7-33de"
CHAR_DMG = "dd3e-ef09-5d1a-37b4"
CHAR_WR = "05b8-00a1-69af-14b6"

# Characteristic typeIds for Abilities / Unique Actions
CHAR_ABILITY = "3467-0678-083e-eb50"
CHAR_UA = "ba93-e32d-f1ac-e188"

# Well-known category IDs
CAT_LEADER = "d999-8cad-8145-4efe"
CAT_OPERATIVE = "cf83-4496-b58e-ac82"
CAT_CONFIG = "874b-0390-e5e2-1daa"
CAT_REFERENCE = "b318-a8d7-2d38-99a3"

NS = "http://www.battlescribe.net/schema/rosterSchema"


# ============================================================================
# ID Generation — deterministic, short, hex-based
# ============================================================================

def _make_id(seed: str) -> str:
    """Generate a deterministic short ID from a seed string."""
    h = hashlib.md5(seed.encode('utf-8')).hexdigest()
    return f"{h[:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"


def _make_short_id(seed: str) -> str:
    """Generate a short alphanumeric ID for selection-level elements."""
    h = hashlib.md5(seed.encode('utf-8')).hexdigest()
    return h[:7]


# ============================================================================
# Weapon Type Detection
# ============================================================================

# Known ranged weapon indicators in special_rules
_RANGED_PATTERNS = [
    re.compile(r'Range \d', re.IGNORECASE),
    re.compile(r'Blast \d', re.IGNORECASE),
    re.compile(r'Torrent \d', re.IGNORECASE),
    re.compile(r'Silent', re.IGNORECASE),
    re.compile(r'Saturate', re.IGNORECASE),
    re.compile(r'Seek', re.IGNORECASE),
    re.compile(r'Heavy', re.IGNORECASE),
]

# Known ranged weapon name patterns
_RANGED_NAME_PATTERNS = re.compile(
    r'(pistol|rifle|carbine|blaster|bolter|cannon|gun|launcher|'
    r'flamer|melta|plasma|las(?:cutter|gun|cannon)|auto|bolt|stubber|grenade|'
    r'needle|sniper|mortar|missile|photon|radium|phosphor|igniter)',
    re.IGNORECASE,
)

# Known melee weapon name patterns (takes priority over ranged heuristics)
_MELEE_NAME_PATTERNS = re.compile(
    r'(sword|blade|claw|fist|axe|hammer|mace|glaive|talons?|'
    r'pincer|pike|spear|staff|whip|maul|scythe|gauntlet|'
    r'bayonet|knife|dagger|spike|club|choppa|stave)',
    re.IGNORECASE,
)


def classify_weapon_type(weapon: Dict) -> str:
    """Classify a weapon as 'melee' or 'ranged'.

    Checks melee name patterns first (priority), then ranged indicators
    in special_rules, then ranged name patterns.
    """
    rules = weapon.get('special_rules', '')
    name = weapon.get('name', '')

    # Melee name takes priority — a "pincer & lascutter" is melee
    if _MELEE_NAME_PATTERNS.search(name) and not _RANGED_PATTERNS[0].search(rules):
        return 'melee'

    for pat in _RANGED_PATTERNS:
        if pat.search(rules):
            return 'ranged'

    if _RANGED_NAME_PATTERNS.search(name):
        return 'ranged'

    return 'melee'


# ============================================================================
# Rule Parsing
# ============================================================================

def parse_weapon_rules(special_rules: str) -> List[str]:
    """Parse comma-separated weapon rules, respecting quoted distances.

    E.g. 'Range 8", Devastating 3, Lethal 5+' -> ['Range 8"', 'Devastating 3', 'Lethal 5+']
    Also handles: '1" Devastating 3' as part of the previous token.
    """
    if not special_rules or not special_rules.strip():
        return []

    # Normalize curly quotes
    text = special_rules.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2033', '"').replace('\u2032', "'")

    rules = []
    current = ''
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue

        # If part starts with a distance like '1"' and current is empty,
        # it might be a distance prefix for the previous rule
        if current:
            current += ', ' + part
        else:
            current = part

        # A rule token is complete if it doesn't end mid-quote
        # Simple heuristic: count quotes
        if current.count('"') % 2 == 0 or current.endswith('"'):
            rules.append(current.strip())
            current = ''

    if current:
        rules.append(current.strip())

    return rules


def match_rule_description(rule_name: str, weapon_rules_db: Dict[str, str]) -> Optional[str]:
    """Look up a rule's full description from the weapon_rules.json database.

    Handles parameterized rules like 'Devastating 3' -> 'Devastating x',
    'Lethal 5+' -> 'Lethal x+', 'Range 8"' -> 'Range x', etc.
    """
    # Direct match
    if rule_name in weapon_rules_db:
        return weapon_rules_db[rule_name]

    # Normalize: strip parameters to find the base rule
    # E.g. "Devastating 3" -> "Devastating x"
    # E.g. "Lethal 5+" -> "Lethal x+"
    # E.g. "Range 8\"" -> "Range x"
    # E.g. "Piercing Crits 1" -> "Piercing x" (close enough)
    # E.g. "Blast 2\"" -> "Blast x"

    normalized = re.sub(r'\d+[\+]?"?$', 'x', rule_name.strip().rstrip('"'))
    if not normalized.endswith('x'):
        normalized = re.sub(r'\d+"?', 'x', normalized)

    for db_key, desc in weapon_rules_db.items():
        # Try exact normalized match
        if normalized.lower() == db_key.lower():
            return desc
        # Try base word match
        base = rule_name.split()[0] if ' ' in rule_name else rule_name
        db_base = db_key.split()[0] if ' ' in db_key else db_key
        if base.lower() == db_base.lower():
            return desc

    return None


# ============================================================================
# XML Building
# ============================================================================

def _esc(text: str) -> str:
    """Escape text for use in both XML attributes and element content.

    Handles &, <, >, and " (double quotes for safe use in attr values).
    """
    return escape(str(text), {'"': '&quot;'})

def _normalize_move(move: str) -> str:
    """Normalize movement value to standard format with proper quote mark."""
    # Remove any existing quote-like chars and re-add proper one
    move = move.strip()
    move = move.rstrip('″"\'`')
    # Extract just the number
    m = re.search(r'(\d+)', move)
    if m:
        return f'{m.group(1)}&quot;'
    return _esc(move)


def _format_damage(damage: str) -> str:
    """Format damage string (already in normal/crit format)."""
    return _esc(damage)


def _build_characteristics(chars: List[Tuple[str, str, str]]) -> str:
    """Build <characteristics> XML block.

    Args:
        chars: List of (name, typeId, value) tuples
    """
    lines = ['<characteristics>']
    for name, type_id, value in chars:
        lines.append(
            f'<characteristic name="{_esc(name)}" '
            f'typeId="{type_id}">{value}</characteristic>'
        )
    lines.append('</characteristics>')
    return ''.join(lines)


def build_operative_profile(op: Dict, team_seed: str) -> str:
    """Build the <profile typeName="Operative"> element for stat line."""
    name = op['name'].title()
    pid = _make_id(f"{team_seed}:op:{name}")

    move_val = _normalize_move(str(op.get('movement', op.get('move', '6"'))))
    save_val = _esc(str(op.get('save', '4+')))
    wounds_val = str(op.get('wounds', 8))
    apl_val = str(op.get('apl', 2))

    chars = _build_characteristics([
        ("APL", CHAR_APL, apl_val),
        ("Move", CHAR_MOVE, move_val),
        ("Save", CHAR_SAVE, save_val),
        ("Wounds", CHAR_WOUNDS, wounds_val),
    ])

    return (
        f'<profile id="{pid}" name="{_esc(name)}" hidden="false" '
        f'typeId="{TYPE_OPERATIVE}" typeName="Operative" from="entry">'
        f'{chars}</profile>'
    )


def build_ability_profiles(op: Dict, team_seed: str) -> str:
    """Build <profile typeName="Abilities"> elements."""
    parts = []
    for i, ability in enumerate(op.get('passive_abilities', [])):
        aname = ability if isinstance(ability, str) else ability.get('name', f'Ability {i+1}')
        adesc = '' if isinstance(ability, str) else ability.get('description', '')
        pid = _make_id(f"{team_seed}:ab:{op['name']}:{aname}")

        chars = _build_characteristics([("Ability", CHAR_ABILITY, _esc(adesc))])
        parts.append(
            f'<profile id="{pid}" name="{_esc(aname)}" hidden="false" '
            f'typeId="{TYPE_ABILITIES}" typeName="Abilities" from="entry">'
            f'{chars}</profile>'
        )
    return ''.join(parts)


def build_ua_profiles(op: Dict, team_seed: str) -> str:
    """Build <profile typeName="Unique Actions"> elements."""
    parts = []
    for i, ua in enumerate(op.get('unique_actions', [])):
        uname = ua if isinstance(ua, str) else ua.get('name', f'Action {i+1}')
        udesc = '' if isinstance(ua, str) else ua.get('description', '')
        pid = _make_id(f"{team_seed}:ua:{op['name']}:{uname}")

        chars = _build_characteristics([("Unique Action", CHAR_UA, _esc(udesc))])
        parts.append(
            f'<profile id="{pid}" name="{_esc(uname)}" hidden="false" '
            f'typeId="{TYPE_UNIQUE_ACTIONS}" typeName="Unique Actions" from="entry">'
            f'{chars}</profile>'
        )
    return ''.join(parts)


def build_weapon_selection(
    weapon: Dict,
    weapon_type: str,
    team_seed: str,
    op_name: str,
    weapon_rules_db: Dict[str, str],
) -> str:
    """Build a <selection type="upgrade"> element for one weapon."""
    wname = weapon['name']
    prefix = '⚔' if weapon_type == 'melee' else '⌖'
    group = 'Melee weapon' if weapon_type == 'melee' else 'Ranged weapon'
    sid = _make_short_id(f"{team_seed}:wpn:{op_name}:{wname}")
    eid = _make_id(f"{team_seed}:wpn-entry:{op_name}:{wname}")
    gid = _make_id(f"{team_seed}:wpn-group:{op_name}:{weapon_type}")

    # Parse weapon rules and build <rules> elements
    raw_rules = weapon.get('special_rules', '')
    parsed_rules = parse_weapon_rules(raw_rules)
    wr_display = ', '.join(parsed_rules) if parsed_rules else '-'

    rules_xml = ''
    if parsed_rules:
        rule_parts = []
        for rule_text in parsed_rules:
            desc = match_rule_description(rule_text, weapon_rules_db)
            if desc:
                rid = _make_id(f"{team_seed}:rule:{rule_text}")
                # Strip parameterized name for display
                base_name = rule_text
                rule_parts.append(
                    f'<rule id="{rid}" name="{_esc(base_name)}" hidden="false">'
                    f'<description>{_esc(desc)}</description></rule>'
                )
        if rule_parts:
            rules_xml = '<rules>' + ''.join(rule_parts) + '</rules>'

    # Build weapon profile
    profile_name = f"{prefix} {wname}"
    pid = _make_id(f"{team_seed}:wpn-prof:{op_name}:{wname}")

    chars = _build_characteristics([
        ("ATK", CHAR_ATK, _esc(str(weapon.get('attacks', '4')))),
        ("HIT", CHAR_HIT, _esc(str(weapon.get('hit', '4+')))),
        ("DMG", CHAR_DMG, _format_damage(str(weapon.get('damage', '3/4')))),
        ("WR", CHAR_WR, _esc(wr_display)),
    ])

    return (
        f'<selection id="{sid}" name="{_esc(wname)}" '
        f'entryId="{eid}" entryGroupId="{gid}" '
        f'number="1" type="upgrade" from="group" group="{_esc(group)}">'
        f'{rules_xml}'
        f'<profiles>'
        f'<profile id="{pid}" name="{_esc(profile_name)}" hidden="false" '
        f'typeId="{TYPE_WEAPONS}" typeName="Weapons" from="entry">'
        f'{chars}</profile>'
        f'</profiles>'
        f'</selection>'
    )


def build_categories(op: Dict, team_seed: str, canonical_team: str) -> str:
    """Build <categories> for an operative from its keywords."""
    keywords = op.get('keywords', [])
    parts = []

    for kw in keywords:
        kw_title = kw.strip().title() if kw.isupper() else kw.strip()
        cid = _make_id(f"cat:{kw_title}")
        is_leader = kw.upper() == 'LEADER'
        primary = 'true' if is_leader else 'false'
        entry_id = CAT_LEADER if is_leader else cid
        parts.append(
            f'<category id="{cid}" name="{_esc(kw_title)}" '
            f'entryId="{entry_id}" primary="{primary}" />'
        )

    # If no LEADER keyword, add Operative as primary
    if not any(k.upper() == 'LEADER' for k in keywords):
        parts.append(
            f'<category id="{_make_id("cat:Operative")}" name="Operative" '
            f'entryId="{CAT_OPERATIVE}" primary="true" />'
        )

    return '<categories>' + ''.join(parts) + '</categories>'


def build_operative(
    op: Dict,
    team_seed: str,
    canonical_team: str,
    weapon_rules_db: Dict[str, str],
) -> str:
    """Build a complete <selection type="model"> for one operative."""
    name = op['name'].title()
    sid = _make_short_id(f"{team_seed}:sel:{name}")
    eid = _make_id(f"{team_seed}:entry:{name}")

    # Profiles: stats + abilities + unique actions
    profiles = '<profiles>'
    profiles += build_operative_profile(op, team_seed)
    profiles += build_ability_profiles(op, team_seed)
    profiles += build_ua_profiles(op, team_seed)
    profiles += '</profiles>'

    # Weapons
    weapons = op.get('weapons', [])
    weapon_selections = ''
    if weapons:
        weapon_parts = []
        for w in weapons:
            wtype = classify_weapon_type(w)
            weapon_parts.append(
                build_weapon_selection(w, wtype, team_seed, op['name'], weapon_rules_db)
            )
        weapon_selections = '<selections>' + ''.join(weapon_parts) + '</selections>'

    # Categories
    categories = build_categories(op, team_seed, canonical_team)

    return (
        f'<selection id="{sid}" name="{_esc(name)}" '
        f'entryId="{eid}" number="1" type="model" from="entry">'
        f'{profiles}'
        f'{weapon_selections}'
        f'{categories}'
        f'</selection>'
    )


def build_roster_xml(
    roster: Dict,
    team_config: Dict,
    team_guid: str,
    weapon_rules_db: Dict[str, str],
) -> str:
    """Build the complete .ros XML string."""
    team_name = roster.get('team', 'Unknown')
    canonical = team_config.get('canonical_name', team_name.replace('-', ' ').title())
    team_seed = team_guid or team_name

    roster_id = _make_short_id(f"roster:{team_seed}")
    force_id = _make_short_id(f"force:{team_seed}")
    cat_id = _make_id(f"catalogue:{team_seed}")

    # Build operatives
    op_parts = []
    for op in roster.get('operatives', []):
        op_parts.append(build_operative(op, team_seed, canonical, weapon_rules_db))

    selections_xml = '<selections>' + ''.join(op_parts) + '</selections>'

    # Force-level categories
    force_cats = (
        '<categories>'
        f'<category name="Configuration" id="{_make_short_id(f"fcat:config:{team_seed}")}" '
        f'primary="false" entryId="{CAT_CONFIG}" />'
        f'<category name="Reference" id="{_make_short_id(f"fcat:ref:{team_seed}")}" '
        f'primary="false" entryId="{CAT_REFERENCE}" />'
        f'<category name="Leader" id="{_make_short_id(f"fcat:leader:{team_seed}")}" '
        f'primary="false" entryId="{CAT_LEADER}" />'
        f'<category name="Operative" id="{_make_short_id(f"fcat:op:{team_seed}")}" '
        f'primary="false" entryId="{CAT_OPERATIVE}" />'
        '</categories>'
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<roster id="{roster_id}" name="{_esc(canonical)}" '
        f'battleScribeVersion="{BS_VERSION}" '
        f'generatedBy="{GENERATED_BY}" '
        f'gameSystemId="{GAME_SYSTEM_ID}" '
        f'gameSystemName="{_esc(GAME_SYSTEM_NAME)}" '
        f'gameSystemRevision="{GAME_SYSTEM_REV}" '
        f'xmlns="{NS}">'
        f'<forces>'
        f'<force id="{force_id}" name="Kill Team" '
        f'entryId="b9c3-f06a-4cfe-483c" '
        f'catalogueId="{cat_id}" catalogueRevision="1" '
        f'catalogueName="{_esc(canonical)}">'
        f'{selections_xml}'
        f'{force_cats}'
        f'</force>'
        f'</forces>'
        f'</roster>'
    )

    return xml


# ============================================================================
# File Output
# ============================================================================

def write_rosz(xml_content: str, output_path: Path) -> None:
    """Write a .rosz file (ZIP containing the .ros XML)."""
    ros_name = output_path.stem + '.ros'

    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(ros_name, xml_content)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buf.getvalue())


# ============================================================================
# Main
# ============================================================================

def process_team(team_name: str, base_dir: Path, force: bool = False) -> bool:
    """Generate .rosz for a single team."""
    roster_path = base_dir / 'output' / team_name / 'statlines' / 'roster.json'
    if not roster_path.exists():
        logger.error(f"  roster.json not found: {roster_path}")
        return False

    with open(roster_path, 'r', encoding='utf-8') as f:
        roster = json.load(f)

    # Load team config
    config_path = base_dir / 'config' / 'team-config.yaml'
    team_config = {}
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            all_config = yaml.safe_load(f)
        team_config = all_config.get('teams', {}).get(team_name, {})

    # Load team GUID
    guids_path = base_dir / 'config' / 'team-guids.json'
    team_guid = ''
    if guids_path.exists():
        with open(guids_path, 'r', encoding='utf-8') as f:
            guids = json.load(f)
        canonical = team_config.get('canonical_name', team_name.replace('-', ' ').title())
        team_guid = guids.get(canonical, '')

    # Load weapon rules database
    rules_path = base_dir / 'config' / 'weapon_rules.json'
    weapon_rules_db = {}
    if rules_path.exists():
        with open(rules_path, 'r', encoding='utf-8') as f:
            weapon_rules_db = json.load(f)

    output_path = base_dir / 'output' / team_name / f'{team_name}.rosz'
    if output_path.exists() and not force:
        logger.info(f"  {output_path.name} already exists (skip, use --force)")
        return True

    operatives = roster.get('operatives', [])
    logger.info(f"  {len(operatives)} operatives")

    # Log weapon type classification
    for op in operatives:
        for w in op.get('weapons', []):
            wtype = classify_weapon_type(w)
            logger.debug(f"    {op['name']}: {w['name']} -> {wtype}")

    xml = build_roster_xml(roster, team_config, team_guid, weapon_rules_db)
    write_rosz(xml, output_path)

    logger.info(f"  ✓ {output_path.name}")
    return True


def run(teams: List[str] = None, base_dir: Path = None, force: bool = False) -> Dict:
    """Main entry point."""
    if base_dir is None:
        base_dir = Path.cwd()

    if teams:
        team_list = teams
    else:
        statlines_root = base_dir / 'output'
        if not statlines_root.exists():
            logger.error("output/ directory not found")
            return {'error': 'no_output_dir'}
        team_list = [
            d.name for d in sorted(statlines_root.iterdir())
            if d.is_dir() and (d / 'statlines' / 'roster.json').exists()
        ]

    results = {'processed': [], 'failed': [], 'skipped': []}

    for team in team_list:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Generating ROSZ: {team}")
        logger.info(f"{'=' * 60}")

        ok = process_team(team, base_dir, force=force)
        if ok:
            results['processed'].append(team)
        else:
            results['failed'].append(team)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"ROSZ GENERATION COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Generated: {len(results['processed'])}")
    if results['failed']:
        logger.warning(f"Failed: {len(results['failed'])}: {results['failed']}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate .rosz files from roster data')
    parser.add_argument('--team', type=str, help='Process specific team')
    parser.add_argument('--force', action='store_true', help='Overwrite existing files')
    args = parser.parse_args()

    teams = [args.team] if args.team else None
    result = run(teams=teams, force=args.force)

    if result.get('failed'):
        sys.exit(1)
