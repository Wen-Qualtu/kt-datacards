import os
import csv
from pathlib import Path

def generate_url_csv():
    """
    Generate a CSV file with all extracted JPG file URLs for GitHub raw access.
    """
    output_dir = Path('output')
    csv_path = Path('datacards-urls.csv')
    
    # GitHub raw URL base
    github_base = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output"
    
    # Collect all entries
    entries = []
    
    # Walk through output directory
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_name = team_dir.name
        
        # Walk through type directories (datacards, equipment, etc.)
        for type_dir in sorted(team_dir.iterdir()):
            if not type_dir.is_dir():
                continue
            
            type_name = type_dir.name
            
            # Get all JPG files
            for jpg_file in sorted(type_dir.glob('*.jpg')):
                file_name = jpg_file.stem  # Name without extension
                
                # Construct GitHub raw URL (use forward slashes)
                url = f"{github_base}/{team_name}/{type_name}/{jpg_file.name}"
                
                entries.append({
                    'team': team_name,
                    'type': type_name,
                    'name': file_name,
                    'url': url
                })
    
    # Write to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['team', 'type', 'name', 'url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry)
    
    print(f"[OK] Generated {csv_path}")
    print(f"[OK] Total entries: {len(entries)}")
    print(f"\nBreakdown by team:")
    
    # Count by team
    team_counts = {}
    for entry in entries:
        team = entry['team']
        team_counts[team] = team_counts.get(team, 0) + 1
    
    for team, count in sorted(team_counts.items()):
        print(f"  {team}: {count} files")

if __name__ == '__main__':
    generate_url_csv()
