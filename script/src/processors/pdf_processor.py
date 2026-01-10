"""PDF processing and identification"""
import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import Optional, Tuple
import logging

from ..models.team import Team
from ..models.card_type import CardType
from .team_identifier import TeamIdentifier


class PDFProcessor:
    """Handles PDF processing, identification, and text extraction"""
    
    def __init__(self, team_identifier: TeamIdentifier):
        """
        Initialize PDFProcessor
        
        Args:
            team_identifier: TeamIdentifier for resolving team names
        """
        self.team_identifier = team_identifier
        self.logger = logging.getLogger(__name__)
    
    def identify_pdf(self, pdf_path: Path) -> Tuple[Optional[Team], Optional[CardType]]:
        """
        Identify team and card type from PDF content
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (Team, CardType) or (None, None) if not identifiable
        """
        try:
            # First try to identify from filename
            filename = pdf_path.stem.lower()
            card_type_from_filename = None
            
            for card_type in CardType:
                # Check if card type is in filename
                type_variants = [
                    card_type.value,  # e.g. "datacards"
                    card_type.value[:-1] if card_type.value.endswith('s') else card_type.value,  # singular
                    card_type.value.replace('-', ' '),  # with spaces
                ]
                if any(variant in filename for variant in type_variants):
                    card_type_from_filename = card_type
                    break
            
            pdf = fitz.open(pdf_path)
            
            # Get first page
            page = pdf[0]
            text_dict = page.get_text("dict")
            
            # Collect text by size
            text_by_size = []
            for block in text_dict["blocks"]:
                if block["type"] == 0:  # Text block
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            size = span["size"]
                            if text and len(text) > 3:
                                text_by_size.append((size, text.upper()))
            
            # Sort by size (largest first)
            text_by_size.sort(reverse=True, key=lambda x: x[0])
            
            # Identify card type from headers (but prefer filename if found)
            card_type = card_type_from_filename if card_type_from_filename else self._identify_card_type(text_by_size, page)
            
            # Identify team name
            team_name = self._identify_team_name(page, card_type)
            
            # Resolve team
            team = None
            if team_name:
                team = self.team_identifier.identify_team(team_name)
                if not team:
                    # Create new team if not found
                    team = self.team_identifier.get_or_create_team(team_name)
            
            pdf.close()
            
            return team, card_type
        
        except Exception as e:
            self.logger.error(f"Error identifying PDF {pdf_path}: {e}")
            return None, None
    
    def _identify_card_type(self, text_by_size, page) -> Optional[CardType]:
        """Identify card type from text"""
        # Check headers for type keywords
        for size, text in text_by_size[:30]:
            text_lower = text.lower()
            
            if 'operatives' == text_lower.strip():
                return CardType.OPERATIVES
            elif 'faction equipment' in text_lower:
                return CardType.EQUIPMENT
            elif 'strategy ploy' in text_lower or 'strategic ploy' in text_lower:
                return CardType.STRATEGY_PLOYS
            elif 'firefight ploy' in text_lower:
                return CardType.FIREFIGHT_PLOYS
            elif 'faction rule' in text_lower:
                return CardType.FACTION_RULES
        
        # Check if it's a datacard by looking for stats keywords
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Look for datacard indicators in bottom portion
        for line in lines[-10:]:
            if any(keyword in line.upper() for keyword in ['RULES CONTINUE', 'APL', 'WOUNDS', 'SAVE', 'MOVE']):
                return CardType.DATACARDS
        
        return None
    
    def _identify_team_name(self, page, card_type: Optional[CardType]) -> Optional[str]:
        """Identify team name from page content"""
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # For datacards, look for metadata line at bottom
        if card_type == CardType.DATACARDS:
            return self._extract_team_from_datacard_metadata(lines)
        
        # For other types, look at top headers
        return self._extract_team_from_headers(lines)
    
    def _extract_team_from_datacard_metadata(self, lines: list) -> Optional[str]:
        """Extract team name from datacard metadata line"""
        faction_keywords = [
            'IMPERIUM', 'CHAOS', 'AELDARI', 'TYRANIDS', 'ORKS',
            "T'AU", 'NECRONS', 'LEAGUES OF VOTANN', 'GENESTEALER'
        ]
        
        role_keywords = [
            'LEADER', 'OPERATIVE', 'WARRIOR', 'SERGEANT', 'THEYN',
            'NOB', 'BOSS', 'PRIEST', 'TECH-PRIEST', 'TECHNOARCHEOLOGIST',
            'ARCHAEOPTER', 'SERVITOR', 'IMMORTAL', 'WRAITH', 'CRYPTEK'
        ]
        
        # Look in bottom portion for metadata line
        for line in lines[-15:]:
            # Check if ALL CAPS and has commas
            if line.isupper() and ',' in line and line.count(',') >= 2:
                # Check for faction keyword
                if any(keyword in line for keyword in faction_keywords):
                    parts = [p.strip() for p in line.split(',')]
                    first_part = parts[0]
                    
                    # Remove role keywords from team name
                    words = first_part.split()
                    team_words = []
                    for word in words:
                        if any(role in word.upper() for role in role_keywords):
                            break
                        team_words.append(word)
                    
                    if team_words:
                        team_name = ' '.join(team_words)
                        return self._clean_filename(team_name)
        
        return None
    
    def _extract_team_from_headers(self, lines: list) -> Optional[str]:
        """Extract team name from header lines"""
        # Look in top portion for team name (usually larger text)
        for line in lines[:20]:
            # Skip common headers
            if any(keyword in line.upper() for keyword in ['EQUIPMENT', 'PLOY', 'RULE', 'OPERATIVES']):
                continue
            
            # If line looks like a team name (can be single word or multiple)
            words = line.split()
            if 1 <= len(words) <= 5 and len(line) > 3 and line.isupper():
                return self._clean_filename(line)
        
        return None
    
    def _clean_filename(self, text: str) -> str:
        """Clean text to create a valid filename"""
        if not text:
            return ""
        
        text = text.lower().strip()
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'[^a-z0-9-]', '', text)
        text = re.sub(r'-+', '-', text)
        text = text.strip('-')
        
        return text
    
    def get_pdf_info(self, pdf_path: Path) -> dict:
        """
        Get basic information about a PDF
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dictionary with page_count, file_size, etc.
        """
        try:
            pdf = fitz.open(pdf_path)
            info = {
                'page_count': len(pdf),
                'file_size': pdf_path.stat().st_size,
                'path': pdf_path
            }
            pdf.close()
            return info
        except Exception as e:
            self.logger.error(f"Error getting PDF info for {pdf_path}: {e}")
            return {}
