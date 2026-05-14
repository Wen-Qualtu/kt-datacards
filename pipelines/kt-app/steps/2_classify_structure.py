"""
Step 2: Classify Datacard Structure

Analyzes extracted single-page datacards and classifies them as fronts or backs,
pairs them together, extracts operative names, and builds a structure mapping.

Input:  layers/kt-app/extracted/{team}/cards/{team}-datacards-page_N.pdf
Output: layers/kt-app/classified/{team}/structure.json
        layers/kt-app/metadata.json (updated)

Structure JSON Format (uniform pages array):
{
  "team": "kasrkin",
  "total_pages": 11,
  "cards": [
    {
      "card_number": 1,
      "operative_name": "KASRKIN SERGEANT",
      "pages": [
        {"type": "front", "page_in_card": 1, "path": "layers/...page_0.pdf"},
        {"type": "back", "page_in_card": 2, "path": "layers/...page_1.pdf"}
      ]
    },
    {
      "card_number": 2,
      "operative_name": "KASRKIN TROOPER",
      "pages": [
        {"type": "front", "page_in_card": 1, "path": "layers/...page_2.pdf"}
      ]
    },
    {
      "card_number": 3,
      "operative_name": "CHRONOMANCER",
      "pages": [
        {"type": "front", "page_in_card": 1, "path": "layers/...page_0.pdf"},
        {"type": "back", "page_in_card": 2, "path": "layers/...page_1.pdf"},
        {"type": "back", "page_in_card": 3, "path": "layers/...page_2.pdf"}
      ]
    }
  ]
}

Usage:
    python pipelines/kt-app/steps/2_classify_structure.py
    python pipelines/kt-app/steps/2_classify_structure.py --teams kasrkin,blooded
    python pipelines/kt-app/steps/2_classify_structure.py --force
"""

import argparse
import json
import hashlib
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF


# ===================================================================
# LOGGING SETUP
# ===================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ===================================================================
# CONSTANTS
# ===================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
LAYERS_DIR = PROJECT_ROOT / "layers" / "kt-app"
EXTRACTED_DIR = LAYERS_DIR / "extracted"
CLASSIFIED_DIR = LAYERS_DIR / "classified"
METADATA_FILE = LAYERS_DIR / "metadata.json"


# ===================================================================
# TOKEN EXTRACTOR IMPORT
# ===================================================================

# Add script directory to path for TokenExtractor import
SCRIPT_DIR = PROJECT_ROOT / "script"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from tools.extract_tokens import TokenExtractor
    TOKEN_EXTRACTION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"TokenExtractor not available: {e}")
    TOKEN_EXTRACTION_AVAILABLE = False
    TokenExtractor = None


# ===================================================================
# METADATA MANAGER
# ===================================================================

