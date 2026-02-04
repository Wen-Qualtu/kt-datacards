"""
Step 5: Generate TTS Objects from Extracted Cards

Generates Tabletop Simulator (TTS) JSON objects for all teams in the output folder.
Uses a self-contained TTS generation system with:
- Hash-based change detection for incremental updates
- Persistent GUIDs for stable object identity
- Hierarchical metadata tracking (team → cardbox → decks → cards)
- GitHub raw URLs for spawning objects in TTS

Input:  output/{team}/cards/**/*.jpg
Output: tts_objects/{team}/cardbox/*.json (nested structure)
        tts_objects/.tts-metadata.json (full tracking)
        tts_objects/.tts-manifest.json (lightweight for TTS Lua)

Architecture:
- Full metadata: Complete hierarchical structure with all components for repo tracking
- Manifest: Lightweight summary for TTS Lua scripts to check updates without choking

Note: This file is self-contained - all TTS generation code is inlined to keep
      each pipeline step independent without external dependencies.
"""

import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod


# ===================================================================
# CHANGE DETECTION SYSTEM
# ===================================================================

@dataclass
class ComponentMetadata:
    """Metadata for a single TTS component"""
    guid: str = ""
    url: str = ""
    component_type: str = ""
    content_hash: str = ""
    last_modified: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary maintaining field order"""
        return {
            "guid": self.guid,
            "url": self.url,
            "component_type": self.component_type,
            "content_hash": self.content_hash,
            "last_modified": self.last_modified
        }


class ChangeDetector:
    """Detects changes in TTS components using content hashing."""
    
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load existing metadata from file"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self):
        """Save metadata to file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def compute_hash(self, content: Any) -> str:
        """Compute SHA-256 hash of content."""
        if isinstance(content, dict):
            content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
            content_bytes = content_str.encode('utf-8')
        elif isinstance(content, str):
            content_bytes = content.encode('utf-8')
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")
        
        return hashlib.sha256(content_bytes).hexdigest()
    
    def has_changed(self, component_path: str, content: Any, component_type: str) -> Tuple[bool, Optional[Dict]]:
        """Check if component content has changed since last generation."""
        current_hash = self.compute_hash(content)
        existing_meta = self._get_component_metadata(component_path)
        
        if existing_meta is None:
            return True, None
        
        stored_hash = existing_meta.get('content_hash')
        return current_hash != stored_hash, existing_meta
    
    def update_metadata(
        self,
        component_path: str,
        content: Any,
        component_type: str,
        guid: str = "",
        url: str = "",
        timestamp: Optional[str] = None
    ) -> ComponentMetadata:
        """Update metadata for a component."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        content_hash = self.compute_hash(content)
        
        # Preserve existing GUID and URL if not provided
        existing_meta = self._get_component_metadata(component_path)
        if not guid and existing_meta and 'guid' in existing_meta:
            guid = existing_meta['guid']
        if not url and existing_meta and 'url' in existing_meta:
            url = existing_meta['url']
        
        metadata = ComponentMetadata(
            guid=guid,
            url=url,
            component_type=component_type,
            content_hash=content_hash,
            last_modified=timestamp
        )
        
        self._set_component_metadata(component_path, metadata.to_dict())
        return metadata
    
    def _get_component_metadata(self, component_path: str) -> Optional[Dict]:
        """Get metadata for component at path"""
        parts = component_path.split('.')
        current = self.metadata
        
        if parts[-1] == "_self":
            parts = parts[:-1]
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        if isinstance(current, dict) and 'content_hash' in current:
            return current
        return None
    
    def _set_component_metadata(self, component_path: str, metadata: Dict):
        """Set metadata for component at path"""
        parts = component_path.split('.')
        current = self.metadata
        
        is_container = parts[-1] == "_self"
        if is_container:
            parts = parts[:-1]
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise ValueError(f"Cannot set nested path {component_path}: {part} is a leaf node")
            current = current[part]
        
        last_part = parts[-1]
        metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
        
        if last_part in current and isinstance(current[last_part], dict):
            children = {k: v for k, v in current[last_part].items() if k not in metadata_fields}
            current[last_part] = {**metadata, **children}
        else:
            current[last_part] = metadata
    
    def get_guid(self, component_path: str) -> Optional[str]:
        """Get stored GUID for component"""
        meta = self._get_component_metadata(component_path)
        return meta.get('guid') if meta else None


class ComponentRegistry:
    """Registry of generated components with their metadata."""
    
    def __init__(self, change_detector: ChangeDetector):
        self.detector = change_detector
        self.generated_components: Dict[str, ComponentMetadata] = {}
    
    def register(
        self,
        component_path: str,
        content: Any,
        component_type: str,
        guid: str = "",
        url: str = "",
        force_update: bool = False
    ) -> Tuple[bool, ComponentMetadata]:
        """Register a component for generation."""
        changed, existing_meta = self.detector.has_changed(component_path, content, component_type)
        
        if changed or force_update:
            metadata = self.detector.update_metadata(component_path, content, component_type, guid, url)
            self.generated_components[component_path] = metadata
            return True, metadata
        else:
            metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
            filtered_meta = {k: v for k, v in existing_meta.items() if k in metadata_fields}
            metadata = ComponentMetadata(**filtered_meta)
            self.generated_components[component_path] = metadata
            return False, metadata


# ===================================================================
# TTS TAGGING SYSTEM
# ===================================================================

class TTSTagGenerator:
    """Generate consistent tags for TTS objects"""
    
    CARD_TYPE_TAGS = {
        "datacards": "KTCardsDatacard",
        "operative-selection": "KTCardsOperativeSelection",
        "faction-rules": "KTCardsFactionRule",
        "firefight-ploys": "KTCardsFirefightPloy",
        "strategy-ploys": "KTCardsStrategyPloy",
        "equipment": "KTCardsEquipment",
        "tactical-ops": "KTCardsTacticalOps",
        "rare-equipment": "KTCardsRareEquipment",
        "spec-ops": "KTCardsSpecOps",
    }
    
    @classmethod
    def get_card_tags(cls, team_name: str, card_type: str, has_back: bool = True) -> List[str]:
        """Generate tags for a card."""
        tags = []
        
        # Team tag
        team_pascal = ''.join(word.capitalize() for word in team_name.split('-'))
        tags.append(f"KT{team_pascal}")
        
        # Card type tag
        type_tag = cls.CARD_TYPE_TAGS.get(card_type)
        if type_tag:
            tags.append(type_tag)
        
        # Generic card tag
        tags.append("KTCard")
        
        # Double-sided tag
        if has_back:
            tags.append("KTCardDoubleSided")
        
        return tags


# ===================================================================
# TTS COMPONENT CLASSES
# ===================================================================

class TTSComponent(ABC):
    """Abstract base class for all TTS components."""
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.metadata: Optional[ComponentMetadata] = None
        self._content: Optional[Dict] = None
    
    @abstractmethod
    def generate(self) -> Dict[str, Any]:
        """Generate the TTS JSON structure for this component."""
        pass
    
    @abstractmethod
    def get_component_path(self) -> str:
        """Get the dot-notation path for this component."""
        pass
    
    @abstractmethod
    def get_component_type(self) -> str:
        """Get the component type identifier."""
        pass
    
    def build(self, force_update: bool = False) -> Tuple[Dict[str, Any], bool]:
        """Build the component with change detection."""
        content = self.generate()
        self._content = content
        
        guid = content.get('GUID', '')
        url = self._generate_json_url()
        
        was_updated, metadata = self.registry.register(
            self.get_component_path(),
            content,
            self.get_component_type(),
            guid,
            url,
            force_update
        )
        
        self.metadata = metadata
        return content, was_updated
    
    def _generate_json_url(self) -> str:
        """Generate GitHub raw URL to this component's JSON file."""
        workspace_root = Path(__file__).parent.parent.parent.parent
        # Get team name from component path
        path_parts = self.get_component_path().split('.')
        team_name = path_parts[0]
        
        # Calculate relative path from workspace root
        output_base = workspace_root / "output" / team_name / "tts"
        file_path = self.get_file_path(output_base)
        rel_path = file_path.relative_to(workspace_root).as_posix()
        
        repo_url = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
        return f"{repo_url}/{rel_path}"
    
    def get_file_path(self, output_dir: Path) -> Path:
        """Get the file path for this component based on its component path."""
        path_parts = self.get_component_path().split('.')
        team_name = path_parts[0]
        
        if len(path_parts) == 3 and path_parts[2] == "_self":
            # team.cardbox._self -> output/{team}/tts/cardbox.json
            return output_dir / "cardbox.json"
        elif len(path_parts) == 4 and path_parts[3] == "_self":
            # team.cardbox.TYPE._self -> output/{team}/tts/cardbox/decks/{team}-TYPE.json
            return output_dir / "cardbox" / "decks" / f"{team_name}-{path_parts[2]}.json"
        elif len(path_parts) == 4:
            # team.cardbox.TYPE.NAME -> output/{team}/tts/cardbox/decks/TYPE/{team}-NAME.json
            return output_dir / "cardbox" / "decks" / path_parts[2] / f"{team_name}-{path_parts[3]}.json"
        elif len(path_parts) == 3:
            # team.cardbox.NAME (single card) -> output/{team}/tts/cardbox/{team}-NAME.json
            return output_dir / "cardbox" / f"{team_name}-{path_parts[2]}.json"
        else:
            raise ValueError(f"Unexpected component path format: {self.get_component_path()}")


