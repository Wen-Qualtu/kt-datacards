"""Image extraction from PDF pages"""
import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import Optional, List, Tuple
import logging

from ..models.team import Team
from ..models.card_type import CardType
from ..models.datacard import Datacard


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
            
            pdf_document.close()
            
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
            elif card_type == CardType.FACTION_RULES and not card_name:
                faction_rule_counter += 1
                card_name = f"faction-rule-{faction_rule_counter}"
            elif not card_name:
                self.logger.warning(
                    f"Could not extract card name for {pdf_path} page {page_num + 1}"
                )
                card_name = f"{card_type.value}-{page_num + 1}"
            
            # Create Datacard object
            datacard = Datacard(
                source_pdf=pdf_path,
                team=team,
                card_type=card_type,
                card_name=card_name
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
            
            # Collect text with sizes
            text_candidates = []
            for block in text_dict["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            size = span["size"]
                            
                            if len(text) > 3:
                                text_candidates.append((text, size))
            
            if not text_candidates:
                return None
            
            # Sort by size (largest first)
            text_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Define skip terms
            skip_terms = [
                'rules continue', 'wounds', 'save', 'move', 'apl',
                'strategy ploy', 'strategic ploy', 'tactical ploy',
                'firefight ploy', 'firefight',
                'faction equipment', 'equipment',
                'faction rules', 'datacard', 'datacards',
                'hit', 'dmg', 'name', 'atk'
            ]
            
            # Add team name to skip for non-datacards
            if card_type != CardType.DATACARDS:
                skip_terms.extend([
                    team.name.lower(), 
                    team.name.replace('-', ' ').lower()
                ])
            
            # Look through largest text
            for text, size in text_candidates[:20]:
                text_lower = text.lower()
                
                # Length checks
                if len(text) < 5 or len(text) > 50:
                    continue
                
                # Team name filtering (exact match)
                text_normalized = text_lower.replace(' ', '').replace('-', '')
                team_normalized = team.name.lower().replace(' ', '').replace('-', '')
                if text_normalized == team_normalized:
                    continue
                
                # Skip generic terms
                if any(skip in text_lower for skip in skip_terms):
                    continue
                
                # Size thresholds
                if card_type == CardType.DATACARDS and size < 10:
                    continue
                elif card_type != CardType.DATACARDS and size < 7:
                    continue
                
                # Skip rule text indicators
                if ':' in text or '(' in text or ')' in text:
                    continue
                
                # Clean and validate
                cleaned = self._clean_filename(text)
                if cleaned and len(cleaned) > 4:
                    return cleaned
            
            # Special cases
            if card_type == CardType.OPERATIVES:
                return "operatives"
            
            # Check for marker guide
            page_text = page.get_text().upper()
            if 'MARKER' in page_text and 'TOKEN' in page_text and 'GUIDE' in page_text:
                return "markertoken-guide"
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Could not extract card name: {e}")
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
