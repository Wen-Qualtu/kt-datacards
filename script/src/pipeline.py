"""Main pipeline for datacard processing"""
from pathlib import Path
from typing import List, Optional
import logging

from .models.team import Team
from .models.card_type import CardType
from .models.datacard import Datacard
from .processors.team_identifier import TeamIdentifier
from .processors.pdf_processor import PDFProcessor
from .processors.image_extractor import ImageExtractor
from .processors.backside_processor import BacksideProcessor
from .generators.url_generator import URLGenerator


class DatacardPipeline:
    """Main pipeline orchestrating the datacard processing workflow"""
    
    def __init__(
        self,
        input_raw_dir: Path = Path('input'),
        processed_dir: Path = Path('processed'),
        output_dir: Path = Path('output'),
        config_dir: Path = Path('config'),
        dpi: int = 300
    ):
        """
        Initialize DatacardPipeline
        
        Args:
            input_raw_dir: Directory with raw PDF files (searches recursively)
            processed_dir: Directory for organized PDFs
            output_dir: Directory for extracted images
            config_dir: Configuration directory
            dpi: Image resolution
        """
        self.input_raw_dir = input_raw_dir
        self.processed_dir = processed_dir
        self.output_dir = output_dir
        self.config_dir = config_dir
        self.dpi = dpi
        
        # Initialize components
        self.team_identifier = TeamIdentifier(
            config_dir / 'team-name-mapping.yaml'
        )
        self.pdf_processor = PDFProcessor(self.team_identifier)
        self.image_extractor = ImageExtractor(dpi=dpi)
        self.backside_processor = BacksideProcessor(
            config_dir / 'card-backside'
        )
        self.url_generator = URLGenerator(output_dir)
        
        self.logger = logging.getLogger(__name__)
    
    def run_full_pipeline(self) -> dict:
        """
        Run complete pipeline: process → extract → backsides → URLs
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'pdfs_processed': 0,
            'images_extracted': 0,
            'backsides_added': 0,
            'urls_generated': 0
        }
        
        self.logger.info("Starting full pipeline")
        
        # Step 1: Process raw PDFs
        self.logger.info("Step 1: Processing raw PDFs")
        processed_pdfs = self.process_raw_pdfs()
        stats['pdfs_processed'] = len(processed_pdfs)
        
        # Step 2: Extract images from processed PDFs
        self.logger.info("Step 2: Extracting images")
        all_datacards = []
        for pdf_path, team, card_type in processed_pdfs:
            datacards = self.image_extractor.extract_from_pdf(
                pdf_path, team, card_type
            )
            all_datacards.extend(datacards)
        stats['images_extracted'] = len(all_datacards)
        
        # Step 3: Add backsides
        self.logger.info("Step 3: Adding backsides")
        stats['backsides_added'] = self.backside_processor.add_backsides(
            all_datacards
        )
        
        # Step 4: Generate URLs CSV
        self.logger.info("Step 4: Generating URLs")
        stats['urls_generated'] = self.url_generator.generate_csv()
        
        self.logger.info("Pipeline complete")
        self._log_stats(stats)
        
        return stats
    
    def process_raw_pdfs(self) -> List[tuple]:
        """
        Process raw PDFs: identify and organize
        
        Returns:
            List of (pdf_path, team, card_type) tuples
        """
        processed_pdfs = []
        
        if not self.input_raw_dir.exists():
            self.logger.warning(f"Raw input directory not found: {self.input_raw_dir}")
            return processed_pdfs
        
        # Get all PDF files recursively
        pdf_files = list(self.input_raw_dir.rglob('*.pdf'))
        
        if not pdf_files:
            self.logger.info(f"No PDF files found in {self.input_raw_dir}")
            return processed_pdfs
        
        self.logger.info(f"Found {len(pdf_files)} PDF file(s)")
        
        for pdf_file in pdf_files:
            try:
                # Identify team and card type
                team, card_type = self.pdf_processor.identify_pdf(pdf_file)
                
                if not team or not card_type:
                    self.logger.warning(
                        f"Could not identify {pdf_file.name} - moving to input/failed"
                    )
                    # Move to failed directory for manual review
                    failed_dir = self.input_raw_dir / 'failed'
                    failed_dir.mkdir(parents=True, exist_ok=True)
                    import shutil
                    shutil.move(str(pdf_file), str(failed_dir / pdf_file.name))
                    continue
                
                # Move to processed directory
                dest_dir = team.get_processed_path()
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate clean filename
                clean_name = self._generate_clean_filename(
                    team, card_type, pdf_file
                )
                dest_path = dest_dir / clean_name
                
                # Copy file to processed
                import shutil
                shutil.copy2(pdf_file, dest_path)
                
                # Move original to archive
                archive_dir = team.get_archive_path()
                archive_dir.mkdir(parents=True, exist_ok=True)
                archive_path = archive_dir / pdf_file.name
                shutil.move(str(pdf_file), str(archive_path))
                
                self.logger.info(
                    f"Processed: {pdf_file.name} → {team.name}/{clean_name}"
                )
                self.logger.info(
                    f"Archived: {pdf_file.name} → archive/{team.name}/"
                )
                
                processed_pdfs.append((dest_path, team, card_type))
                
            except Exception as e:
                self.logger.error(
                    f"Failed to process {pdf_file.name}: {e}"
                )
        
        return processed_pdfs
    
    def extract_images(
        self, 
        team_filter: Optional[List[str]] = None
    ) -> List[Datacard]:
        """
        Extract images from processed PDFs
        
        Args:
            team_filter: Optional list of team names to process
            
        Returns:
            List of Datacard objects
        """
        all_datacards = []
        
        if not self.processed_dir.exists():
            self.logger.warning(
                f"Processed directory not found: {self.processed_dir}"
            )
            return all_datacards
        
        # Get team directories
        team_dirs = [d for d in self.processed_dir.iterdir() if d.is_dir()]
        
        for team_dir in team_dirs:
            team_name = team_dir.name
            
            # Apply filter if specified
            if team_filter and team_name not in team_filter:
                continue
            
            # Get team object
            team = self.team_identifier.get_or_create_team(team_name)
            
            # Process all PDFs in team directory
            for pdf_file in team_dir.glob('*.pdf'):
                try:
                    # Extract card type from filename instead of re-analyzing PDF
                    # Processed PDFs are named: {team}-{card-type}.pdf
                    # Example: hearthkyn-salvager-datacards.pdf
                    filename_parts = pdf_file.stem.split('-')
                    
                    # Find card type in filename (last part after removing team name)
                    # Team name might have hyphens, so we need to find the card type suffix
                    card_type_str = None
                    for card_type in CardType:
                        # Check if filename ends with -{card_type_value}
                        if pdf_file.stem.endswith(f'-{card_type.value}'):
                            card_type_str = card_type.value
                            break
                    
                    if not card_type_str:
                        self.logger.warning(
                            f"Could not extract card type from filename: {pdf_file.name} in {team_name}"
                        )
                        continue
                    
                    # Convert to CardType enum
                    card_type = CardType(card_type_str)
                    
                    # Extract images
                    datacards = self.image_extractor.extract_from_pdf(
                        pdf_file, team, card_type
                    )
                    all_datacards.extend(datacards)
                    
                except Exception as e:
                    self.logger.error(
                        f"Failed to extract {pdf_file}: {e}"
                    )
        
        return all_datacards
    
    def add_backsides(
        self, 
        team_filter: Optional[List[str]] = None
    ) -> int:
        """
        Add backside images to cards
        
        Args:
            team_filter: Optional list of team names to process
            
        Returns:
            Number of backsides added
        """
        # Collect all datacards from output directory
        datacards = self._collect_existing_datacards(team_filter)
        
        # Add backsides
        return self.backside_processor.add_backsides(datacards)
    
    def generate_urls(self) -> int:
        """
        Generate URLs CSV
        
        Returns:
            Number of entries generated
        """
        return self.url_generator.generate_csv()
    
    def _generate_clean_filename(
        self, 
        team: Team, 
        card_type: CardType,
        original_file: Path
    ) -> str:
        """Generate clean filename for processed PDF"""
        # Format: {team-name}-{card-type}.pdf
        # e.g., hearthkyn-salvager-datacards.pdf
        return f"{team.name}-{card_type.value}.pdf"
    
    def _collect_existing_datacards(
        self, 
        team_filter: Optional[List[str]] = None
    ) -> List[Datacard]:
        """Collect Datacard objects from existing output directory"""
        datacards = []
        
        if not self.output_dir.exists():
            return datacards
        
        for team_dir in self.output_dir.iterdir():
            if not team_dir.is_dir():
                continue
            
            team_name = team_dir.name
            
            # Apply filter
            if team_filter and team_name not in team_filter:
                continue
            
            team = self.team_identifier.get_or_create_team(team_name)
            
            # Process card type directories
            for type_dir in team_dir.iterdir():
                if not type_dir.is_dir():
                    continue
                
                # Skip directories with team name prefix (inconsistency from old scripts)
                # Check both full team name and first part of hyphenated name
                dir_name = type_dir.name
                
                # Try to parse as card type
                try:
                    card_type = CardType.from_string(dir_name)
                except ValueError:
                    # Not a recognized card type, skip this directory
                    continue
                
                if not card_type:
                    continue
                
                # Collect front images
                for front_image in type_dir.glob('*_front.jpg'):
                    card_name = front_image.stem.replace('_front', '')
                    
                    # Create Datacard object
                    datacard = Datacard(
                        source_pdf=None,  # Unknown at this point
                        team=team,
                        card_type=card_type,
                        card_name=card_name
                    )
                    datacard.front_image = front_image
                    
                    # Check for back image
                    back_image = front_image.parent / front_image.name.replace(
                        '_front.jpg', '_back.jpg'
                    )
                    if back_image.exists():
                        datacard.back_image = back_image
                    
                    datacards.append(datacard)
        
        return datacards
    
    def _log_stats(self, stats: dict):
        """Log pipeline statistics"""
        self.logger.info("=" * 60)
        self.logger.info("Pipeline Statistics:")
        self.logger.info(f"  PDFs Processed: {stats['pdfs_processed']}")
        self.logger.info(f"  Images Extracted: {stats['images_extracted']}")
        self.logger.info(f"  Backsides Added: {stats['backsides_added']}")
        self.logger.info(f"  URLs Generated: {stats['urls_generated']}")
        self.logger.info("=" * 60)
