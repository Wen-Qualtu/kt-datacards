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
        # First check if it's a datacard (highest priority since abilities mention ploys)
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Look for datacard indicators in bottom portion
        # Datacards have multiple stat abbreviations in close proximity
        stat_keywords = ['APL', 'WS', 'BS', 'STR', 'DF', 'GA', 'SV', 'WOUNDS', 'SAVE', 'MOVE']
        stats_found = []
        for line in lines[-15:]:
            line_upper = line.upper().strip()
            # Check if line is exactly a stat keyword (for vertically stacked stats)
            if line_upper in stat_keywords:
                stats_found.append(line_upper)
            else:
                # Check if stat appears as standalone word in line
                for keyword in ['APL', 'WS', 'BS', 'STR', 'DF', 'GA', 'SV']:
                    if f' {keyword} ' in f' {line_upper} ' or f' {keyword}:' in f' {line_upper} ':
                        stats_found.append(keyword)
            # Also check for specific datacard phrases
            if 'RULES CONTINUE' in line_upper:
                return CardType.DATACARDS
        
        # If we found 2+ different stats, it's likely a datacard
        if len(set(stats_found)) >= 2:
            return CardType.DATACARDS
        
        # Then check headers for other type keywords
        for size, text in text_by_size[:30]:
            text_lower = text.lower()
            
            if 'operatives' == text_lower.strip():
                return CardType.OPERATIVES
            elif 'faction equipment' in text_lower or 'equipment' == text_lower.strip():
                return CardType.EQUIPMENT
            elif 'strategy ploy' in text_lower or 'strategic ploy' in text_lower:
                return CardType.STRATEGY_PLOYS
            elif 'firefight ploy' in text_lower:
                return CardType.FIREFIGHT_PLOYS
            elif 'faction rule' in text_lower:
                return CardType.FACTION_RULES
        
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
        """Extract team name from datacard metadata line (bottom tags section)"""
        # The team name is in the first tag at the bottom (orange text on black background)
        # It appears in the bottom section, typically the last few lines
        
        faction_keywords = [
            'IMPERIUM', 'CHAOS', 'AELDARI', 'TYRANIDS', 'ORKS',
            'TAU', 'NECRONS', 'LEAGUES OF VOTANN', 'GENESTEALER'
        ]
        # Add T'AU with regular apostrophe (will match after normalization)
        faction_keywords.append('T' + chr(39) + 'AU')
        
        role_keywords = [
            'LEADER', 'OPERATIVE', 'WARRIOR', 'SERGEANT', 'THEYN',
            'NOB', 'BOSS', 'PRIEST', 'TECH-PRIEST', 'TECHNOARCHEOLOGIST',
            'ARCHAEOPTER', 'SERVITOR', 'IMMORTAL', 'WRAITH', 'CRYPTEK'
        ]
        
        # Look in bottom 20 lines for the tag section
        # The first meaningful tag is usually the team name
        candidate_teams = []
        
        for line in lines[-20:]:
            # Normalize apostrophes for matching (replace curly quotes with regular)
            line_normalized = line.replace(chr(8217), chr(39)).replace(chr(8216), chr(39))
            line_upper = line_normalized.upper()
            
            # Skip if it's a stat line or common card elements
            if any(stat in line_upper for stat in ['APL', 'WOUNDS', 'SAVE', 'MOVEMENT', 'GA', 'DF']):
                continue
            
            # Check if line is uppercase and contains faction keyword
            if not line_normalized.isupper():
                continue
                
            # Check for faction keyword (check normalized line since we normalized apostrophes)
            if not any(keyword in line_upper for keyword in faction_keywords):
                continue
            
            # This line contains a faction keyword and is uppercase
            # It could be either:
            # 1. A comma-separated metadata line (TEAM, FACTION, ROLE, etc.)
            # 2. A short tag (just team name, 1-5 words)
            
            if ',' in line_normalized and line_normalized.count(',') >= 2:
                # Comma-separated format - first part is team name
                parts = [p.strip() for p in line_normalized.split(',')]
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
                    candidate_teams.append(self._clean_filename(team_name))
            
            elif len(line_normalized.split()) <= 5:
                # Short tag format - likely just team name
                # Remove role keywords if present
                words = line_normalized.split()
                team_words = []
                for word in words:
                    if any(role in word.upper() for role in role_keywords):
                        break
                    team_words.append(word)
                
                if team_words:
                    team_name = ' '.join(team_words)
                    candidate_teams.append(self._clean_filename(team_name))
        
        # Return the first candidate found (closest to bottom)
        return candidate_teams[0] if candidate_teams else None
    
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
