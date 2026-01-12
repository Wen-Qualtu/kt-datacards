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
from .processors.v2_output_processor import V2OutputProcessor


class DatacardPipeline:
    """Main pipeline orchestrating the datacard processing workflow"""
    
    def __init__(
        self,
        input_raw_dir: Path = Path('input'),
        processed_dir: Path = Path('processed'),
        output_v2_dir: Path = Path('output_v2'),
        config_dir: Path = Path('config'),
        dpi: int = 300
    ):
        """
        Initialize DatacardPipeline
        
        Args:
            input_raw_dir: Directory with raw PDF files (searches recursively)
            processed_dir: Directory for organized PDFs
            output_v2_dir: Directory for extracted images with V2 structure
            config_dir: Configuration directory
            dpi: Image resolution
        """
        self.input_raw_dir = input_raw_dir
        self.processed_dir = processed_dir
        self.output_v2_dir = output_v2_dir
        self.config_dir = config_dir
        self.dpi = dpi
        
        # Initialize components
        self.team_identifier = TeamIdentifier(
            config_dir / 'team-config.yaml'
        )
        self.pdf_processor = PDFProcessor(self.team_identifier)
        self.image_extractor = ImageExtractor(dpi=dpi, output_v2_dir=output_v2_dir)
        self.backside_processor = BacksideProcessor(
            config_dir
        )
        self.v2_processor = V2OutputProcessor(output_v2_dir)
        
        self.logger = logging.getLogger(__name__)
    
    def run_full_pipeline(self) -> dict:
        """
        Run complete pipeline: process → extract → backsides → URLs → V2
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'pdfs_processed': 0,
            'images_extracted': 0,
            'backsides_added': 0,
            'v2_urls_generated': 0
        }
        
        self.logger.info("Starting full pipeline")
        
        # Step 1: Process raw PDFs
        self.logger.info("Step 1: Processing raw PDFs")
        processed_pdfs = self.process_raw_pdfs()
        stats['pdfs_processed'] = len(processed_pdfs)
        
        # If no raw PDFs were processed, look for existing processed PDFs
        if not processed_pdfs:
            self.logger.info("No raw PDFs found, looking for existing processed PDFs")
            processed_pdfs = self._find_processed_pdfs()
            if processed_pdfs:
                self.logger.info(f"Found {len(processed_pdfs)} existing processed PDFs")
            else:
                self.logger.warning("No processed PDFs found")
        
        # Step 2: Extract images from processed PDFs directly to V2 structure
        self.logger.info("Step 2: Extracting images to V2 structure")
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
        
        # Step 4: Generate V2 URLs JSON
        self.logger.info("Step 4: Generating V2 URLs")
        stats['v2_urls_generated'] = self.v2_processor.generate_v2_urls_json()
        
        # Step 5: Generate TTS objects
        self.logger.info("Step 5: Generating TTS objects")
        from .generators.tts_generator import TTSGenerator
        tts_generator = TTSGenerator(
            output_v2_dir=self.output_v2_dir,
            tts_output_dir=self.output_v2_dir.parent / 'tts_objects',
            config_dir=self.config_dir
        )
        stats['tts_objects_generated'] = tts_generator.generate_all_tts_objects()
        
        # Step 6: Generate metadata
        self.logger.info("Step 6: Generating metadata")
        if self.output_v2_dir.exists():
            self.generate_metadata()
        else:
            self.logger.warning("Skipping metadata generation - no output files found")
        
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
    
    def _find_processed_pdfs(self) -> List[tuple]:
        """
        Find and identify existing processed PDFs
        
        Returns:
            List of (pdf_path, team, card_type) tuples
        """
        processed_pdfs = []
        
        if not self.processed_dir.exists():
            return processed_pdfs
        
        # Iterate through team directories
        for team_dir in sorted(self.processed_dir.iterdir()):
            if not team_dir.is_dir():
                continue
            
            # Get team from directory name
            team = self.team_identifier.get_or_create_team(team_dir.name)
            if not team:
                self.logger.warning(f"Unknown team directory: {team_dir.name}")
                continue
            
            # Find all PDFs in this team directory
            for pdf_file in sorted(team_dir.glob('*.pdf')):
                # Parse card type from filename: team-name-cardtype.pdf
                # Remove team name prefix and .pdf suffix
                filename_lower = pdf_file.stem.lower()
                team_prefix = f"{team.name}-"
                if filename_lower.startswith(team_prefix):
                    card_type_str = filename_lower[len(team_prefix):]
                    try:
                        card_type = CardType.from_string(card_type_str)
                        processed_pdfs.append((pdf_file, team, card_type))
                    except ValueError:
                        self.logger.warning(f"Could not identify card type for {pdf_file.name}")
                else:
                    self.logger.warning(f"Unexpected filename format: {pdf_file.name}")
        
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
        Generate URLs JSON
        
        Returns:
            Number of URLs generated
        """
        return self.url_generator.generate_json()
    
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
    
    def generate_metadata(self):
        """Generate metadata YAML file"""
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from generate_metadata import OutputMetadataGenerator
        
        generator = OutputMetadataGenerator(
            output_dir=self.output_v2_dir,
            config_dir=self.config_dir
        )
        generator.generate_and_save(output_path=self.output_v2_dir / 'metadata.yaml')
    
    def _log_stats(self, stats: dict):
        """Log pipeline statistics"""
        self.logger.info("=" * 60)
        self.logger.info("Pipeline Statistics:")
        self.logger.info(f"  PDFs Processed: {stats.get('pdfs_processed', 0)}")
        self.logger.info(f"  Images Extracted: {stats.get('images_extracted', 0)}")
        self.logger.info(f"  Backsides Added: {stats.get('backsides_added', 0)}")
        self.logger.info(f"  V2 URLs Generated: {stats.get('v2_urls_generated', 0)}")
        self.logger.info("=" * 60)
