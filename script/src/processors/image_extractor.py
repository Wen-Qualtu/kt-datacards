"""Image extraction from PDF pages"""
import fitz  # PyMuPDF
import re
import json
from pathlib import Path
from typing import Optional, List, Tuple
from datetime import datetime
import logging

from ..models.team import Team
from ..models.card_type import CardType
from ..models.datacard import Datacard
from ..managers import TeamDataManager, ExtractionMetadataManager


class ImageExtractor:
    """Extracts card images from PDFs"""
    
    def __init__(self, dpi: int = 300):
        """
        Initialize ImageExtractor
        
        Args:
            dpi: Resolution for output images
        """
        self.dpi = dpi
        self.logger = logging.getLogger(__name__)
    
    def extract_from_pdf(
        self, 
        pdf_path: Path, 
        team: Team, 
        card_type: CardType
    ) -> List[Datacard]:
        """
        Extract cards from PDF
        
        Args:
            pdf_path: Path to source PDF
            team: Team the PDF belongs to
            card_type: Type of cards in the PDF
            
        Returns:
            List of Datacard objects
        """
        datacards = []
        
        print(f"[DEBUG extract_from_pdf] Called for {team.name} - {card_type.value} from {pdf_path}")
        
        try:
            pdf_document = fitz.open(pdf_path)
            
            # Analyze pages to detect front/back relationships
            card_pages = self._analyze_pages(pdf_document, team, card_type)
            
            # Extract images with proper naming
            datacards = self._extract_pages(
                pdf_document, 
                pdf_path,
                card_pages, 
                team, 
                card_type
            )
            
            # Get page count before closing
            page_count = len(pdf_document)
            
            pdf_document.close()
            
            # Save data using new managers
            self._save_team_data(datacards, team, pdf_path, page_count)
            
        except Exception as e:
            self.logger.error(f"Failed to extract from {pdf_path}: {e}")
        
        return datacards
    
    def _analyze_pages(
        self, 
        pdf_document, 
        team: Team, 
        card_type: CardType
    ) -> List[dict]:
        """Analyze pages to detect card names and front/back relationships"""
        card_pages = []
        skip_next_page = False
        
        for page_num in range(len(pdf_document)):
            if skip_next_page:
                skip_next_page = False
                continue
            
            page = pdf_document[page_num]
            text = page.get_text().upper()
            
            # Check for continuation markers
            has_continuation = any(marker in text for marker in [
                'CONTINUES ON OTHER SIDE',
                'CONTINUES ON THE OTHER SIDE', 
                'RULES CONTINUE ON OTHER SIDE'
            ])
            
            # Extract card name
            card_name = self._extract_card_name(
                page, 
                card_type, 
                team
            )
            
            # Determine if card has back side
            has_back = False
            if has_continuation and page_num + 1 < len(pdf_document):
                has_back = True
                skip_next_page = True
            elif card_type == CardType.DATACARDS:
                # For datacards, check if next page has same name
                if page_num + 1 < len(pdf_document):
                    next_page = pdf_document[page_num + 1]
                    next_name = self._extract_card_name(
                        next_page, 
                        card_type, 
                        team
                    )
                    if next_name == card_name:
                        has_back = True
                        skip_next_page = True
            elif card_type == CardType.FACTION_RULES and card_name:
                # For faction rules, check if next page has no extractable name
                # (indicating it's a continuation page)
                if page_num + 1 < len(pdf_document):
                    next_page = pdf_document[page_num + 1]
                    next_name = self._extract_card_name(
                        next_page, 
                        card_type, 
                        team
                    )
                    # If next page has no name or is marker guide, current card might have back
                    if not next_name or next_name == 'markertoken-guide':
                        # Only treat as back if next page isn't a marker guide
                        if next_name != 'markertoken-guide':
                            has_back = True
                            skip_next_page = True
            
            card_pages.append({
                'page_num': page_num,
                'card_name': card_name,
                'has_back': has_back
            })
        
        return card_pages
    
    def _extract_pages(
        self,
        pdf_document,
        pdf_path: Path,
        card_pages: List[dict],
        team: Team,
        card_type: CardType
    ) -> List[Datacard]:
        """Extract pages as images"""
        datacards = []
        
        # Track card counters for numbering
        operatives_counter = 0
        faction_rule_counter = 0
        
        # Determine if operatives need numbering
        operatives_need_numbering = False
        if card_type == CardType.OPERATIVES:
            operatives_cards = [c for c in card_pages if c['card_name'] == 'operatives']
            operatives_need_numbering = len(operatives_cards) > 1
        
        page_index = 0
        while page_index < len(card_pages):
            card_info = card_pages[page_index]
            page_num = card_info['page_num']
            card_name = card_info['card_name']
            has_back = card_info['has_back']
            
            # Generate card name and filename
            if card_type == CardType.OPERATIVES and card_name == 'operatives':
                operatives_counter += 1
                if operatives_need_numbering and operatives_counter > 1:
                    card_name = f"operatives-{operatives_counter}"
                else:
                    card_name = "operatives"
            elif card_type == CardType.FACTION_RULES:
                # For faction rules, if no name extracted, fail
                if not card_name:
                    self.logger.error(
                        f"FAILED: Could not extract faction rule name for {pdf_path} page {page_num + 1}. "
                        f"Manual review required. Add to config or fix PDF."
                    )
                    raise ValueError(f"Failed to extract card name for {pdf_path} page {page_num + 1}")
            elif not card_name:
                self.logger.error(
                    f"FAILED: Could not extract card name for {pdf_path} page {page_num + 1}. "
                    f"Card type: {card_type.value}. Manual review required."
                )
                raise ValueError(f"Failed to extract card name for {pdf_path} page {page_num + 1}")
            
            # Create Datacard object
            # Extract description from the front page
            description = self._extract_card_description(
                pdf_document[page_num],
                card_name,
                card_type
            )
            
            datacard = Datacard(
                source_pdf=pdf_path,
                team=team,
                card_type=card_type,
                card_name=card_name,
                description=description
            )
            
            # Extract front image
            front_path = self._extract_page_image(
                pdf_document[page_num],
                datacard.get_output_folder() / datacard.get_expected_front_filename()
            )
            if front_path:
                datacard.front_image = front_path
            
            # Extract back image if exists
            if has_back:
                back_path = self._extract_page_image(
                    pdf_document[page_num + 1],
                    datacard.get_output_folder() / datacard.get_expected_back_filename()
                )
                if back_path:
                    datacard.back_image = back_path
            
            datacards.append(datacard)
            page_index += 1
        
        return datacards
    
    def _extract_page_image(self, page, output_path: Path) -> Optional[Path]:
        """Extract single page as image"""
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert page to image
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Save as JPG
            pix.save(output_path)
            self.logger.info(f"Extracted: {output_path}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to extract page to {output_path}: {e}")
            return None
    
    def _extract_card_name(
        self, 
        page, 
        card_type: CardType, 
        team: Team
    ) -> Optional[str]:
        """Extract card name from page text"""
        try:
            text_dict = page.get_text("dict")
            
            # Collect text with sizes and positions
            text_candidates = []
            for block in text_dict["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            size = span["size"]
                            y_pos = span["bbox"][1]  # Top position
                            
                            if len(text) > 3:
                                text_candidates.append((text, size, y_pos))
            
            if not text_candidates:
                return None
            
            # Sort by size (largest first), then by position (top to bottom)
            text_candidates.sort(key=lambda x: (-x[1], x[2]))
            
            # Define skip terms (base terms that appear on many cards)
            skip_terms = [
                'rules continue', 'wounds', 'save', 'move', 'apl',
                'strategy ploy', 'strategic ploy', 'tactical ploy',
                'firefight ploy', 'firefight',
                'faction equipment', 'equipment',
                'datacard', 'datacards',
                'hit', 'dmg', 'name', 'atk'
            ]
            
            # Special handling for faction rules - skip the header but get the rule name
            if card_type == CardType.FACTION_RULES:
                # Look for the rule name which typically appears after "FACTION RULE" header
                # It's usually the next largest text after team name and "FACTION RULE"
                faction_rule_found = False
                for text, size, y_pos in text_candidates[:30]:
                    text_lower = text.lower()
                    
                    # Skip the "FACTION RULE" header itself
                    if 'faction rule' in text_lower:
                        faction_rule_found = True
                        continue
                    
                    # Skip team name
                    text_normalized = text_lower.replace(' ', '').replace('-', '')
                    team_normalized = team.name.lower().replace(' ', '').replace('-', '')
                    if text_normalized == team_normalized:
                        continue
                    
                    # Skip if too short or too long
                    if len(text) < 5 or len(text) > 60:
                        continue
                    
                    # Skip common terms
                    if any(skip in text_lower for skip in skip_terms):
                        continue
                    
                    # Skip rule text indicators
                    if ':' in text or '(' in text or ')' in text:
                        continue
                    
                    # If we've seen "FACTION RULE" header and this is reasonable text, use it
                    if faction_rule_found and size > 8:
                        cleaned = self._clean_filename(text)
                        if cleaned and len(cleaned) > 4:
                            return cleaned
                    
                    # Even without seeing header, if text is large enough and looks like title
                    if size > 10:
                        cleaned = self._clean_filename(text)
                        if cleaned and len(cleaned) > 4:
                            return cleaned
                
                # Fallback: check for marker guide
                page_text = page.get_text().upper()
                if 'MARKER' in page_text and 'TOKEN' in page_text and 'GUIDE' in page_text:
                    return "markertoken-guide"
                
                return None
            
            # Don't skip "faction rules" for non-faction-rule card types
            skip_terms.append('faction rules')
            
            # For operatives, skip "kill team" terms and just use "operatives"
            if card_type == CardType.OPERATIVES:
                return "operatives"
            
            # Look through largest text
            for text, size, y_pos in text_candidates[:20]:
                text_lower = text.lower()
                
                # Length checks
                if len(text) < 5 or len(text) > 50:
                    continue
                
                # Team name filtering - handle plural/singular variations
                text_normalized = text_lower.replace(' ', '').replace('-', '')
                team_normalized = team.name.lower().replace(' ', '').replace('-', '')
                # Check exact match or singular/plural variants
                if (text_normalized == team_normalized or 
                    text_normalized == team_normalized.rstrip('s') or
                    text_normalized + 's' == team_normalized):
                    continue
                
                # Skip generic terms (substring match)
                if any(skip in text_lower for skip in skip_terms):
                    continue
                
                # Size thresholds (more lenient for faction rules)
                if card_type == CardType.DATACARDS and size < 10:
                    continue
                elif card_type == CardType.FACTION_RULES and size < 5:
                    # Allow smaller text for faction rules as rule names can vary
                    continue
                elif card_type != CardType.DATACARDS and card_type != CardType.FACTION_RULES and size < 7:
                    continue
                
                # Skip rule text indicators
                if ':' in text or '(' in text or ')' in text:
                    continue
                
                # Clean and validate
                cleaned = self._clean_filename(text)
                if cleaned and len(cleaned) > 4:
                    return cleaned
            
            # Check for marker guide
            page_text = page.get_text().upper()
            if 'MARKER' in page_text and 'TOKEN' in page_text and 'GUIDE' in page_text:
                return "markertoken-guide"
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Could not extract card name: {e}")
            return None
    
    def _extract_card_description(
        self,
        page,
        card_name: str,
        card_type: CardType
    ) -> Optional[str]:
        """
        Extract description text from card page
        
        For ploys and equipment, extracts all text after the card name.
        For datacards, extracts stats and abilities.
        
        Args:
            page: PyMuPDF page object
            card_name: Name of the card
            card_type: Type of card
            
        Returns:
            Extracted description text
        """
        try:
            # Get all text from the page
            full_text = page.get_text()
            
            if not full_text:
                return None
            
            # Clean up the text - remove excessive whitespace
            lines = full_text.split('\n')
            cleaned_lines = []
            
            # Skip empty lines and normalize spacing
            for line in lines:
                line = line.strip()
                if line:
                    cleaned_lines.append(line)
            
            if not cleaned_lines:
                return None
            
            # For ploys and equipment, extract text after the title
            if card_type in [CardType.STRATEGY_PLOYS, CardType.FIREFIGHT_PLOYS, CardType.EQUIPMENT]:
                # Find the title line (usually the first few lines)
                # Skip the title and take the description
                description_lines = []
                title_found = False
                
                for i, line in enumerate(cleaned_lines):
                    # Convert card name to comparable format
                    card_name_normalized = card_name.replace('-', ' ').upper()
                    line_normalized = line.upper()
                    
                    # Check if this line contains the card title
                    if not title_found:
                        # Skip team names, card type headers, etc.
                        skip_terms = ['STRATEGY PLOY', 'FIREFIGHT PLOY', 'EQUIPMENT', 'FACTION RULE']
                        if any(term in line_normalized for term in skip_terms):
                            continue
                        
                        # If we find the card name, mark title as found
                        if card_name_normalized in line_normalized:
                            title_found = True
                            continue
                    else:
                        # After title, collect description lines
                        # Stop if we hit common card end markers
                        if line_normalized in ['FACTION RULES', 'DATACARDS', 'EQUIPMENT']:
                            break
                        description_lines.append(line)
                
                if description_lines:
                    return ' '.join(description_lines)
            
            # For datacards, just return cleaned text (stats, abilities, etc.)
            elif card_type == CardType.DATACARDS:
                # Skip the first few lines (usually title/team name)
                return ' '.join(cleaned_lines[3:]) if len(cleaned_lines) > 3 else None
            
            # For other types, return first substantial text block
            return ' '.join(cleaned_lines[:10]) if cleaned_lines else None
            
        except Exception as e:
            self.logger.warning(f"Could not extract description for {card_name}: {e}")
            return None
    
    def _clean_filename(self, text: str) -> Optional[str]:
        """Clean text to create valid filename"""
        if not text:
            return None
        
        # Convert to lowercase and strip
        text = text.lower().strip()
        
        # Replace spaces and underscores with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        
        # Remove non-alphanumeric except hyphens
        text = re.sub(r'[^a-z0-9-]', '', text)
        
        # Remove multiple consecutive hyphens
        text = re.sub(r'-+', '-', text)
        
        # Remove leading/trailing hyphens
        text = text.strip('-')
        
        return text if text else None
    
    def _save_team_data(self, datacards: List[Datacard], team: Team, pdf_path: Path, page_count: int):
        """
        Save card data and extraction metadata using new managers
        
        Args:
            datacards: List of datacards with descriptions
            team: Team the cards belong to
            pdf_path: Path to the source PDF
            page_count: Number of pages in the PDF
        """
        try:
            print(f"[DEBUG] _save_team_data called for {team.name} with {len(datacards)} cards")
            
            # Initialize managers (they will load existing data if available)
            team_data = TeamDataManager(
                team_name=team.name,
                team_display_name=team.name.replace('-', ' ').title(),
                faction=None,  # Could be added from team config if needed
                army=None  # Could be added from team config if needed
            )
            
            extraction_meta = ExtractionMetadataManager(
                team_name=team.name,
                team_display_name=team.name.replace('-', ' ').title()
            )
            
            print(f"[DEBUG] Managers initialized for {team.name}")
            
            # Track PDF processing
            extraction_meta.add_pdf_processed(
                pdf_path=str(pdf_path),
                pages_processed=page_count
            )
            
            # Process each datacard
            for datacard in datacards:
                # Prepare content dict - only cleaned/structured data
                content = {
                    "description": datacard.description if datacard.description else ""
                }
                
                # Save card data (clean content only)
                team_data.add_card(
                    card_type=datacard.card_type.value,
                    card_name=datacard.card_name,
                    has_back=datacard.back_image is not None,
                    content=content
                )
                
                # Save extraction metadata (includes raw full_text)
                extraction_meta.add_card_metadata(
                    card_type=datacard.card_type.value,
                    card_name=datacard.card_name,
                    page_num=0,  # Page number would need to be tracked in datacard if needed
                    extraction={
                        "source_pdf": str(pdf_path),
                        "extracted_at": datetime.now().isoformat(),
                        "full_text": datacard.description if datacard.description else "",  # Raw extracted text
                        "text_extracted": bool(datacard.description),
                        "name_confidence": "high"  # Could be enhanced to track actual confidence
                    },
                    output={
                        "front_image": str(datacard.front_image) if datacard.front_image else None,
                        "back_image": str(datacard.back_image) if datacard.back_image else None,
                        "image_format": "jpg",
                        "image_dpi": self.dpi
                    }
                )
            
            print(f"[DEBUG] Processed {len(datacards)} cards, now saving...")
            
            # Save both files
            team_data.save()
            extraction_meta.save()
            
            print(f"[DEBUG] Files saved successfully for {team.name}")
            self.logger.info(f"Saved team data and metadata for {team.name}")
            
        except Exception as e:
            self.logger.error(f"Could not save team data for {team.name}: {e}")
            print(f"[DEBUG] Error saving team data: {e}")
            import traceback
            traceback.print_exc()

