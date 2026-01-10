"""Metadata generation for processed output tracking"""
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import yaml
import re
from PIL import Image
import pytesseract


class OutputMetadataGenerator:
    """Generates metadata YAML file tracking processed output"""
    
    # Card type folder names to YAML keys mapping
    CARD_TYPE_MAPPING = {
        'faction-rules': 'faction-rules',
        'strategy-ploys': ('ploys', 'strategy'),
        'firefight-ploys': ('ploys', 'firefight'),
        'equipment': 'equipment',
        'operatives': 'operative_selection',
        'datacards': 'datacards'
    }
    
    def __init__(
        self,
        output_dir: Path = Path('output'),
        config_dir: Path = Path('config')
    ):
        """
        Initialize OutputMetadataGenerator
        
        Args:
            output_dir: Base output directory containing team folders
            config_dir: Config directory with team-name-mapping.yaml
        """
        self.output_dir = Path(output_dir)
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger(__name__)
        self.team_mapping = self._load_team_mapping()
    
    def _load_team_mapping(self) -> Dict[str, str]:
        """Load team name mapping from config"""
        mapping_file = self.config_dir / 'team-name-mapping.yaml'
        if not mapping_file.exists():
            self.logger.warning(f"Team mapping file not found: {mapping_file}")
            return {}
        
        with open(mapping_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('teams', {})
    
    def _extract_card_name_from_image(self, image_path: Path, card_type: str = None, team_slug: str = None) -> str:
        """
        Extract card name from filename (the filename was already extracted from the PDF 
        using the proven method from extract_pages.py, so we just use it)
        
        Args:
            image_path: Path to card image
            card_type: Type of card (for special handling)
            team_slug: Team slug (for detecting problematic patterns)
            
        Returns:
            Card name from filename
        """
        # The filenames in output/ were already created using proper PDF text extraction
        # in extract_pages.py, so they're already correct. Just use them!
        filename_base = image_path.stem.replace('_front', '')
        
        # Detect problematic generic filenames that indicate extraction failure
        # These are cases where the PDF extraction couldn't find a proper card name
        generic_names = ['operatives', 'kill-team', 'faction-rule', 'markertoken-guide']
        
        # Check if filename matches team name (extraction grabbed team name instead of card name)
        # Handle both exact match and singular/plural variants
        if team_slug:
            filename_normalized = filename_base.replace('-', '').replace('_', '').lower()
            team_normalized = team_slug.replace('-', '').replace('_', '').lower()
            
            # Check for exact match
            if filename_normalized == team_normalized:
                self.logger.warning(f"Card name matches team name for {image_path.name} - extraction issue")
                return f"[NEEDS REVIEW] {filename_base.replace('-', ' ').title()}"
            
            # Check if adding 's' to filename matches team (angel vs angels)
            if filename_normalized + 's' == team_normalized:
                self.logger.warning(f"Card name matches team name for {image_path.name} - extraction issue")
                return f"[NEEDS REVIEW] {filename_base.replace('-', ' ').title()}"
            
            # Check for plural/singular in compound words (angels-of-death vs angel-of-death)
            # Compare word-by-word
            filename_words = filename_base.split('-')
            team_words = team_slug.split('-')
            if len(filename_words) == len(team_words):
                # Check if only difference is plural 's' on one word
                differences = 0
                for fw, tw in zip(filename_words, team_words):
                    if fw == tw:
                        continue
                    elif fw + 's' == tw or (tw.endswith('s') and tw[:-1] == fw):
                        differences += 1
                    else:
                        differences = 999  # Different words entirely
                        break
                
                if differences == 1:  # Only one word differs by plural
                    self.logger.warning(f"Card name matches team name (plural variant) for {image_path.name} - extraction issue")
                    return f"[NEEDS REVIEW] {filename_base.replace('-', ' ').title()}"
        
        # Check for generic names
        if filename_base in generic_names:
            self.logger.warning(f"Generic filename detected: {image_path.name} - extraction issue")
            return filename_base.replace('-', ' ').title()
        
        # Check if filename starts with numbers (like "7-sharpshooter" from Angels of Death)
        # These are page numbers that shouldn't be in the card name
        if filename_base and filename_base[0].isdigit():
            # Remove leading numbers and hyphens
            import re
            filename_base = re.sub(r'^\d+-', '', filename_base)
            self.logger.debug(f"Removed page number prefix from {image_path.name}")
        
        return filename_base.replace('-', ' ').title()
    
    def _parse_operative_selection(self, front_image: Path) -> Dict[str, Any]:
        """
        Parse operative selection card to extract roster building rules
        
        Args:
            front_image: Path to operative selection front image
            
        Returns:
            Dict with total, options, and notes
        """
        try:
            # Extract text from card using OCR
            img = Image.open(front_image)
            text = pytesseract.image_to_string(img)
            
            self.logger.debug(f"Extracted text from {front_image.name}:\n{text}")
            
            # Parse the roster structure
            # Format is typically:
            # N <number> <operative name>
            # operative
            # OR
            # N <number> <operative name> operatives selected from the
            # following list:
            #   e <operative option>
            
            total_slots = 0
            options = []
            notes_lines = []
            
            lines = text.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines
                if not line:
                    i += 1
                    continue
                
                # Skip header lines (but not roster lines that contain these words)
                if line.upper() in ['OPERATIVES', 'KILL TEAM'] or 'ARCHETYPES' in line.upper():
                    i += 1
                    continue
                
                # Check for operative count lines (N <number> <name>)
                # May be split across lines with "operative" or "operatives" on next line
                match = re.match(r'^[NU]\s*[.:]?\s*(\d+)\s+(.+)', line, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                    name = match.group(2).strip()
                    
                    # Check next line for "operative" or "operatives selected from"
                    next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
                    
                    # Case 1: Just "operative" on next line (mandatory operative)
                    if next_line.lower() == 'operative':
                        total_slots += count
                        # Clean up name (remove trademark symbols, etc.)
                        clean_name = re.sub(r'[®©]', '', name).strip()
                        options.append({
                            'name': clean_name,
                            'max': count,
                            'mandatory': True
                        })
                        i += 2  # Skip current + "operative" line
                        continue
                    
                    # Case 2: "operative with" on same line (mandatory with weapon choices)
                    if 'operative with' in line.lower():
                        total_slots += count
                        # Extract name before "operative with"
                        name_match = re.match(r'^[NU]\s*[.:]?\s*\d+\s+(.+?)\s+operative\s+with', line, re.IGNORECASE)
                        if name_match:
                            clean_name = re.sub(r'[®©@]', '', name_match.group(1)).strip()
                            options.append({
                                'name': clean_name,
                                'max': count,
                                'mandatory': True
                            })
                        i += 1  # Skip to next line (weapon options will be skipped)
                        continue
                    
                    # Case 3: "operatives selected from" (may be same line or next line)
                    combined = line + ' ' + next_line
                    if 'operatives selected from' in combined.lower() or 'following list' in next_line.lower():
                        # This is a selection pool
                        total_slots += count
                        
                        # Skip to the option lines
                        i += 2  # Skip "N X operatives..." and "following list:" lines
                        
                        # Parse options (lines starting with 'e' or '©' or '°', or all-caps operative names)
                        while i < len(lines):
                            option_line = lines[i].strip()
                            
                            # Check if it's an option bullet
                            if option_line.startswith(('e ', '© ', '° ')):
                                # Extract operative name (before "with")
                                option_text = option_line[2:].strip()  # Remove bullet
                                
                                # Parse operative name (everything before "with" or end)
                                operative_match = re.match(r'^([A-Z][A-Z\s&-]+?)(?:\s+with|$)', option_text)
                                if operative_match:
                                    operative_name = operative_match.group(1).strip()
                                    
                                    # Check if this operative already exists (avoid duplicates for weapon variants)
                                    if not any(opt['name'] == operative_name for opt in options):
                                        options.append({
                                            'name': operative_name,
                                            'max': count  # Pool size
                                        })
                                
                                i += 1
                            elif option_line.startswith(('N', 'U')) and any(c.isdigit() for c in option_line):
                                # Hit another operative section
                                break
                            elif re.match(r'^[A-Z][A-Z\s&-]+(?:\s+with|$)', option_line):
                                # All-caps operative name (bullets may be missing due to OCR)
                                # Parse operative name (everything before "with" or end)
                                operative_match = re.match(r'^([A-Z][A-Z\s&-]+?)(?:\s+with|$)', option_line)
                                if operative_match:
                                    operative_name = operative_match.group(1).strip()
                                    
                                    # Check if this operative already exists
                                    if not any(opt['name'] == operative_name for opt in options):
                                        options.append({
                                            'name': operative_name,
                                            'max': count  # Pool size
                                        })
                                
                                i += 1
                            elif not option_line or option_line.startswith(('©', 'o')):
                                # Sub-options or empty, skip
                                i += 1
                            else:
                                i += 1
                        
                        continue  # Don't increment i again
                
                i += 1
            
            # Build notes
            notes = f"Roster: {total_slots} operatives total. See card for weapon options and constraints."
            
            return {
                'total': total_slots,
                'options': options,
                'notes': notes
            }
            
        except Exception as e:
            self.logger.error(f"Failed to parse operative selection from {front_image}: {e}")
            import traceback
            self.logger.debug(traceback.format_exc())
            # Return fallback structure
            return {
                'total': 0,
                'options': [],
                'notes': "Failed to parse operative selection - needs manual review"
            }
    
    def _get_canonical_name(self, team_slug: str) -> str:
        """
        Get canonical team name from slug
        
        Args:
            team_slug: Team folder name (e.g., 'kasrkin')
            
        Returns:
            Canonical team name
        """
        # Check mapping file first
        if team_slug in self.team_mapping:
            return self.team_mapping[team_slug]
        
        # Fallback: convert slug to title case
        return team_slug.replace('-', ' ').title()
    
    def _scan_card_type_folder(self, folder_path: Path, team_slug: str = None) -> Dict[str, Any]:
        """
        Scan a card type folder and extract card information
        
        Args:
            folder_path: Path to card type folder (e.g., output/kasrkin/datacards/)
            team_slug: Team identifier for context
            
        Returns:
            Dict with count and cards list, or special structure for operative_selection
        """
        # Find all front images (avoid counting front/back separately)
        front_images = sorted(folder_path.glob('*_front.jpg'))
        
        # Extract card type from folder name
        card_type = folder_path.name
        
        # Special handling for operative_selection
        if card_type == 'operatives':
            # operative_selection has a different structure: total, options, notes
            if len(front_images) == 0:
                self.logger.warning(f"No operative selection cards found in {folder_path}")
                return {
                    'total': 0,
                    'options': [],
                    'notes': 'No operative selection card found',
                    'card_count': 0  # Track number of cards for total_cards calculation
                }
            
            # Parse all operative selection cards and merge
            total = 0
            all_options = []
            all_notes = []
            
            for front_image in front_images:
                parsed = self._parse_operative_selection(front_image)
                total += parsed.get('total', 0)
                
                # Merge options with deduplication
                for new_opt in parsed.get('options', []):
                    # Check if this operative name already exists
                    existing = next((opt for opt in all_options if opt['name'] == new_opt['name']), None)
                    if existing:
                        # Update max if new value is different (keep higher value for pools)
                        if new_opt.get('max', 0) > existing.get('max', 0):
                            existing['max'] = new_opt['max']
                        # Preserve mandatory flag if either has it
                        if new_opt.get('mandatory', False):
                            existing['mandatory'] = True
                    else:
                        all_options.append(new_opt)
                
                all_notes.append(parsed.get('notes', ''))
            
            return {
                'total': total,
                'options': all_options,
                'notes': ' '.join(all_notes),
                'card_count': len(front_images)  # Track number of cards
            }
        
        # Regular card type handling
        cards = []
        for front_image in front_images:
            # Extract name from filename (already correctly extracted from PDF during processing)
            card_name = self._extract_card_name_from_image(front_image, card_type, team_slug)
            
            cards.append({
                'name': card_name,
                'description': '...'  # Placeholder
            })
        
        return {
            'count': len(cards),
            'cards': cards
        }
    
    def _scan_team_folder(self, team_path: Path) -> Dict[str, Any]:
        """
        Scan a team folder and generate metadata
        
        Args:
            team_path: Path to team folder (e.g., output/kasrkin/)
            
        Returns:
            Team metadata dict
        """
        team_slug = team_path.name
        canonical_name = self._get_canonical_name(team_slug)
        
        self.logger.info(f"Scanning team: {canonical_name} ({team_slug})")
        
        metadata = {
            'canonical_name': canonical_name,
            'faction': 'Unknown',  # TODO: Add faction detection
            'subfaction': 'Unknown',
            'last_processed': datetime.now().isoformat(),
            'source_pdfs': []  # TODO: Track source PDFs
        }
        
        total_cards = 0
        
        # Scan each card type folder
        for card_type_folder in sorted(team_path.iterdir()):
            if not card_type_folder.is_dir():
                continue
            
            folder_name = card_type_folder.name
            if folder_name not in self.CARD_TYPE_MAPPING:
                self.logger.warning(f"Unknown card type folder: {folder_name}")
                continue
            
            # Get card data
            card_data = self._scan_card_type_folder(card_type_folder, team_slug)
            
            # Add to total card count
            # operative_selection has 'card_count', others use 'count'
            card_count = card_data.get('count', card_data.get('card_count', 0))
            total_cards += card_count
            
            # Remove internal tracking field before storing
            if 'card_count' in card_data:
                del card_data['card_count']
            
            # Map to YAML structure
            mapping = self.CARD_TYPE_MAPPING[folder_name]
            
            if isinstance(mapping, tuple):
                # Nested structure (e.g., ploys -> strategy/firefight)
                parent_key, child_key = mapping
                if parent_key not in metadata:
                    metadata[parent_key] = {}
                metadata[parent_key][child_key] = card_data
            else:
                # Direct mapping
                metadata[mapping] = card_data
        
        # Add summary
        metadata['total_cards'] = total_cards
        metadata['complete'] = self._check_completeness(metadata)
        
        return metadata
    
    def _check_completeness(self, team_metadata: Dict[str, Any]) -> bool:
        """
        Check if team has all expected card types
        
        Args:
            team_metadata: Team metadata dict
            
        Returns:
            True if all card types present
        """
        # Expected keys in metadata
        expected = ['faction-rules', 'ploys', 'equipment', 'operative_selection', 'datacards']
        
        for key in expected:
            if key not in team_metadata:
                return False
            
            # Check ploys has both strategy and firefight
            if key == 'ploys':
                if 'strategy' not in team_metadata[key] or 'firefight' not in team_metadata[key]:
                    return False
        
        return True
    
    def generate(self) -> Dict[str, Any]:
        """
        Generate metadata for all teams in output directory
        
        Returns:
            Complete metadata dict
        """
        self.logger.info(f"Generating metadata from: {self.output_dir}")
        
        metadata = {
            'generated': datetime.now().isoformat(),
            'teams': {}
        }
        
        # Scan each team folder
        for team_path in sorted(self.output_dir.iterdir()):
            if not team_path.is_dir():
                continue
            
            team_slug = team_path.name
            metadata['teams'][team_slug] = self._scan_team_folder(team_path)
        
        self.logger.info(f"Generated metadata for {len(metadata['teams'])} teams")
        
        return metadata
    
    def save(self, metadata: Dict[str, Any], output_path: Path = Path('output-metadata.yaml')):
        """
        Save metadata to YAML file
        
        Args:
            metadata: Metadata dict to save
            output_path: Path to output YAML file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        self.logger.info(f"Saved metadata to: {output_path}")
    
    def generate_and_save(self, output_path: Path = Path('output-metadata.yaml')):
        """
        Generate and save metadata in one step
        
        Args:
            output_path: Path to output YAML file
        """
        metadata = self.generate()
        self.save(metadata, output_path)
