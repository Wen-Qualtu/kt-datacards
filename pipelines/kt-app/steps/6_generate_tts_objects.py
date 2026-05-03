"""
Step 6: Generate TTS Objects

Generates Tabletop Simulator (TTS) JSON save files from classified cards and extracted data.
Creates card boxes containing all card types (datacards, equipment, ploys, etc.) organized into decks.

Input:
    layers/kt-app/classified/{team}/structure.json - Card organization
    output_v3/{team}/data/team_data.json - Operative stats and weapons
    output_v3/{team}/cards/{card_type}/*.png - Card images
    output_v3/{team}/tokens/*.png - Token images (for tokens_ready teams)
    config/team-config.yaml - Team metadata
    
Output:
    tts_objects_v3/{team}/{Team Name} Cards.json - TTS card box save file
"""

import argparse
import json
import logging
import hashlib
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ===================================================================
# GUID GENERATION
# ===================================================================

def generate_guid(seed: str = None) -> str:
    """Generate a deterministic GUID from seed or random if no seed."""
    if seed:
        # Deterministic GUID from seed
        hash_digest = hashlib.md5(seed.encode()).hexdigest()
        return f"{hash_digest[:8]}-{hash_digest[8:12]}-{hash_digest[12:16]}-{hash_digest[16:20]}-{hash_digest[20:32]}"
    else:
        # Random GUID
        import random
        import uuid
        return str(uuid.uuid4())


# ===================================================================
# TTS OBJECT BUILDERS
# ===================================================================

def create_tts_card(
    card_name: str,
    front_url: str,
    back_url: str,
    team_tag: str,
    deck_id: str = "100",
    card_type: Optional[str] = None,
    gm_notes: str = ""
) -> Dict[str, Any]:
    """Create a single TTS Card object."""
    
    card_id = int(deck_id + "00")
    
    # Build tags
    tags = [f"_{team_tag}"]
    if card_type:
        type_tag = get_card_type_tag(card_type)
        if type_tag:
            tags.append(type_tag)
    
    return {
        "GUID": generate_guid(f"{team_tag}:card:{card_name}"),
        "Name": "Card",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 180.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": card_name,
        "Description": "",
        "GMNotes": gm_notes,
        "Tags": tags,
        "Locked": False,
        "Grid": True,
        "Snap": True,
        "Autoraise": True,
        "Sticky": True,
        "Tooltip": True,
        "CardID": card_id,
        "SidewaysCard": False,
        "CustomDeck": {
            deck_id: {
                "FaceURL": front_url,
                "BackURL": back_url,
                "NumWidth": 1,
                "NumHeight": 1,
                "BackIsHidden": True,
                "UniqueBack": False,
                "Type": 0
            }
        },
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": ""
    }


