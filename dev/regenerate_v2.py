#!/usr/bin/env python3
"""Regenerate V2 output with corrected filenames"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'script'))

from src.processors.v2_output_processor import V2OutputProcessor
from src.processors.team_identifier import TeamIdentifier

# Initialize
team_identifier = TeamIdentifier(Path('config/team-name-mapping.yaml'))
v2_processor = V2OutputProcessor(Path('output'), Path('output/v2'))

# Get all teams
teams = team_identifier.get_all_teams()

print(f"Processing {len(teams)} teams for v2 output...")

# Process all teams
stats = v2_processor.process_all_teams(teams)

print(f"\nProcessed {stats['files_processed']} files")
print(f"Errors: {stats['errors']}")

# Generate URLs
print("\nGenerating v2 URLs CSV...")
url_count = v2_processor.generate_v2_urls_csv()
print(f"Generated {url_count} URLs")

print("\n✅ V2 output regeneration complete!")