class MetadataManager:
    """Manages pipeline metadata with hash-based change detection"""
    
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load existing metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "pipeline_version": "2.0",
            "last_full_run": None,
            "teams": {}
        }
    
    def save_metadata(self):
        """Save metadata to file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def has_source_changed(self, team: str, step: str) -> bool:
        """Check if source files have changed since last run"""
        if team not in self.metadata.get("teams", {}):
            return True
        if "steps" not in self.metadata["teams"][team]:
            return True
        if step not in self.metadata["teams"][team]["steps"]:
            return True
        if "completed" not in self.metadata["teams"][team]["steps"][step]:
            return True
        
        # Check if previous step (1_process) has newer completion time
        prev_step = "1_process"
        if prev_step not in self.metadata["teams"][team].get("steps", {}):
            return True
        
        prev_completed = self.metadata["teams"][team]["steps"][prev_step].get("completed")
        current_completed = self.metadata["teams"][team]["steps"][step].get("completed")
        
        if not prev_completed:
            return True
        if not current_completed:
            return True
        
        # If previous step is newer, we need to rerun
        return prev_completed > current_completed
    
    def update_file(self, team: str, step: str, file_key: str, file_path: Path):
        """Update metadata for a file"""
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {"outputs": {}}
        if "outputs" not in self.metadata["teams"][team]["steps"][step]:
            self.metadata["teams"][team]["steps"][step]["outputs"] = {}
        
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        
        self.metadata["teams"][team]["steps"][step]["outputs"][file_key] = {
            "path": str(file_path),
            "hash": file_hash,
            "modified": timestamp
        }
    
    def mark_step_complete(self, team: str, step: str):
        """Mark step as completed"""
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {}
        
        self.metadata["teams"][team]["steps"][step]["completed"] = datetime.now(timezone.utc).isoformat()


# ===================================================================
# SPECIAL CASE DETECTION
# ===================================================================

def is_three_card_special_case(team_name: str, text: str) -> bool:
    """
    Detect 3-card special cases (same front, two different backs).
    
    Teams with 3-card groups:
    - elucidian-starstriders: WARRANT OF TRADE
    - gellerpox-infected: TECHNO-CURSE
    - hunter-clade: DOCTRINA IMPERATIVES
    - pathfinders: MARKERLIGHTS
    """
    text_upper = text.upper()
    
    if team_name == 'elucidian-starstriders' and 'WARRANT OF TRADE' in text_upper:
        return True
    if team_name == 'gellerpox-infected' and 'TECHNO-CURSE' in text_upper:
        return True
    if team_name == 'hunter-clade' and 'DOCTRINA IMPERATIVES' in text_upper:
        return True
    if team_name == 'pathfinders' and 'MARKERLIGHTS' in text_upper:
        return True
    
    return False


def is_four_card_special_case(team_name: str, text: str) -> bool:
    """
    Detect 4-card special cases (two pairs: 0+1, 2+3).
    
    Teams with 4-card groups:
    - angels-of-death: CHAPTER TACTICS
    - warpcoven: BOONS OF TZEENTCH
    """
    text_upper = text.upper()
    
    if team_name == 'angels-of-death' and 'CHAPTER TACTICS' in text_upper:
        return True
    if team_name == 'warpcoven' and 'BOONS OF TZEENTCH' in text_upper:
        return True
    
    return False


# ===================================================================
# PAGE CLASSIFIER
# ===================================================================

class PageClassifier:
    """Classifies datacard pages as fronts or backs and extracts operative names"""
    
    @staticmethod
    def is_front_page(pdf_path: Path) -> bool:
        """
        Check if a page is a front-side datacard (has the NAME weapon header row).
        
        Front pages have the weapon table header: "NAME ATK HIT DMG WR" or "NAME A HIT D WR"
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            
            page = doc[0]
            blocks = page.get_text("dict").get("blocks", [])
            
            for block in blocks:
                if block.get("type") != 0:  # Only text blocks
                    continue
                
                bbox = block["bbox"]
                if bbox[1] < 50:  # Header is typically in top area
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span.get("text", "")
                    
                    # Header can be "NAME ATK HIT DMG WR" or "NAME A HIT D WR"
                    if "NAME" in text and "HIT" in text and "WR" in text:
                        doc.close()
                        return True
            
            doc.close()
            return False
        except Exception as e:
            logger.warning(f"Error checking front page for {pdf_path}: {e}")
            return False
    
    @staticmethod
    def has_multi_card_pattern(pdf_path: Path) -> bool:
        """
        Check if a page has a multi-card pattern like "(CARD 2/3)".
        
        These cards should NOT be paired as front/back pairs.
        """
        import re
        
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            
            page = doc[0]
            text = page.get_text()
            doc.close()
            
            # Normalize whitespace
            text_normalized = ' '.join(text.split())
            
            # Check for pattern: (CARD X/Y)
            return bool(re.search(r'\(CARD\s+\d+/\d+\)', text_normalized))
        except Exception as e:
            logger.warning(f"Error checking multi-card pattern for {pdf_path}: {e}")
            return False
    
    @staticmethod
    def has_continue_on_back(pdf_path: Path) -> bool:
        """
        Check if a front page indicates it continues on the back.
        
        Returns True if text contains continuation indicators like:
        - "CONTINUE ON BACK"
        - "CONTINUE ON OTHER SIDE"
        - "CONTINUES ON OTHER SIDE"
        - "RULES CONTINUE ON OTHER SIDE"
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            
            page = doc[0]
            text = page.get_text()
            doc.close()
            
            # Check for continuation indicators (case-insensitive)
            text_upper = text.upper()
            indicators = [
                "CONTINUE ON BACK",
                "CONTINUE ON OTHER SIDE",
                "CONTINUES ON OTHER SIDE",
                "RULES CONTINUE ON OTHER SIDE"
            ]
            
            return any(indicator in text_upper for indicator in indicators)
        except Exception as e:
            logger.warning(f"Error checking continuation for {pdf_path}: {e}")
            return False
    
    @staticmethod
    def has_own_cards_indicator(pdf_path: Path) -> bool:
        """
        Check if a front page indicates actions/rules are on separate cards.
        
        Returns True if text contains "OWN CARD" or "OWN CARDS" pattern
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            
            page = doc[0]
            text = page.get_text()
            doc.close()
            
            # Check for "OWN CARD" or "OWN CARDS" pattern (e.g., "ACTIONS ARE PRESENTED ON THEIR OWN CARDS")
            text_upper = text.upper()
            return "OWN CARD" in text_upper
        except Exception as e:
            logger.warning(f"Error checking own cards indicator for {pdf_path}: {e}")
            return False
    
    @staticmethod
    def extract_operative_name(pdf_path: Path) -> Optional[str]:
        """
        Extract operative name from datacard front page.
        
        The name is in the top-left corner (x < 60% of page width, y < 15px),
        and is uppercase text between 3-50 characters.
        """
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return None
            
            page = doc[0]
            page_width = page.rect.width
            blocks = page.get_text("dict").get("blocks", [])
            
            for block in blocks:
                if block.get("type") != 0:  # Only text blocks
                    continue
                
                bbox = block["bbox"]
                if bbox[0] < page_width * 0.6 and bbox[1] < 15:
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span.get("text", "")
                    
                    text = text.strip()
                    
                    # Skip header keywords and stat labels
                    if ',' in text or text.upper() in ['NAME', 'ATK', 'HIT', 'DMG', 'WR', 'NOTES:', 'NOTES']:
                        continue
                    if 'ACTIONS' in text.upper():
                        continue
                    
                    # Name should be uppercase, 3-50 chars
                    if text.isupper() and 3 <= len(text) <= 50:
                        # Clean up OCR artifacts and trailing stats
                        # Remove patterns like: 26"5+, 26'5+, 265+, etc. (common OCR errors from stat lines)
                        import re
                        name = re.sub(r'\d+["\']?\d+\+?$', '', text).strip()  # Remove trailing number patterns
                        name = re.sub(r'\d{2,}["\']?\d+[+\-]?$', '', name).strip()  # Remove stat patterns like 26"5+
                        name = name.rstrip('0123456789+"\'-').strip()  # Final cleanup
                        
                        if len(name) >= 3:
                            doc.close()
                            return name
            
            doc.close()
            return None
        except Exception as e:
            logger.warning(f"Error extracting name from {pdf_path}: {e}")
            return None
    
    @staticmethod
    def extract_card_name(pdf_path: Path) -> Optional[str]:
        """
        Extract card name from non-datacard pages (equipment, ploys, faction rules, etc.).
        
        These cards typically have structure:
        Line 1: Team name
        Line 2: Card type label (FACTION EQUIPMENT, STRATEGY PLOY, etc.)
        Line 3: Card name (FOREGRIP, ELIMINATION PATTERN, etc.)
        
        For multi-card rules with "(CARD X/Y)" pattern, appends card number to name.
        Example: "ELITE FIELDCRAFT (CARD 2/3)" → "ELITE FIELDCRAFT-CARD-2"
        
        Returns the third major text line (uppercase, 3-50 chars).
        """
        import re
        
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return None
            
            page = doc[0]
            text = page.get_text()
            doc.close()
            
            # Normalize text for pattern matching
            text_normalized = ' '.join(text.split())
            
            # Check for multi-card pattern: "RULE NAME (CARD X/Y)"
            # Pattern matches: FACTION RULE <NAME> (CARD 2/3)
            card_num_match = re.search(r'FACTION\s+RULE\s+([A-Z\s]+?)\s*\(CARD\s+(\d+)/(\d+)\)', text_normalized)
            if card_num_match:
                rule_name = card_num_match.group(1).strip()
                card_num = card_num_match.group(2)
                # Slugify the rule name and append card number
                cleaned = re.sub(r'[^A-Z0-9\s]', '', rule_name)  # Remove special chars
                cleaned = re.sub(r'\s+', '-', cleaned.strip())    # Replace spaces with hyphens
                cleaned = cleaned.lower()
                return f"{cleaned}-card-{card_num}"
            
            # Split into lines and filter out empty ones
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Keywords that indicate card type labels
            type_keywords = ['FACTION', 'EQUIPMENT', 'PLOY', 'RULE', 'STRATEGY', 'FIREFIGHT', 'OPERATIVES', 'SELECTION']
            
            # Find the first type keyword line (this tells us where team name ends)
            type_line_idx = -1
            for i, line in enumerate(lines):
                if any(kw in line.upper() for kw in type_keywords):
                    type_line_idx = i
                    break
            
            # If no type line found, fall back to old logic
            if type_line_idx == -1:
                for line in lines:
                    if len(line) >= 3 and line.isupper() and 3 <= len(line) <= 50:
                        return line.rstrip('0123456789').strip()
                return None
            
            # Card name should be the first uppercase line AFTER the type line
            for i in range(type_line_idx + 1, len(lines)):
                line = lines[i]
                
                # Skip very short lines
                if len(line) < 3:
                    continue
                
                # Look for uppercase text
                if line.isupper() and 3 <= len(line) <= 50:
                    # Clean up trailing numbers
                    name = line.rstrip('0123456789').strip()
                    if len(name) >= 3:
                        return name
            
            return None
        except Exception as e:
            logger.warning(f"Error extracting card name from {pdf_path}: {e}")
            return None