class TTSCard(TTSComponent):
    """TTS Card component"""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        card_name: str,
        front_url: str,
        back_url: str,
        card_type: str = None,
        is_in_deck: bool = True,
        tags: Optional[List[str]] = None
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.card_name = card_name
        self.front_url = front_url
        self.back_url = back_url
        self.card_type = card_type
        self.is_in_deck = is_in_deck
        self.tags = tags or []
    
    def get_component_path(self) -> str:
        if self.is_in_deck and self.card_type:
            return f"{self.team_name}.cardbox.{self.card_type}.{self.card_name}"
        else:
            return f"{self.team_name}.cardbox.{self.card_type or self.card_name}"
    
    def get_component_type(self) -> str:
        return "card"
    
    def generate(self) -> Dict[str, Any]:
        """Generate TTS Card object"""
        return {
            "GUID": self._generate_guid(),
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
            "Nickname": self.card_name,
            "Description": "",
            "GMNotes": "",
            "Tags": self.tags,
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "CardID": 100000,
            "SidewaysCard": False,
            "CustomDeck": {
                "1000": {
                    "FaceURL": self.front_url,
                    "BackURL": self.back_url,
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
    
    def _generate_guid(self) -> str:
        """Generate or retrieve persistent GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_{self.card_name}".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSDeck(TTSComponent):
    """TTS Deck component"""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        deck_type: str,
        cards: List[TTSCard]
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.deck_type = deck_type
        self.cards = cards
    
    def get_component_path(self) -> str:
        return f"{self.team_name}.cardbox.{self.deck_type}._self"
    
    def get_component_type(self) -> str:
        return "deck"
    
    def generate(self) -> Dict[str, Any]:
        """Generate TTS Deck object"""
        card_objects = []
        for card in self.cards:
            card_content, _ = card.build()
            card_objects.append(card_content)
        
        return {
            "GUID": self._generate_guid(),
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
            "Nickname": f"{self.deck_type} deck",
            "Description": "",
            "GMNotes": "",
            "Tags": [f"_{self.team_name}"],
            "DeckIDs": [card["CardID"] for card in card_objects],
            "CustomDeck": self._merge_custom_decks(card_objects),
            "ContainedObjects": card_objects,
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    
    def _merge_custom_decks(self, cards: List[Dict]) -> Dict:
        """Merge CustomDeck definitions from all cards"""
        merged = {}
        for card in cards:
            if "CustomDeck" in card:
                merged.update(card["CustomDeck"])
        return merged
    
    def _generate_guid(self) -> str:
        """Generate or retrieve persistent GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_{self.deck_type}_deck".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSCardBox(TTSComponent):
    """Complete TTS card box containing all decks for a team."""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        team_display_name: str,
        faction: str,
        decks: List[TTSDeck],
        mesh_url: str,
        texture_url: str,
        lua_script: str = "",
        single_cards: Optional[List[TTSCard]] = None,
        token_bag: Optional[Any] = None
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.team_display_name = team_display_name
        self.faction = faction
        self.decks = decks
        self.single_cards = single_cards or []
        self.mesh_url = mesh_url
        self.texture_url = texture_url
        self.lua_script = lua_script
        self.token_bag = token_bag
    
    def get_component_path(self) -> str:
        return f"{self.team_name}.cardbox._self"
    
    def get_component_type(self) -> str:
        return "cardbox"
    
    def generate(self) -> Dict[str, Any]:
        """Generate complete TTS cardbox"""
        deck_objects = []
        for deck in self.decks:
            deck_content, _ = deck.build()
            deck_objects.append(deck_content)
        
        for card in self.single_cards:
            card_content, _ = card.build()
            deck_objects.append(card_content)
        
        if self.token_bag:
            token_bag_content, _ = self.token_bag.build()
            deck_objects.append(token_bag_content)
        
        # Aggregate timestamps from metadata
        card_timestamps = []
        token_timestamps = []
        
        if self.team_name in self.registry.detector.metadata:
            team_meta = self.registry.detector.metadata[self.team_name]
            if "cardbox" in team_meta:
                cardbox_meta = team_meta["cardbox"]
                metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
                
                for key, value in cardbox_meta.items():
                    if key in metadata_fields:
                        continue
                    if isinstance(value, dict):
                        if "last_modified" in value:
                            card_timestamps.append(value["last_modified"])
                        for card_key, card_data in value.items():
                            if card_key not in metadata_fields and isinstance(card_data, dict) and "last_modified" in card_data:
                                card_timestamps.append(card_data["last_modified"])
        
        card_timestamp = max(card_timestamps) if card_timestamps else ""
        token_timestamp = max(token_timestamps) if token_timestamps else ""
        
        lua_script_state = {
            "ml": {},
            "rr": 270,
            "teamSlug": self.team_name,
            "lastCardUpdate": card_timestamp,
            "lastTokenUpdate": token_timestamp,
            "tokenBagPositions": {}
        }
        
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
                    "GUID": self._generate_guid(),
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
                    "Nickname": self.team_display_name,
                    "Description": "",
                    "GMNotes": f"_{self.team_name}",
                    "Tags": ["_Faction_Decks"],
                    "Locked": False,
                    "CustomMesh": {
                        "MeshURL": self.mesh_url,
                        "DiffuseURL": self.texture_url,
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
                    "LuaScript": self.lua_script,
                    "LuaScriptState": json.dumps(lua_script_state, separators=(',', ': ')),
                    "ContainedObjects": deck_objects,
                    "XmlUI": ""
                }
            ]
        }
    
    def _generate_guid(self) -> str:
        """Generate deterministic GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_cardbox".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


# ===================================================================
# PIPELINE FUNCTIONS
# ===================================================================


def find_all_teams(output_dir: Path) -> List[Path]:
    """Find all team directories in output folder."""
    teams = []
    for team_dir in output_dir.iterdir():
        if team_dir.is_dir() and (team_dir / 'cards').exists():
            teams.append(team_dir)
    return sorted(teams)


def get_team_metadata(team_dir: Path) -> Dict[str, str]:
    """
    Extract team metadata from directory structure.
    
    Returns:
        Dict with team_name, faction, army (if available)
    """
    team_name = team_dir.name
    
    # Try to infer faction from known mappings or metadata files
    # For now, return basic info
    return {
        'team_name': team_name,
        'slug': team_name
    }


def find_card_images(cards_dir: Path, card_type: str, card_name: str) -> Dict[str, str]:
    """
    Find front and back images for a card.
    
    Args:
        cards_dir: Base cards directory (output/{team}/cards/)
        card_type: Type of card (datacards, equipment, firefight-ploys, etc.)
        card_name: Card name
    
    Returns:
        Dict with 'front' and 'back' GitHub raw URLs (back may be empty)
    """
    # Handle ploys subdirectory structure
    if card_type.endswith('-ploys'):
        # firefight-ploys -> ploys/firefight, strategy-ploys -> ploys/strategy
        ploy_type = card_type.replace('-ploys', '')
        type_dir = cards_dir / 'ploys' / ploy_type
    else:
        type_dir = cards_dir / card_type
    
    if not type_dir.exists():
        return {'front': '', 'back': ''}
    
    # Build GitHub raw URL base
    repo_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
    team_name = cards_dir.parent.name
    
    # Look for front and back images
    front_patterns = [f"{card_name}-front.jpg", f"{card_name}-front.png"]
    back_patterns = [f"{card_name}-back.jpg", f"{card_name}-back.png"]
    
    front_url = ""
    back_url = ""
    
    # Get workspace root
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    for pattern in front_patterns:
        front_path = type_dir / pattern
        if front_path.exists():
            rel_path = front_path.relative_to(workspace_root)
            front_url = f"{repo_base}/{rel_path.as_posix()}"
            break
    
    for pattern in back_patterns:
        back_path = type_dir / pattern
        if back_path.exists():
            rel_path = back_path.relative_to(workspace_root)
            back_url = f"{repo_base}/{rel_path.as_posix()}"
            break
    
    return {'front': front_url, 'back': back_url}


def organize_cards_by_type(cards_dir: Path) -> Dict[str, List[str]]:
    """
    Organize cards by type based on directory structure.
    
    Returns:
        Dict mapping card_type -> list of card base names
    """
    cards_by_type = {}
    
    for type_dir in cards_dir.iterdir():
        if not type_dir.is_dir():
            continue
        
        # Handle ploys/ subdirectory with firefight/ and strategy/
        if type_dir.name == 'ploys':
            for ploy_subdir in type_dir.iterdir():
                if not ploy_subdir.is_dir():
                    continue
                
                # firefight -> firefight-ploys, strategy -> strategy-ploys
                card_type = f"{ploy_subdir.name}-ploys"
                cards = set()
                
                for img_path in ploy_subdir.glob('*.jpg'):
                    name = img_path.stem
                    if name.endswith('-front'):
                        base_name = name[:-6]
                    elif name.endswith('-back'):
                        base_name = name[:-5]
                    else:
                        base_name = name
                    
                    team_name = cards_dir.parent.name
                    if base_name.startswith(f"{team_name}-"):
                        base_name = base_name[len(team_name)+1:]
                    
                    cards.add(base_name)
                
                if cards:
                    cards_by_type[card_type] = sorted(cards)
            continue
        
        card_type = type_dir.name
        cards = set()
        
        # Find all card base names (strip -front/-back suffix)
        for img_path in type_dir.glob('*.jpg'):
            name = img_path.stem
            # Remove -front/-back suffix
            if name.endswith('-front'):
                base_name = name[:-6]
            elif name.endswith('-back'):
                base_name = name[:-5]
            else:
                base_name = name
            
            # Remove team prefix if present
            team_name = cards_dir.parent.name
            if base_name.startswith(f"{team_name}-"):
                base_name = base_name[len(team_name)+1:]
            
            cards.add(base_name)
        
        if cards:
            cards_by_type[card_type] = sorted(cards)
    
    return cards_by_type


def generate_team_tts(team_dir: Path, output_dir: Path, registry: ComponentRegistry) -> bool:
    """
    Generate TTS objects for a single team.
    
    Args:
        team_dir: Path to team directory (output/{team}/)
        output_dir: Base TTS output directory (tts_objects/)
        registry: Component registry for change detection
    
    Returns:
        True if any components were updated
    """
    team_meta = get_team_metadata(team_dir)
    team_name = team_meta['team_name']
    cards_dir = team_dir / 'cards'
    
    print(f"\nProcessing {team_name}...")
    
    # Organize cards by type
    cards_by_type = organize_cards_by_type(cards_dir)
    
    if not cards_by_type:
        print(f"  ⚠ No cards found for {team_name}")
        return False
    
    # Map card types to deck types
    type_mapping = {
        'datacards': 'datacards',
        'equipment': 'equipment',
        'faction-rules': 'faction-rules',
        'ploys': 'firefight-ploys',  # Assume firefight ploys for now
        'operative-selection': 'operative-selection'
    }
    
    all_decks = []
    single_cards = []
    
    # Create decks/cards for each type
    for card_type, card_names in cards_by_type.items():
        deck_type = type_mapping.get(card_type, card_type)
        
        # Special handling for operative-selection (usually single card)
        if deck_type == 'operative-selection' and len(card_names) == 1:
            card_name = card_names[0]
            images = find_card_images(cards_dir, card_type, f"{team_name}-{card_name}")
            
            if images['front']:
                card = TTSCard(
                    registry=registry,
                    team_name=team_name,
                    card_name=card_name,
                    front_url=images['front'],
                    back_url=images['back'] or images['front'],
                    card_type=deck_type,
                    is_in_deck=False,
                    tags=TTSTagGenerator.get_card_tags(team_name, deck_type, bool(images['back']))
                )
                single_cards.append(card)
                print(f"  ✓ Created single card: {card_name}")
            continue
        
        # Create deck for this type
        cards_in_deck = []
        for card_name in card_names:
            images = find_card_images(cards_dir, card_type, f"{team_name}-{card_name}")
            
            if not images['front']:
                print(f"  ⚠ Missing front image for {card_name}")
                continue
            
            card = TTSCard(
                registry=registry,
                team_name=team_name,
                card_name=card_name,
                front_url=images['front'],
                back_url=images['back'] or images['front'],
                card_type=deck_type,
                is_in_deck=True,
                tags=TTSTagGenerator.get_card_tags(team_name, deck_type, bool(images['back']))
            )
            cards_in_deck.append(card)
        
        if cards_in_deck:
            deck = TTSDeck(
                registry=registry,
                team_name=team_name,
                deck_type=deck_type,
                cards=cards_in_deck
            )
            all_decks.append(deck)
            print(f"  ✓ Created {deck_type} deck with {len(cards_in_deck)} cards")
    
    # TODO: Token bag generation (commented out until tokens are extracted)
    # token_bag = None
    # tokens_dir = team_dir / 'tokens'
    # if tokens_dir.exists():
    #     dispensers = []
    #     for token_path in tokens_dir.glob('*.png'):
    #         token_name = token_path.stem
    #         # Create token dispenser...
    #     if dispensers:
    #         token_bag = TTSTokenBag(
    #             team_name=team_name,
    #             dispensers=dispensers,
    #             registry=registry
    #         )
    #         print(f"  ✓ Created token bag with {len(dispensers)} dispensers")
    
    # Create cardbox (container for all decks and token bag)
    # TODO: Extract proper faction and display name from metadata
    team_display_name = team_name.replace('-', ' ').title()
    faction = "Unknown"  # Will be extracted from metadata in future
    
    # Default box mesh/texture (can be customized per team later)
    mesh_url = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/layers/kt-app/assets/cardbox-mesh.obj"
    texture_url = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/layers/kt-app/assets/cardbox-texture.png"
    
    cardbox = TTSCardBox(
        registry=registry,
        team_name=team_name,
        team_display_name=team_display_name,
        faction=faction,
        decks=all_decks,
        single_cards=single_cards,
        token_bag=None,  # Will be added when tokens are ready
        mesh_url=mesh_url,
        texture_url=texture_url
    )
    
    # Build all components (triggers change detection)
    print(f"\nBuilding components...")
    cardbox_content, was_updated = cardbox.build()
    
    if was_updated:
        print(f"  ✓ Cardbox was UPDATED")
    else:
        print(f"  ○ Cardbox unchanged")
    
    # Save all component JSONs
    print(f"\nSaving component JSONs...")
    team_output = output_dir / team_name / "tts"
    
    # Save cardbox container
    cardbox_file = team_output / "cardbox.json"
    cardbox_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cardbox_file, 'w', encoding='utf-8') as f:
        json.dump(cardbox_content, f, indent=2, ensure_ascii=False)
    
    # Save individual decks and cards
    for deck in all_decks:
        deck_file = team_output / "cardbox" / "decks" / f"{team_name}-{deck.deck_type}.json"
        deck_file.parent.mkdir(parents=True, exist_ok=True)
        if deck._content:
            with open(deck_file, 'w', encoding='utf-8') as f:
                json.dump(deck._content, f, indent=2, ensure_ascii=False)
        
        # Save individual cards in deck
        for card in deck.cards:
            card_dir = team_output / "cardbox" / "decks" / deck.deck_type
            card_dir.mkdir(parents=True, exist_ok=True)
            card_file = card_dir / f"{team_name}-{card.card_name}.json"
            if card._content:
                with open(card_file, 'w', encoding='utf-8') as f:
                    json.dump(card._content, f, indent=2, ensure_ascii=False)
    
    # Save single cards
    for card in single_cards:
        card_file = team_output / "cardbox" / f"{team_name}-{card.card_type}.json"
        card_file.parent.mkdir(parents=True, exist_ok=True)
        if card._content:
            with open(card_file, 'w', encoding='utf-8') as f:
                json.dump(card._content, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved to {team_output}")
    
    return was_updated


def generate_tts_manifest(metadata: Dict, output_file: Path):
    """
    Generate lightweight manifest for TTS Lua scripts.
    
    Extracts only deck/bag level metadata to avoid choking TTS.
    Format:
    {
      "team_name": {
        "cardbox": {
          "guid": "...",
          "url": "...",
          "content_hash": "...",
          "last_modified": "..."
        },
        "decks": {
          "datacards": {"guid": "...", "url": "...", "content_hash": "...", "last_modified": "..."},
          "equipment": {...}
        },
        "token_bag": {"guid": "...", "url": "...", "content_hash": "...", "last_modified": "..."}
      }
    }
    """
    manifest = {}
    
    for team_name, team_data in metadata.items():
        if 'cardbox' not in team_data:
            continue
        
        cardbox_data = team_data['cardbox']
        team_manifest = {
            'cardbox': {
                'guid': cardbox_data.get('guid', ''),
                'url': cardbox_data.get('url', ''),
                'content_hash': cardbox_data.get('content_hash', ''),
                'last_modified': cardbox_data.get('last_modified', '')
            },
            'decks': {},
            'token_bag': {}
        }
        
        # Extract deck-level metadata (skip individual cards)
        metadata_fields = {'guid', 'url', 'component_type', 'content_hash', 'last_modified'}
        for key, value in cardbox_data.items():
            if key in metadata_fields or key == 'token-bag':
                continue
            
            if isinstance(value, dict) and value.get('component_type') == 'deck':
                team_manifest['decks'][key] = {
                    'guid': value.get('guid', ''),
                    'url': value.get('url', ''),
                    'content_hash': value.get('content_hash', ''),
                    'last_modified': value.get('last_modified', '')
                }
        
        # Extract token bag metadata
        if 'token-bag' in cardbox_data:
            token_bag = cardbox_data['token-bag']
            team_manifest['token_bag'] = {
                'guid': token_bag.get('guid', ''),
                'url': token_bag.get('url', ''),
                'content_hash': token_bag.get('content_hash', ''),
                'last_modified': token_bag.get('last_modified', '')
            }
        
        manifest[team_name] = team_manifest
    
    # Save manifest
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ TTS manifest saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate TTS objects from extracted cards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--force', action='store_true',
                       help='Force regeneration even if unchanged')
    
    args = parser.parse_args()
    
    # Setup paths
    workspace_dir = Path(__file__).parent.parent.parent.parent
    output_dir = workspace_dir / 'output'
    metadata_file = output_dir / '.tts-metadata.json'
    manifest_file = output_dir / '.tts-manifest.json'
    
    # Initialize change detection
    detector = ChangeDetector(metadata_file)
    registry = ComponentRegistry(detector)
    
    print("=" * 60)
    print("TTS Object Generation - Warcom Pipeline")
    print("=" * 60)
    
    # Find teams to process
    if args.teams:
        teams = [output_dir / team for team in args.teams if (output_dir / team).exists()]
    else:
        teams = find_all_teams(output_dir)
    
    if not teams:
        print("\n⚠ No teams found to process")
        return
    
    print(f"\nFound {len(teams)} team(s) to process")
    
    # Process each team
    updated_count = 0
    for team_dir in teams:
        try:
            was_updated = generate_team_tts(team_dir, output_dir, registry)
            if was_updated:
                updated_count += 1
        except Exception as e:
            print(f"\n✗ Error processing {team_dir.name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Save metadata
    detector.save_metadata()
    print(f"\n✓ Full metadata saved to {metadata_file}")
    
    # Generate lightweight manifest for TTS
    generate_tts_manifest(detector.metadata, manifest_file)
    
    # Summary
    print("\n" + "=" * 60)
    print("Generation Complete")
    print("=" * 60)
    print(f"Teams processed: {len(teams)}")
    print(f"Teams updated: {updated_count}")
    print(f"Output: {output_dir}")
    print(f"Metadata: {metadata_file}")
    print(f"Manifest: {manifest_file}")


if __name__ == '__main__':
    main()
