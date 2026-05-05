"""
Step 8: Embed Datacard Stats

Embeds operative stats (GMNotes + Lua script) into datacard objects in TTS JSON files.
Adds "Load stats to model" context menu functionality to all datacards.

Prerequisites:
    Step 3: Team data must be extracted (team_data.json)
    Step 7: TTS objects must be generated

Input:
    output_v3/{team}/data/team_data.json - Operative stats
    tts_objects_v3/{team}/*.json - TTS card box files
    config/defaults/tts-script/datacard-load-stats.lua - Datacard Lua script
    config/weapon_rules.json - Weapon rule definitions
    config/team-config.yaml - Team metadata
    
Output:
    tts_objects_v3/{team}/*.json - Patched with GMNotes and LuaScript
"""

import argparse
import json
import logging
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class DatacardStatsEmbedder:
    """Embeds operative stats into TTS datacard objects."""
    
    def __init__(
        self,
        output_v3_dir: Path,
        config_dir: Path
    ):
        self.output_v3_dir = output_v3_dir
        self.config_dir = config_dir
        
        # Load shared resources
        with open(config_dir / "weapon_rules.json", 'r', encoding='utf-8') as f:
            self.weapon_rules = json.load(f)
        
        with open(config_dir / "team-config.yaml", 'r', encoding='utf-8') as f:
            self.team_config = yaml.safe_load(f)
        
        # Load datacard Lua script
        lua_script_path = config_dir / "defaults" / "tts-script" / "datacard-load-stats.lua"
        with open(lua_script_path, 'r', encoding='utf-8') as f:
            self.lua_script = f.read()
    
    def process_team(self, team: str) -> Tuple[int, int]:
        """
        Embed stats for a single team.
        Returns (patched_count, total_count).
        """
        # Load team data
        team_data_path = self.output_v3_dir / team / "data" / "team_data.json"
        if not team_data_path.exists():
            logger.warning(f"  No team_data.json found for {team}")
            return 0, 0
        
        logger.debug(f"  Loading team data from {team_data_path}")
        with open(team_data_path, 'r', encoding='utf-8') as f:
            team_data = json.load(f)
        
        # Find TTS files (now in output_v3/{team}/tts_object/)
        tts_team_dir = self.output_v3_dir / team / "tts_object"
        if not tts_team_dir.exists():
            logger.warning(f"  No TTS objects found for {team}")
            return 0, 0
        
        tts_files = list(tts_team_dir.glob("*.json"))
        if not tts_files:
            logger.warning(f"  No TTS JSON files found for {team}")
            return 0, 0
        
        logger.debug(f"  Found {len(tts_files)} TTS files")
        
        total_patched = 0
        total_cards = 0
        
        for tts_file in tts_files:
            logger.debug(f"  Processing {tts_file.name}")
            with open(tts_file, 'r', encoding='utf-8') as f:
                tts_data = json.load(f)
            
            # Find all datacard objects
            datacards = self._find_datacards(tts_data)
            logger.debug(f"  Found {len(datacards)} datacard objects")
            if not datacards:
                continue
            
            modified = False
            for card in datacards:
                nickname = card.get("Nickname", "")
                total_cards += 1
                
                # Match card to operative in team_data
                operative = self._match_card_to_operative(nickname, team, team_data)
                if not operative:
                    logger.debug(f"  No match for card '{nickname}'")
                    continue
                
                # Build GMNotes data
                try:
                    gm_notes_data = self._build_gm_notes(operative, team_data)
                except Exception as e:
                    logger.error(f"  Error building GMNotes for '{nickname}': {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue
                
                gm_notes_json = json.dumps(gm_notes_data, separators=(",", ":"), ensure_ascii=False)
                
                # Get faction rule code if applicable (operative-specific for chaos-cult)
                operative_name = operative.get('name', '')
                faction_rule_code = self._get_faction_rule_code(team, team_data, operative_name)
                lua_script = self.lua_script + faction_rule_code
                
                # Set GMNotes and Lua script
                card["GMNotes"] = gm_notes_json
                card["LuaScript"] = lua_script
                
                modified = True
                total_patched += 1
            
            if modified:
                # Update bag timestamp
                self._update_bag_timestamp(tts_data)
                
                with open(tts_file, 'w', encoding='utf-8') as f:
                    json.dump(tts_data, f, indent=2, ensure_ascii=False)
                
                logger.info(f"  Patched {tts_file.name}")
        
        return total_patched, total_cards
    
    def _get_faction_rule_code(self, team: str, team_data: Dict, operative_name: str = "") -> str:
        """
        Generate faction rule Lua code from team_data.json.
        
        Generates Lua code for teams with faction-specific rules:
        - Chapter Tactics (angels-of-death)
        - Marks of Chaos + Accursed Gifts (legionaries)
        - Marks of Chaos (chaos-cult, specific operatives only)
        
        For chaos-cult, filters by operative name:
        - Chaos Mutant: single selection
        - Chaos Torment: Primary + Secondary
        - Others: no faction rules
        
        Args:
            team: Team slug
            team_data: Team data dict from team_data.json
            operative_name: Operative name for filtering (chaos-cult only)
            
        Returns:
            Lua code block for faction rule, or empty string if not applicable
        """
        # Check if team has faction rules in team_data
        faction_rules = team_data.get('faction_rules', [])
        if not faction_rules:
            return ""
        
        # For chaos-cult, only specific operatives get faction rules
        if team == "chaos-cult":
            op_lower = operative_name.lower()
            if "mutant" not in op_lower and "torment" not in op_lower and "possessed" not in op_lower:
                return ""  # Other operatives don't get faction rules
        
        # Load faction rule Lua template
        template_path = self.config_dir / "defaults" / "tts-script" / "faction-rule-chapter-tactics.lua"
        if not template_path.exists():
            logger.warning(f"  Faction rule template not found: {template_path}")
            return ""
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # Find first faction rule with options (Chapter Tactics, Marks of Chaos, etc.)
        rule_with_options = None
        for rule in faction_rules:
            if 'options' in rule and rule['options']:
                rule_with_options = rule
                break
        
        if not rule_with_options:
            logger.debug(f"  No faction rule with options found for {team}")
            return ""
        
        # Generate Lua options array
        rule_name = rule_with_options['name']
        options = rule_with_options['options']
        
        # Format options as Lua table entries
        lua_options = []
        for opt in options:
            opt_name = opt.get('name', '')
            opt_text = opt.get('text', '')
            # Escape Lua special chars
            opt_name_escaped = opt_name.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            opt_text_escaped = opt_text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            lua_options.append(f'    {{name = "{opt_name_escaped}", text = "{opt_text_escaped}"}}')
        
        options_str = ',\n'.join(lua_options)
        
        # Replace template placeholders
        lua_code = template.replace('{{FACTION_RULE_NAME}}', rule_name)
        lua_code = lua_code.replace('{{FACTION_RULE_OPTIONS}}', options_str)
        
        logger.info(f"  Generated faction rule code for {team} ({len(lua_code)} chars)")
        return lua_code
    
    def _find_datacards(self, tts_data: Dict) -> List[Dict]:
        """Find all datacard objects in TTS JSON."""
        datacards = []
        
        def recurse(obj):
            if isinstance(obj, dict):
                nickname = obj.get("Nickname", "")
                
                # Cards in a deck have CardID but no CustomDeck
                # Single cards have both CardID and CustomDeck
                if ("CardID" in obj or "CustomDeck" in obj) and nickname:
                    # Exclude deck names and special cards
                    excluded_patterns = [
                        "Datacards", "Equipment", "Strategy Ploys", "Firefight Ploys",
                        "OPERATIVE SELECTION", "TOKEN GUIDE", "SKILL AT ARMS"
                    ]
                    
                    is_excluded = any(pattern in nickname for pattern in excluded_patterns)
                    
                    if not is_excluded:
                        logger.debug(f"    Found datacard: {nickname}")
                        datacards.append(obj)
                
                # Recurse into nested structures
                for key, value in obj.items():
                    if key not in ["CustomDeck", "CustomImage"]:  # Don't recurse into asset definitions
                        recurse(value)
            elif isinstance(obj, list):
                for item in obj:
                    recurse(item)
        
        recurse(tts_data)
        return datacards
    
    def _match_card_to_operative(self, nickname: str, team: str, team_data: Dict) -> Optional[Dict]:
        """Match a card nickname to an operative in team_data."""
        # Nicknames in TTS may be short form: "sergeant" or "combat-medic"
        # Team data has full names: "KASRKIN SERGEANT" or "KASRKIN COMBAT MEDIC"
        # Normalize and match on the operative type (suffix) only
        def normalize(s):
            return s.lower().strip().replace("-", " ").replace("_", " ")
        
        nickname_norm = normalize(nickname)
        team_norm = normalize(team)
        
        # Search in datacards
        datacards = team_data.get('datacards', [])
        for operative in datacards:
            op_name = operative.get('name', '')
            op_name_norm = normalize(op_name)
            
            # Try exact match first
            if op_name_norm == nickname_norm:
                return operative
            
            # Try matching without team prefix
            if op_name_norm.startswith(team_norm):
                op_type = op_name_norm[len(team_norm):].strip()
                if op_type == nickname_norm:
                    return operative
        
        return None
    
    def _build_gm_notes(self, operative: Dict, team_data: Dict) -> Dict:
        """Build GMNotes JSON structure with operative stats (OLD FORMAT for Lua compatibility)."""
        import re
        
        # Helper: Parse movement string to integer (e.g., "7″" -> 7)
        def parse_move(s: str) -> int:
            m = re.search(r"(\d+)", str(s))
            return int(m.group(1)) if m else 6
        
        # Helper: Parse save string to integer (e.g., "4+" -> 4)
        def parse_save(s: str) -> int:
            m = re.search(r"(\d+)", str(s))
            return int(m.group(1)) if m else 5
        
        # Helper: Classify weapon type for prefix
        def classify_weapon(weapon: Dict) -> str:
            special_rules = weapon.get('special_rules', '').lower()
            if 'range' in special_rules or 'rng' in special_rules:
                return 'ranged'
            # Default to melee if no range specified
            return 'melee'
        
        # Helper: Get weapon prefix for TTS display
        def weapon_prefix(weapon: Dict) -> str:
            if classify_weapon(weapon) == 'melee':
                return '[F4641D]M[-]'
            return '[1E87FF]R[-]'
        
        # Build stats in OLD format (capital letters, integer values)
        stats = {
            'APL': operative.get('apl', 2),
            'Move': parse_move(operative.get('movement', '6')),
            'Save': parse_save(operative.get('save', '5+')),
            'Wounds': operative.get('wounds', 1)
        }
        
        # Build keywords list (Operative + extracted keywords)
        keywords = ['Operative']
        if 'keywords' in operative:
            keywords.extend(operative.get('keywords', []))
        
        # Build weapons array in OLD format
        weapons = []
        weapon_rules = {}
        for weapon in operative.get('weapons', []):
            weapon_name = weapon.get('name', '')
            special_rules = weapon.get('special_rules', '')
            
            # Add prefix to weapon name
            prefix = weapon_prefix(weapon)
            full_name = f'{prefix} {weapon_name}'
            
            weapons.append({
                'name': full_name,
                'plain_name': weapon_name,
                'stats': {
                    'ATK': weapon.get('attacks', ''),
                    'HIT': weapon.get('hit', ''),
                    'DMG': weapon.get('damage', ''),
                    'WR': special_rules
                }
            })
            
            # Extract weapon rules from special_rules text
            if special_rules:
                # Match rule names with descriptions from weapon_rules.json
                for rule_name, rule_description in self.weapon_rules.items():
                    if rule_name.lower() in special_rules.lower():
                        # weapon_rules.json has flat structure: {rule_name: description}
                        weapon_rules[rule_name] = rule_description
        
        # Build abilities array from passive_abilities (filter out malformed keyword entries)
        abilities = []
        for ability in operative.get('passive_abilities', []):
            ability_name = ability.get('name', '')
            ability_desc = ability.get('description', '')
            
            # Skip if description is just a number (malformed keyword extraction)
            if ability_desc.isdigit():
                continue
            
            # Skip if description starts with digits (e.g., "32 RULES CONTINUE ON OTHER SIDE")
            if ability_desc and ability_desc[0].isdigit():
                continue
            
            # Skip if name contains multiple commas (likely malformed keywords)
            if ',' in ability_name and len(ability_name.split(',')) > 3:
                continue
            
            # Skip if name is ALL UPPERCASE and longer than 20 chars (likely text fragment or keyword line)
            if ability_name.isupper() and len(ability_name) > 20:
                continue
            
            # Skip if name doesn't start with a capital letter (likely text fragment)
            if not ability_name or not ability_name[0].isupper():
                continue
            
            # Skip if name contains too many words (>5) - likely a sentence fragment
            word_count = len(ability_name.split())
            if word_count > 5:
                continue
            
            abilities.append({
                'name': ability_name,
                'text': ability_desc
            })
        
        # Build actions array from unique_actions
        actions = []
        for action in operative.get('unique_actions', []):
            actions.append({
                'name': action.get('name', ''),
                'text': action.get('description', '')
            })
        
        # Build description text (formatted for TTS display)
        description_lines = [
            f"[D36B3E][[84E680]APL[-] [ffffff]{stats['APL']}[-]] [[84E680]MOVE[-] [ffffff]{stats['Move']}\"[-]]",
            f"[[84E680]SAVE[-] [ffffff]{stats['Save']}+[-]] [[84E680]WOUNDS[-] [ffffff]{stats['Wounds']}[-]][-]"
        ]
        
        if keywords:
            description_lines.append('[C5C5C5]' + ', '.join(keywords) + '[-]')
        
        description_lines.append('[31B32B]Weapons[-]')
        for w in weapons:
            description_lines.append(w['name'])
            w_stats = w['stats']
            description_lines.append(
                f"[84E680]ATK[-] {w_stats['ATK']} [84E680]HIT[-] {w_stats['HIT']} [84E680]DMG[-] {w_stats['DMG']}"
            )
            if w_stats['WR']:
                description_lines.append(f"[84E680]WR[-]: {w_stats['WR']}")
            description_lines.append('')
        
        if abilities:
            description_lines.append('---')
            description_lines.append('[31B32B]Abilities[-]')
            for ab in abilities:
                description_lines.append(f"- [EF8450]{ab['name']}[-]")
        
        if actions:
            description_lines.append('---')
            description_lines.append('[31B32B]Unique Actions[-]')
            for act in actions:
                description_lines.append(f"- [EF8450]{act['name']}[-]")
        
        description = '\n'.join(description_lines)
        
        # Assemble GMNotes in OLD format (matches script/embed_datacard_stats.py)
        gm_notes = {
            'name': operative.get('name', ''),
            'stats': stats,
            'keywords': keywords,
            'weapons': weapons,
            'abilities': abilities,
            'actions': actions,
            'weapon_rules': weapon_rules,
            'description': description
        }
        
        # Add selection data if available (for weapon loadout choices)
        selection_data = self._get_selection_for_operative(operative.get('name', ''), team_data)
        if selection_data:
            gm_notes['selection'] = selection_data
        
        return gm_notes
    
    def _get_selection_for_operative(self, operative_name: str, team_data: Dict) -> Optional[Dict]:
        """
        Get weapon selection data for an operative from team_data.json.
        
        Uses operatives_selection.selection from team_data extracted by step 3.
        
        Returns selection structure: {groups: [[{label, weapons}]], fixed: [], exclusive_sets: [[]]}
        or None if no selection data exists.
        """
        team = team_data.get('team', '')
        
        # Get selection data from operatives_selection in team_data
        # operatives_selection is a list with one entry containing {name, text, selection, exclusive_sets}
        operatives_selection_list = team_data.get('operatives_selection', [])
        if not operatives_selection_list or not isinstance(operatives_selection_list, list):
            logger.debug(f"  No operatives_selection in team_data for {team}")
            return None
        
        # Extract selection data from first entry
        operatives_selection = operatives_selection_list[0] if operatives_selection_list else {}
        selection_lookup = operatives_selection.get('selection', {})
        exclusive_sets_lookup = operatives_selection.get('exclusive_sets', {})
        
        if not selection_lookup:
            logger.debug(f"  No selection data in operatives_selection for {team}")
            return None
        
        # Normalize operative name for lookup (uppercase)
        op_name_upper = operative_name.upper()
        selection_groups = selection_lookup.get(op_name_upper, [])
        
        if not selection_groups:
            return None
        
        # Build indexed selection structure
        return self._build_selection_for_gmnotes(
            selection_groups,
            team_data.get('datacards', []),
            operative_name,
            exclusive_sets_lookup.get(op_name_upper)
        )
    
    def _build_selection_for_gmnotes(
        self,
        selection_groups: List[List[str]],
        datacards: List[Dict],
        operative_name: str,
        exclusive_sets: Optional[List[List[int]]] = None
    ) -> Optional[Dict]:
        """
        Transform selection groups into indexed format for TTS GMNotes.
        
        Returns {"groups": [[{"label": str, "weapons": [int]}]], "fixed": [int]}
        where weapon indices are 0-based into the weapons list.
        """
        # Find the operative to get weapon list
        operative = None
        for op in datacards:
            if op.get('name', '') == operative_name:
                operative = op
                break
        
        if not operative:
            return None
        
        weapons = operative.get('weapons', [])
        if not weapons:
            return None
        
        weapon_names_lower = [w.get('name', '').lower() for w in weapons]
        all_matched = set()
        result_groups = []
        
        for group in selection_groups:
            group_options = []
            for option_label in group:
                # Split "; " or " and " combos into individual weapon fragments
                fragments = [f.strip().lower() for f in re.split(r'\s*;\s*|\s+and\s+', option_label)]
                matched = set()
                for frag in fragments:
                    # Handle "X or Y" alternatives within a fragment
                    sub_frags = [sf.strip() for sf in frag.split(" or ")]
                    for sf in sub_frags:
                        for i, wname in enumerate(weapon_names_lower):
                            if sf in wname:
                                matched.add(i)
                all_matched.update(matched)
                group_options.append({"label": option_label, "weapons": sorted(matched)})
            result_groups.append(group_options)
        
        # Weapons not covered by any option are always included
        fixed = [i for i in range(len(weapons)) if i not in all_matched]
        
        result = {"groups": result_groups, "fixed": fixed}
        if exclusive_sets:
            result["exclusive_sets"] = exclusive_sets
        return result
    
    def _update_bag_timestamp(self, tts_data: Dict) -> None:
        """Update lastCardUpdate in the top-level bag's LuaScriptState."""
        obj = tts_data.get("ObjectStates", [{}])[0]
        lss = obj.get("LuaScriptState", "")
        try:
            state = json.loads(lss) if lss else {}
        except (json.JSONDecodeError, TypeError):
            state = {}
        
        state["lastCardUpdate"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        obj["LuaScriptState"] = json.dumps(state)


def main():
    """Embed datacard stats for teams."""
    parser = argparse.ArgumentParser(
        description='Step 8: Embed Datacard Stats'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=PROJECT_ROOT / 'output_v3',
        help='Output V3 directory'
    )
    parser.add_argument(
        '--config-dir',
        type=Path,
        default=PROJECT_ROOT / 'config',
        help='Config directory'
    )
    parser.add_argument(
        '--teams',
        type=str,
        help='Comma-separated list of teams to process (default: all)'
    )
    
    args = parser.parse_args()
    
    # Initialize embedder
    logger.info("Step 8: Embedding datacard stats...")
    embedder = DatacardStatsEmbedder(
        output_v3_dir=args.output_dir,
        config_dir=args.config_dir
    )
    
    # Get teams to process
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    else:
        # Get all teams from output_v3 that have team_data.json
        teams = []
        if args.output_dir.exists():
            for team_dir in sorted(args.output_dir.iterdir()):
                if team_dir.is_dir():
                    team = team_dir.name
                    team_data_path = team_dir / "data" / "team_data.json"
                    tts_team_dir = team_dir / "tts_object"
                    if team_data_path.exists() and tts_team_dir.exists():
                        teams.append(team)
    
    if not teams:
        logger.error("No teams found to process")
        return
    
    logger.info(f"Processing {len(teams)} teams...")
    
    # Process teams
    total_patched = 0
    total_cards = 0
    success_count = 0
    
    for team in teams:
        try:
            patched, cards = embedder.process_team(team)
            if cards > 0:
                logger.info(f"  {team}: {patched}/{cards} datacards patched")
                success_count += 1
            total_patched += patched
            total_cards += cards
        except Exception as e:
            import traceback
            logger.error(f"  Error processing {team}: {e}")
            logger.debug(traceback.format_exc())
    
    logger.info(f"Successfully embedded stats: {total_patched}/{total_cards} datacards across {success_count} teams")


if __name__ == "__main__":
    main()