# ===================================================================
# STRUCTURE CLASSIFIER
# ===================================================================

class StructureClassifier:
    """Classifies datacard pages and builds structure mapping"""
    
    def __init__(self, team: str, extracted_dir: Path):
        self.team = team
        self.extracted_dir = extracted_dir
        self.page_classifier = PageClassifier()
        self._token_guide_pages_cache = None  # Cache for token guide page paths
    
    def _get_token_guide_pages(self) -> set:
        """
        Identify which pages in faction-rules are token guides.
        
        Token guides stay in faction-rules directory but are classified separately.
        Returns set of Path objects for token guide pages.
        """
        if self._token_guide_pages_cache is not None:
            return self._token_guide_pages_cache
        
        token_guide_pages = set()
        faction_rules_dir = self.extracted_dir / self.team / "cards" / "faction-rules"
        
        if not faction_rules_dir.exists():
            self._token_guide_pages_cache = token_guide_pages
            return token_guide_pages
        
        # Check all faction-rules pages for token guide marker
        all_pages = faction_rules_dir.glob(f"{self.team}-faction-rules-page_*.pdf")
        for page_file in all_pages:
            try:
                doc = fitz.open(page_file)
                page = doc[0]
                text = page.get_text()
                doc.close()
                
                if 'MARKER/TOKEN GUIDE' in text:
                    token_guide_pages.add(page_file)
            except Exception as e:
                logger.debug(f"Error checking token guide in {page_file.name}: {e}")
                continue
        
        self._token_guide_pages_cache = token_guide_pages
        
        if token_guide_pages:
            logger.info(f"  Found {len(token_guide_pages)} token-guide pages in faction-rules")
        
        return token_guide_pages
    
    def _extract_token_metadata(self, token_guide_entities: List[Dict]) -> None:
        """
        Extract token text labels from token guide cards for extraction prep.
        
        Extracts text layer from PDF (token names with positions and types).
        Image detection and shape classification are deferred to the token extraction step.
        
        Modifies token_guide_entities in-place to add 'tokens' field.
        """
        if not token_guide_entities:
            return
        
        if not TOKEN_EXTRACTION_AVAILABLE:
            logger.warning("  Token extraction not available - skipping token metadata")
            return
        
        logger.info(f"  Extracting token metadata from {len(token_guide_entities)} token guide(s)")
        
        # Initialize TokenExtractor with temp output dir
        temp_output_dir = PROJECT_ROOT / "layers" / "kt-app" / "_temp_token_extraction"
        temp_output_dir.mkdir(parents=True, exist_ok=True)
        
        extractor = TokenExtractor(output_base_dir=temp_output_dir)
        
        for entity in token_guide_entities:
            cards = entity.get("cards", [])
            if not cards:
                continue
            
            # Prepare token metadata (text layer only)
            token_names = []
            
            # Process each card in the token guide
            for card_data in cards:
                card_number = card_data.get("card_number", 1)
                pdf_path = card_data.get("front")  # Token guides are always front-only
                
                if not pdf_path:
                    continue
                
                # Convert relative path to absolute
                abs_pdf_path = PROJECT_ROOT / pdf_path
                if not abs_pdf_path.exists():
                    logger.warning(f"    Token guide PDF not found: {pdf_path}")
                    continue
                
                try:
                    # Get PDF dimensions and calculate skip region
                    doc = fitz.open(abs_pdf_path)
                    page = doc[0]
                    pdf_height = page.rect.height  # PDF coordinate space (~72 DPI)
                    doc.close()
                    
                    # Calculate skip region in PDF coordinate space
                    skip_percent = 0.15
                    skip_pixels_pdf = int(pdf_height * skip_percent)  # For PDF text filtering
                    
                    # Extract text labels from PDF
                    text_elements = extractor.extract_text_from_pdf(
                        pdf_path=abs_pdf_path,
                        page_num=0,  # Always first page of single-page PDF
                        target_image_path=None
                    )
                    
                    # Filter text elements to only include those below the header skip region
                    # Text coordinates are in PDF space, so compare with skip_pixels_pdf
                    for (x, y), text in text_elements.items():
                        # Skip text in header region (using PDF coordinate space)
                        if y < skip_pixels_pdf:
                            continue
                        
                        # Determine type from text
                        text_lower = text.lower()
                        token_type = "marker" if "marker" in text_lower else "token"
                        
                        token_names.append({
                            "card_number": card_number,
                            "name": text,
                            "type": token_type,
                            "position": {"x": x, "y": y}
                        })
                    
                except Exception as e:
                    logger.warning(f"    Failed to extract token text for card {card_number}: {e}")
                    continue
            
            # Add token metadata to entity
            if token_names:
                entity["tokens"] = {"names": token_names}
                logger.info(f"    Extracted {len(token_names)} token names")
        
        # Clean up temporary extraction directory
        import shutil
        if temp_output_dir.exists():
            shutil.rmtree(temp_output_dir, ignore_errors=True)
    
    def classify(self) -> Optional[Dict]:
        """
        Classify all card types for this team.
        
        Returns structure dict with separate arrays for each card type:
        {
          "team": "kasrkin",
          "datacards": [
            {
              "datacard_number": 1,
              "name": "OPERATIVE NAME",
              "cards": [
                {"card_number": 1, "type": "front", "front": "path.pdf"},
                {"card_number": 2, "type": "both", "front": "path.pdf", "back": "path.pdf"}
              ]
            }
          ],
          "equipment": [...],
          "faction_rules": [...],
          "firefight_ploys": [...],
          "operatives_selection": [...],
          "strategy_ploys": [...]
        }
        """
        cards_dir = self.extracted_dir / self.team / "cards"
        if not cards_dir.exists():
            logger.debug(f"No cards directory for {self.team}")
            return None
        
        structure = {"team": self.team}
        
        # Card types to process (matching CardType enum from Step 1)
        card_types = [
            ("datacards", "datacards"),
            ("equipment", "equipment"),
            ("faction-rules", "faction_rules"),
            ("token-guide", "token_guide"),
            ("firefight-ploys", "firefight_ploys"),
            ("operatives-selection", "operatives_selection"),
            ("strategy-ploys", "strategy_ploys")
        ]
        
        total_entities = 0
        for file_prefix, key in card_types:
            result = self._classify_card_type(file_prefix, key)
            if result:
                # Extract token metadata for token guides
                if key == "token_guide":
                    self._extract_token_metadata(result)
                
                structure[key] = result
                total_entities += len(result)
        
        if total_entities > 0:
            logger.info(f"    Classified {total_entities} entities across all types")
            return structure
        else:
            logger.debug(f"No cards found for {self.team}")
            return None
    
    def _classify_card_type(self, file_prefix: str, card_type_key: str) -> Optional[List]:
        """
        Classify pages for a specific card type (datacards, equipment, faction-rules, etc.).
        
        Card Grouping Logic:
        - If page has "OWN CARDS" text → following pages are sub-cards of this group
        - For each page, check if it has "CONTINUE ON BACK" → next page is its back
        - Each card can have max 2 pages (1 front + optional 1 back)
        - Group continues until we hit a new named card
        
        Structure Format:
        [
          {
            "{type}_number": 1,
            "name": "ENTITY NAME",
            "cards": [
              {"card_number": 1, "type": "front", "front": "path.pdf"},
              {"card_number": 2, "type": "both", "front": "path.pdf", "back": "path.pdf"}
            ]
          }
        ]
        
        Returns array of entity objects or None if no pages found.
        """
        # Mapping for number property names (type_key -> singular_number)
        number_prop_names = {
            "datacards": "datacard_number",
            "equipment": "equipment_number",
            "faction_rules": "faction_rule_number",
            "token_guide": "token_guide_number",
            "firefight_ploys": "ploy_number",
            "operatives_selection": "operative_selection_number",
            "strategy_ploys": "ploy_number"
        }
        # Updated to use type subdirectories
        type_dir = self.extracted_dir / self.team / "cards" / file_prefix
        
        # Special handling for token-guide: read from faction-rules directory
        if file_prefix == "token-guide":
            type_dir = self.extracted_dir / self.team / "cards" / "faction-rules"
            if not type_dir.exists():
                return None
            
            # Get only token guide pages
            token_guide_pages = self._get_token_guide_pages()
            if not token_guide_pages:
                return None
            
            all_page_files = sorted(token_guide_pages)
        else:
            if not type_dir.exists():
                return None
            
            # Find all pages for this card type
            all_page_files = list(type_dir.glob(f"{self.team}-{file_prefix}-page_*.pdf"))
            
            # Special handling for faction-rules: exclude token guide pages
            if file_prefix == "faction-rules":
                token_guide_pages = self._get_token_guide_pages()
                all_page_files = [f for f in all_page_files if f not in token_guide_pages]
            
            all_page_files = sorted(all_page_files)
        
        if not all_page_files:
            return None
        
        # Sort by page number for correct PDF order
        all_page_files.sort(key=lambda f: int(f.stem.split('_')[-1]))
        
        logger.info(f"  Processing {len(all_page_files)} {file_prefix} pages")
        
        # Phase 1: Identify "first" pages and extract names
        # For datacards: check for weapon header (only fronts are "first")
        # For others: extract name from all pages to enable grouping
        is_datacard_type = file_prefix == "datacards"
        is_operative_selection = file_prefix == "operatives-selection"
        is_token_guide = file_prefix == "token-guide"
        
        first_pages = []
        first_positions = set()
        
        for pos, page_file in enumerate(all_page_files):
            if is_datacard_type:
                # Datacards: only fronts are first pages
                if not self.page_classifier.is_front_page(page_file):
                    continue
                name = self.page_classifier.extract_operative_name(page_file)
            elif is_operative_selection:
                # Operative selection: use default name based on team
                team_name = self.team.replace('-', ' ').title()
                name = f"OPERATIVE SELECTION {team_name.upper()}"
            elif is_token_guide:
                # Token guide: use default name based on team
                team_name = self.team.replace('-', ' ').title()
                name = f"TOKEN GUIDE {team_name.upper()}"
            else:
                # Other card types: extract name to enable grouping by name
                name = self.page_classifier.extract_card_name(page_file)
            
            has_own_cards = self.page_classifier.has_own_cards_indicator(page_file)
            has_continue = self.page_classifier.has_continue_on_back(page_file)
            
            rel_path = page_file.relative_to(PROJECT_ROOT)
            first_pages.append({
                "position": pos,
                "path": str(rel_path).replace('\\', '/'),
                "name": name,
                "has_own_cards": has_own_cards,
                "has_continue": has_continue
            })
            first_positions.add(pos)
        
        if is_datacard_type:
            logger.info(f"    Found {len(first_pages)} front pages (operatives)")
        else:
            logger.info(f"    Processing {len(all_page_files)} pages")
        
        # Phase 2: Build card groups with pairing logic
        cards = []
        processed_positions = set()
        
        # Check for special cases before normal processing
        if len(first_pages) > 0:
            first_page_text = ""
            try:
                doc = fitz.open(all_page_files[first_pages[0]["position"]])
                first_page_text = doc[0].get_text()
                doc.close()
            except:
                pass
            
            # 4-card special case: pairs (0,1) and (2,3)
            # NOTE: Only apply to non-datacard types. Datacard pages often reference
            # faction rule names in ability text, causing false positives.
            if not is_datacard_type and is_four_card_special_case(self.team, first_page_text):
                if len(all_page_files) >= 4:
                    logger.info(f"    Special case: 4-card group detected")
                    
                    # Extract name from first page (all pairs use this name)
                    first_file = all_page_files[0]
                    if is_datacard_type:
                        card_name = self.page_classifier.extract_operative_name(first_file)
                    elif is_operative_selection:
                        team_name = self.team.replace('-', ' ').title()
                        card_name = f"OPERATIVE SELECTION {team_name.upper()}"
                    elif is_token_guide:
                        team_name = self.team.replace('-', ' ').title()
                        card_name = f"TOKEN GUIDE {team_name.upper()}"
                    else:
                        card_name = self.page_classifier.extract_card_name(first_file)
                    
                    # Create two paired cards from first 4 pages
                    for pair_idx in range(2):
                        front_idx = pair_idx * 2
                        back_idx = front_idx + 1
                        
                        if front_idx >= len(all_page_files) or back_idx >= len(all_page_files):
                            break
                        
                        front_file = all_page_files[front_idx]
                        back_file = all_page_files[back_idx]
                        front_path = str(front_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                        back_path = str(back_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                        
                        card_pages = [{
                            "type": "both",
                            "card_in_group": pair_idx + 1,
                            "front": front_path,
                            "back": back_path
                        }]
                        
                        # Both cards use the same name from first page
                        cards.append({
                            "card_number": len(cards) + 1,
                            "name": card_name,
                            "pages": card_pages
                        })
                        
                        processed_positions.add(front_idx)
                        processed_positions.add(back_idx)
                    
                    # Continue processing remaining pages normally
            
            # 3-card special case: same front with 2 different backs
            # NOTE: Only apply to non-datacard types. Datacard pages often reference
            # faction rule names in ability text, causing false positives.
            elif not is_datacard_type and is_three_card_special_case(self.team, first_page_text):
                if len(all_page_files) >= 3:
                    logger.info(f"    Special case: 3-card group detected")
                    
                    front_file = all_page_files[0]
                    back1_file = all_page_files[1]
                    back2_file = all_page_files[2]
                    
                    front_path = str(front_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                    back1_path = str(back1_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                    back2_path = str(back2_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                    
                    # Extract name from front page
                    if is_datacard_type:
                        name = self.page_classifier.extract_operative_name(front_file)
                    elif is_operative_selection:
                        team_name = self.team.replace('-', ' ').title()
                        name = f"OPERATIVE SELECTION {team_name.upper()}"
                    elif is_token_guide:
                        team_name = self.team.replace('-', ' ').title()
                        name = f"TOKEN GUIDE {team_name.upper()}"
                    else:
                        name = self.page_classifier.extract_card_name(front_file)
                    
                    # Create first card: front + back1
                    cards.append({
                        "card_number": 1,
                        "name": name,
                        "pages": [{
                            "type": "both",
                            "card_in_group": 1,
                            "front": front_path,
                            "back": back1_path
                        }]
                    })
                    
                    # Create second card: front + back2
                    cards.append({
                        "card_number": 2,
                        "name": f"{name}-2",
                        "pages": [{
                            "type": "both",
                            "card_in_group": 1,
                            "front": front_path,
                            "back": back2_path
                        }]
                    })
                    
                    processed_positions.add(0)
                    processed_positions.add(1)
                    processed_positions.add(2)
                    
                    # Continue processing remaining pages normally
        
        # Use unified logic for all card types since we now have names for all
        for i, first_page in enumerate(first_pages):
            # Skip if already processed as part of a group
            if first_page["position"] in processed_positions:
                continue
            
            card_name = first_page["name"]
            card_pages = []
            
            # Determine if this page starts a group (has "OWN CARDS" indicator)
            if first_page["has_own_cards"]:
                # Group mode: collect ALL pages with same name (datacards) or until next OWN CARDS (non-datacards)
                group_start = first_page["position"]
                
                # Find group end
                group_end = len(all_page_files)
                
                if is_datacard_type:
                    # Datacards: group by matching operative name
                    for j in range(i + 1, len(first_pages)):
                        next_first = first_pages[j]
                        if next_first["name"] != card_name:
                            group_end = next_first["position"]
                            break
                else:
                    # Non-datacards: group until next OWN CARDS indicator (option pages may have different names)
                    for j in range(i + 1, len(first_pages)):
                        next_first = first_pages[j]
                        if next_first["has_own_cards"]:
                            group_end = next_first["position"]
                            break
                
                # Process all pages in this range
                pos = group_start
                card_in_group = 1
                
                while pos < group_end:
                    if pos in processed_positions:
                        pos += 1
                        continue
                    
                    page_file = all_page_files[pos]
                    front_path = str(page_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                    
                    # Check if this page has continuation text
                    has_continue = self.page_classifier.has_continue_on_back(page_file)
                    
                    if has_continue and pos + 1 < group_end:
                        # Check if both pages have multi-card pattern (CARD X/Y)
                        # If so, they should NOT be paired (each is a separate card)
                        current_has_card_num = self.page_classifier.has_multi_card_pattern(page_file)
                        next_has_card_num = False
                        if pos + 1 < len(all_page_files):
                            next_file = all_page_files[pos + 1]
                            next_has_card_num = self.page_classifier.has_multi_card_pattern(next_file)
                        
                        # Don't pair if both have card numbers
                        if current_has_card_num and next_has_card_num:
                            # Standalone page (part of multi-card sequence)
                            card_pages.append({
                                "type": "front",
                                "card_in_group": card_in_group,
                                "front": front_path
                            })
                            processed_positions.add(pos)
                            pos += 1
                            card_in_group += 1
                            continue
                        
                        # Check if next page is NOT a first (would be the back)
                        if (pos + 1) not in first_positions or not is_datacard_type:
                            back_file = all_page_files[pos + 1]
                            back_path = str(back_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                            
                            card_pages.append({
                                "type": "both",
                                "card_in_group": card_in_group,
                                "front": front_path,
                                "back": back_path
                            })
                            processed_positions.add(pos)
                            processed_positions.add(pos + 1)
                            pos += 2
                            card_in_group += 1
                            continue
                    
                    # Standalone page
                    card_pages.append({
                        "type": "front",
                        "card_in_group": card_in_group,
                        "front": front_path
                    })
                    processed_positions.add(pos)
                    pos += 1
                    card_in_group += 1
            else:
                # Single card mode: just this page + optional back
                front_path = first_page["path"]
                processed_positions.add(first_page["position"])
                
                if first_page["has_continue"]:
                    # Check if next page is available
                    next_pos = first_page["position"] + 1
                    if next_pos < len(all_page_files):
                        # Check if both pages have multi-card pattern (CARD X/Y)
                        current_file = all_page_files[first_page["position"]]
                        current_has_card_num = self.page_classifier.has_multi_card_pattern(current_file)
                        next_file = all_page_files[next_pos]
                        next_has_card_num = self.page_classifier.has_multi_card_pattern(next_file)
                        
                        # Don't pair if both have card numbers
                        if current_has_card_num and next_has_card_num:
                            card_pages.append({
                                "type": "front",
                                "card_in_group": 1,
                                "front": front_path
                            })
                        else:
                            # For datacards, check if next page is not a front
                            # For non-datacards, always pair
                            can_pair = not is_datacard_type or next_pos not in first_positions
                            if can_pair:
                                back_file = all_page_files[next_pos]
                                back_path = str(back_file.relative_to(PROJECT_ROOT)).replace('\\', '/')
                                
                                card_pages.append({
                                    "type": "both",
                                    "card_in_group": 1,
                                    "front": front_path,
                                    "back": back_path
                                })
                                processed_positions.add(next_pos)
                            else:
                                card_pages.append({
                                    "type": "front",
                                    "card_in_group": 1,
                                    "front": front_path
                                })
                    else:
                        card_pages.append({
                            "type": "front",
                            "card_in_group": 1,
                            "front": front_path
                        })
                else:
                    card_pages.append({
                        "type": "front",
                        "card_in_group": 1,
                        "front": front_path
                    })
            
            # Add card to list (name first after card_number)
            if card_pages:
                cards.append({
                    "card_number": len(cards) + 1,
                    "name": card_name,
                    "pages": card_pages
                })
        
        # Transform to object-based structure:
        # Group cards by name into parent objects
        # Each parent object represents a logical entity (rule, equipment, operative, etc.)
        # and contains one or more physical cards
        
        grouped_entities = []
        current_entity = None
        
        for card in cards:
            card_name = card["name"]
            
            # Check if this card belongs to the current entity
            if current_entity is None or current_entity["name"] != card_name:
                # Start new entity
                if current_entity is not None:
                    grouped_entities.append(current_entity)
                
                # Get the appropriate number property name
                number_prop = number_prop_names.get(card_type_key, f"{card_type_key}_number")
                
                current_entity = {
                    number_prop: len(grouped_entities) + 1,
                    "name": card_name,
                    "cards": []
                }
            
            # Flatten card pages and add to entity
            for page_data in card["pages"]:
                flattened_card = {
                    "card_number": len(current_entity["cards"]) + 1,
                    "type": page_data["type"]
                }
                
                # Add front and back paths
                if "front" in page_data:
                    flattened_card["front"] = page_data["front"]
                if "back" in page_data:
                    flattened_card["back"] = page_data["back"]
                
                current_entity["cards"].append(flattened_card)
        
        # Add final entity
        if current_entity is not None:
            grouped_entities.append(current_entity)
        
        logger.info(f"    Classified {len(grouped_entities)} {file_prefix}")
        
        return grouped_entities


# ===================================================================
# MAIN PIPELINE
# ===================================================================

def run(teams: Optional[List[str]] = None, force: bool = False):
    """
    Run Step 2: Classify Structure
    
    Args:
        teams: Optional list of team names to process (default: all)
        force: If True, reprocess even if up to date
    """
    logger.info("Step 2: Classify Structure")
    logger.info("")
    
    # Load metadata
    metadata_manager = MetadataManager(METADATA_FILE)
    
    # Find teams to process
    if teams:
        team_dirs = [EXTRACTED_DIR / team for team in teams if (EXTRACTED_DIR / team).exists()]
    else:
        team_dirs = sorted([d for d in EXTRACTED_DIR.iterdir() if d.is_dir()])
    
    if not team_dirs:
        logger.error("No teams found in extracted directory")
        return
    
    logger.info(f"Processing {len(team_dirs)} teams")
    logger.info("")
    
    # Statistics
    stats = {
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'total_cards': 0
    }
    
    # Process each team
    for team_dir in team_dirs:
        team = team_dir.name
        logger.info(f"Processing: {team}")
        
        # Check if needs processing
        if not force and not metadata_manager.has_source_changed(team, "2_classify"):
            logger.info(f"  Skipped: No changes detected")
            stats['skipped'] += 1
            continue
        
        # Run classification
        try:
            classifier = StructureClassifier(team, EXTRACTED_DIR)
            structure = classifier.classify()
            
            if not structure:
                logger.info(f"  Skipped: No datacards found")
                stats['skipped'] += 1
                continue
            
            # Save structure.json
            output_dir = CLASSIFIED_DIR / team
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "structure.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)
            
            logger.info(f"  Saved: {output_file}")
            
            # Update metadata
            metadata_manager.update_file(team, "2_classify", "structure.json", output_file)
            metadata_manager.mark_step_complete(team, "2_classify")
            
            stats['processed'] += 1
            # Count total physical cards from all entities
            for key in ["datacards", "equipment", "faction_rules", "firefight_ploys", "operatives_selection", "strategy_ploys"]:
                if key in structure:
                    # structure[key] is now an array of entities
                    for entity in structure[key]:
                        stats['total_cards'] += len(entity["cards"])
            
        except Exception as e:
            logger.error(f"  Failed: {e}", exc_info=True)
            stats['failed'] += 1
    
    # Save metadata
    metadata_manager.metadata["last_full_run"] = datetime.now(timezone.utc).isoformat()
    metadata_manager.save_metadata()
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("Step 2 Complete!")
    logger.info(f"  Processed: {stats['processed']}")
    logger.info(f"  Total cards: {stats['total_cards']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Step 2: Classify datacard structure")
    parser.add_argument("--teams", help="Comma-separated team names to process")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if up to date")
    args = parser.parse_args()
    
    teams = None
    if args.teams:
        teams = [t.strip() for t in args.teams.split(',')]
    
    run(teams=teams, force=args.force)


if __name__ == "__main__":
    main()