def create_tts_deck(
    deck_nickname: str,
    team_tag: str,
    cards: List[Dict[str, Any]],
    starting_deck_id: int = 1000,
    card_type: Optional[str] = None
) -> Dict[str, Any]:
    """Create a TTS Deck object containing multiple cards."""
    
    # Build tags
    tags = [f"_{team_tag}"]
    if card_type:
        type_tag = get_card_type_tag(card_type)
        if type_tag:
            tags.append(type_tag)
    
    # Build contained card objects
    deck_ids = []
    contained_objects = []
    custom_deck = {}
    
    for idx, card_data in enumerate(cards):
        card_name = card_data.get('name', f'Card {idx + 1}')
        front_url = card_data.get('front_url', '')
        back_url = card_data.get('back_url', '')
        gm_notes = card_data.get('gm_notes', '')
        
        deck_id_str = str(starting_deck_id + idx)
        card_id = int(deck_id_str + "00")
        
        deck_ids.append(card_id)
        
        # Add to custom deck
        custom_deck[deck_id_str] = {
            "FaceURL": front_url,
            "BackURL": back_url,
            "NumWidth": 1,
            "NumHeight": 1,
            "BackIsHidden": True,
            "UniqueBack": False,
            "Type": 0
        }
        
        # Build card object
        card_obj = {
            "GUID": generate_guid(f"{team_tag}:card:{card_name}:{idx}"),
            "Name": "Card",
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": card_name,
            "Description": "",
            "GMNotes": gm_notes,
            "Tags": tags,
            "Locked": False,
            "CardID": card_id,
            "SidewaysCard": False,
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
        
        contained_objects.append(card_obj)
    
    # Reverse order so cards come out in correct sequence when drawn from top
    contained_objects.reverse()
    deck_ids.reverse()
    
    return {
        "GUID": generate_guid(f"{team_tag}:deck:{deck_nickname}"),
        "Name": "Deck",
        "Transform": {
            "posX": 0.0,
            "posY": 3.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 180.0,
            "rotZ": 180.0,
            "scaleX": 1.0,
            "scaleY": 1.0,
            "scaleZ": 1.0
        },
        "Nickname": deck_nickname,
        "Description": "",
        "GMNotes": "",
        "Tags": tags,
        "Locked": False,
        "DeckIDs": deck_ids,
        "CustomDeck": custom_deck,
        "ContainedObjects": contained_objects,
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": ""
    }


def create_tts_cardbox(
    team_name: str,
    team_display_name: str,
    team_tag: str,
    faction: str,
    contained_objects: List[Dict[str, Any]],
    lua_script: str = "",
    mesh_url: str = "",
    texture_url: str = ""
) -> Dict[str, Any]:
    """Create a TTS Custom_Model_Bag (cardbox) containing decks and cards."""
    
    # Build Lua script state
    lua_script_state = {
        "ml": {},  # Memory list (positions for decks when spawned)
        "rr": 270,  # Rotation
        "teamSlug": team_name,
        "lastCardUpdate": datetime.now(timezone.utc).isoformat(),
        "lastTokenUpdate": "",
        "tokenBagPositions": {}
    }
    
    # Top-level TTS save file structure
    return {
        "SaveName": "",
        "Date": "",
        "VersionNumber": "",
        "GameMode": "",
        "GameType": "",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "",
        "Sky": "",
        "Note": "",
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [
            {
                "GUID": generate_guid(f"{team_tag}:cardbox"),
                "Name": "Custom_Model_Bag",
                "Transform": {
                    "posX": 0.0,
                    "posY": 3.5,
                    "posZ": 0.0,
                    "rotX": 0.0,
                    "rotY": 270.0,
                    "rotZ": 0.0,
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "scaleZ": 1.0
                },
                "Nickname": team_display_name,
                "Description": "",
                "GMNotes": f"_{team_name}",
                "Tags": ["_Faction_Decks"],
                "Locked": False,
                "CustomMesh": {
                    "MeshURL": mesh_url or get_default_mesh_url(),
                    "DiffuseURL": texture_url or get_default_texture_url(),
                    "NormalURL": "",
                    "ColliderURL": "",
                    "Convex": True,
                    "MaterialIndex": 0,
                    "TypeIndex": 6,
                    "CastShadows": True
                },
                "Bag": {
                    "Order": 0
                },
                "LuaScript": lua_script,
                "LuaScriptState": json.dumps(lua_script_state, separators=(',', ': ')),
                "ContainedObjects": contained_objects,
                "XmlUI": ""
            }
        ]
    }


def get_card_type_tag(card_type: str) -> Optional[str]:
    """Get KTCards tag for a card type."""
    tag_map = {
        'datacards': 'KTDatacard',
        'operatives_selection': 'KTOperativeSelection',
        'faction_rules': 'KTFactionRules',
        'equipment': 'KTEquipment',
        'strategy_ploys': 'KTStrategyPloy',
        'firefight_ploys': 'KTFirefightPloy',
        'token_guide': 'KTTokenGuide'
    }
    return tag_map.get(card_type)


def get_default_mesh_url() -> str:
    """Get default cardbox mesh URL."""
    return "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refactor-kt-app-pipeline/config/defaults/tts-cardbox/cardbox-mesh.obj"


def get_default_texture_url() -> str:
    """Get default cardbox texture URL."""
    return "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refactor-kt-app-pipeline/config/defaults/tts-cardbox/cardbox-texture.png"


# ===================================================================
# TTS GENERATOR
# ===================================================================

class TTSObjectGenerator:
    """Generates TTS objects for teams."""
    
    def __init__(
        self,
        classified_dir: Path,
        output_v3_dir: Path,
        tts_output_dir: Path,
        config_file: Path
    ):
        self.classified_dir = classified_dir
        self.output_v3_dir = output_v3_dir
        self.tts_output_dir = tts_output_dir
        self.config_file = config_file
        
        # Load team config
        with open(self.config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            self.teams = config.get('teams', {})
    
    def process_team(self, team: str) -> bool:
        """
        Generate TTS objects for a single team.
        
        Args:
            team: Team slug
            
        Returns:
            True if successful
        """
        logger.info(f"Generating TTS objects for {team}...")
        
        # Load team config
        team_config = self.teams.get(team)
        if not team_config:
            logger.error(f"  Team not found in config: {team}")
            return False
        
        canonical_name = team_config.get('canonical_name', team.title())
        faction = team_config.get('faction', 'unknown')
        
        # Load structure
        structure_path = self.classified_dir / team / "structure.json"
        if not structure_path.exists():
            logger.error(f"  Structure file not found: {structure_path}")
            return False
        
        with open(structure_path, 'r', encoding='utf-8') as f:
            structure = json.load(f)
        
        # Load team data (stats)
        team_data_path = self.output_v3_dir / team / "data" / "team_data.json"
        team_data = {}
        if team_data_path.exists():
            with open(team_data_path, 'r', encoding='utf-8') as f:
                team_data = json.load(f)
        else:
            logger.warning(f"  Team data not found: {team_data_path}")
        
        # Build card decks
        contained_objects = []
        
        # Check if team has tokens ready
        tokens_ready = team_config.get('tokens_ready', False)
        
        # Card types to process (in order they should appear)
        card_types = [
            ('datacards', 'Datacards'),
            ('operatives_selection', 'Operative Selection'),
            ('faction_rules', 'Faction Rules'),
            ('equipment', 'Equipment'),
            ('strategy_ploys', 'Strategy Ploys'),
            ('firefight_ploys', 'Firefight Ploys'),
            ('token_guide', 'Token Guide')
        ]
        
        for card_type, display_name in card_types:
            if card_type not in structure or not structure[card_type]:
                continue
            
            cards_data = self._build_cards_for_type(team, card_type, structure[card_type], team_data)
            
            if not cards_data:
                continue
            
            # Create deck or single card
            if len(cards_data) > 1:
                deck = create_tts_deck(
                    deck_nickname=f"{display_name}",
                    team_tag=team,
                    cards=cards_data,
                    starting_deck_id=1000 + len(contained_objects) * 100,
                    card_type=card_type
                )
                contained_objects.append(deck)
                logger.info(f"  Added {display_name} deck with {len(cards_data)} cards")
            else:
                # Single card (not in a deck)
                card_data = cards_data[0]
                card = create_tts_card(
                    card_name=card_data['name'],
                    front_url=card_data['front_url'],
                    back_url=card_data['back_url'],
                    team_tag=team,
                    deck_id=str(100 + len(contained_objects)),
                    card_type=card_type,
                    gm_notes=card_data.get('gm_notes', '')
                )
                contained_objects.append(card)
                logger.info(f"  Added single {display_name} card")
        
        if not contained_objects:
            logger.warning(f"  No cards found for {team}")
            return False
        
        # Add token bag if tokens_ready
        if tokens_ready:
            token_bag = self._create_token_bag(team, team_config)
            if token_bag:
                contained_objects.append(token_bag)
                logger.info(f"  Added token bag")
        
        # Load Lua script
        lua_script = self._load_lua_script()
        
        # Get mesh and texture URLs (use defaults for now)
        mesh_url = get_default_mesh_url()
        texture_url = get_default_texture_url()
        
        # Create cardbox
        cardbox = create_tts_cardbox(
            team_name=team,
            team_display_name=canonical_name,
            team_tag=team,
            faction=faction,
            contained_objects=contained_objects,
            lua_script=lua_script,
            mesh_url=mesh_url,
            texture_url=texture_url
        )
        
        # Save to file
        output_dir = self.tts_output_dir / team
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{canonical_name} Cards.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(cardbox, f, indent=2, ensure_ascii=False)
        
        logger.info(f"  Saved to {output_file}")
        return True
    
    def _build_cards_for_type(
        self,
        team: str,
        card_type: str,
        entities: List[Dict],
        team_data: Dict
    ) -> List[Dict[str, Any]]:
        """Build card data for a specific card type."""
        cards = []
        
        for entity in entities:
            name = entity.get('name', 'Unknown')
            
            # Build URLs for front and back images
            # Cards are stored as: output_v3/{team}/cards/{card_type}/{team}-{slug}-front.png
            # Note: Step 4 already prefixed with team slug, so we don't add it again
            slug = self._slugify(name)
            front_url = self._build_card_url(team, card_type, f"{slug}-front.png")
            back_url = self._build_card_url(team, card_type, f"{slug}-back.png")
            
            # Build GM notes with stats (for datacards)
            gm_notes = ""
            if card_type == 'datacards' and team_data:
                gm_notes = self._build_gm_notes(name, team_data)
            
            cards.append({
                'name': name,
                'front_url': front_url,
                'back_url': back_url,
                'gm_notes': gm_notes
            })
        
        return cards
    
    def _build_card_url(self, team: str, card_type: str, filename: str) -> str:
        """Build GitHub raw URL for card image."""
        encoded_filename = filename.replace(' ', '%20')
        return f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refactor-kt-app-pipeline/output_v3/{team}/cards/{card_type}/{encoded_filename}"
    
    def _slugify(self, text: str) -> str:
        """Convert text to slug format."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')
    
    def _create_token_bag(self, team: str, team_config: Dict) -> Optional[Dict[str, Any]]:
        """Create a token bag for teams with tokens_ready."""
        tokens = team_config.get('tokens', [])
        if not tokens:
            return None
        
        # Check if token images exist
        token_dir = self.output_v3_dir / team / "tokens"
        if not token_dir.exists():
            logger.warning(f"  Token directory not found: {token_dir}")
            return None
        
        # Load token bag Lua script
        lua_script_path = PROJECT_ROOT / "config" / "defaults" / "tts-token" / "token-bag-script.lua"
        lua_script = ""
        if lua_script_path.exists():
            with open(lua_script_path, 'r', encoding='utf-8') as f:
                lua_script = f.read()
        
        # Build token objects
        token_objects = []
        for idx, token in enumerate(tokens):
            token_name = token.get('name', 'Unknown Token')
            token_type = token.get('type', 'token')
            
            # Build token image URL
            token_slug = self._slugify(token_name)
            token_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/refactor-kt-app-pipeline/output_v3/{team}/tokens/{token_slug}.png"
            
            # Create token object (Custom_Token)
            token_obj = {
                "GUID": generate_guid(f"{team}:token:{token_name}"),
                "Name": "Custom_Token",
                "Transform": {
                    "posX": 0.0,
                    "posY": 3.0,
                    "posZ": 0.0,
                    "rotX": 0.0,
                    "rotY": 0.0,
                    "rotZ": 0.0,
                    "scaleX": 1.0,
                    "scaleY": 1.0,
                    "scaleZ": 1.0
                },
                "Nickname": token_name,
                "Description": "",
                "GMNotes": "",
                "Tags": [f"_{team}"],
                "Locked": False,
                "CustomImage": {
                    "ImageURL": token_url,
                    "ImageSecondaryURL": token_url,
                    "ImageScalar": 1.0,
                    "WidthScale": 0.0,
                    "CustomToken": {
                        "Thickness": 0.1,
                        "MergeDistancePixels": 15.0,
                        "StandUp": False,
                        "Stackable": False
                    }
                },
                "LuaScript": "",
                "LuaScriptState": "",
                "XmlUI": ""
            }
            token_objects.append(token_obj)
        
        # Create bag
        bag = {
            "GUID": generate_guid(f"{team}:token-bag"),
            "Name": "Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 3.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": f"{team.title()} tokens",
            "Description": "",
            "GMNotes": "",
            "Tags": [f"_{team}", "KTCardsTokenBag"],
            "Locked": False,
            "Bag": {
                "Order": 0
            },
            "LuaScript": lua_script,
            "LuaScriptState": "",
            "ContainedObjects": token_objects,
            "XmlUI": ""
        }
        
        return bag
    
    def _build_gm_notes(self, operative_name: str, team_data: Dict) -> str:
        """Build GM notes JSON with operative stats."""
        # Find operative in team data
        datacards = team_data.get('datacards', [])
        
        for datacard in datacards:
            if datacard.get('name', '').upper() == operative_name.upper():
                # Build simplified stats JSON
                stats = {
                    'name': datacard.get('name'),
                    'apl': datacard.get('apl'),
                    'movement': datacard.get('movement'),
                    'save': datacard.get('save'),
                    'wounds': datacard.get('wounds'),
                    'weapons': datacard.get('weapons', [])
                }
                return json.dumps(stats, separators=(',', ':'))
        
        return ""
    
    def _load_lua_script(self) -> str:
        """Load Lua script for cardbox."""
        lua_script_path = PROJECT_ROOT / "config" / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
        
        if lua_script_path.exists():
            with open(lua_script_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            logger.warning(f"  Lua script not found: {lua_script_path}")
            return ""


# ===================================================================
# MAIN
# ===================================================================

def main():
    """Generate TTS objects for teams."""
    parser = argparse.ArgumentParser(
        description='Step 6: Generate TTS Objects'
    )
    parser.add_argument(
        '--classified-dir',
        type=Path,
        default=PROJECT_ROOT / 'layers' / 'kt-app' / 'classified',
        help='Classified structure directory'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=PROJECT_ROOT / 'output_v3',
        help='Output V3 directory'
    )
    parser.add_argument(
        '--tts-output-dir',
        type=Path,
        default=PROJECT_ROOT / 'tts_objects_v3',
        help='TTS objects output directory'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default=PROJECT_ROOT / 'config' / 'team-config.yaml',
        help='Team config file'
    )
    parser.add_argument(
        '--teams',
        type=str,
        help='Comma-separated list of teams to process (default: all)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration of TTS objects'
    )
    
    args = parser.parse_args()
    
    # Initialize generator
    generator = TTSObjectGenerator(
        classified_dir=args.classified_dir,
        output_v3_dir=args.output_dir,
        tts_output_dir=args.tts_output_dir,
        config_file=args.config
    )
    
    # Get teams to process
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    else:
        # Get all teams from classified directory
        teams = sorted([
            d.name for d in args.classified_dir.iterdir()
            if d.is_dir() and (d / "structure.json").exists()
        ])
    
    logger.info(f"Processing {len(teams)} teams...")
    
    # Process teams
    success_count = 0
    for team in teams:
        try:
            if generator.process_team(team):
                success_count += 1
        except Exception as e:
            logger.error(f"  Error processing {team}: {e}")
    
    logger.info(f"Successfully generated TTS objects for {success_count}/{len(teams)} teams")


if __name__ == "__main__":
    main()
