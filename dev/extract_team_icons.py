#!/usr/bin/env python3
"""
Extract team icons from Warhammer Community Kill Team page.

This script scrapes the official Warhammer Community page to download team icons
that can be used for custom backside designs. Each team has a clickable icon
linking to their rules PDF.
"""

import requests
from pathlib import Path
import json
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from PIL import Image
import io
import re

def fetch_team_icons(url):
    """
    Fetch team icon images from Warhammer Community page.
    
    The page has clickable team icons that link to PDF downloads.
    Each icon is wrapped in an <a> tag linking to the rules PDF.
    """
    print(f"Fetching {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links to team rules PDFs
    team_data = []
    
    # Look for links to PDF files in the warcomprod storage
    pdf_links = soup.find_all('a', href=re.compile(r'warcomprod.*\.pdf'))
    
    print(f"Found {len(pdf_links)} team rule PDFs")
    
    for link in pdf_links:
        pdf_url = link.get('href')
        
        # Extract team name from URL
        # Format: .../team-rules/angels-of-death/killteam_teamrules_angelsofdeath_eng_02.10.24.pdf
        match = re.search(r'team-rules/([^/]+)/', pdf_url)
        if match:
            team_slug = match.group(1)
        else:
            continue
        
        # Find the icon image - it's a sibling in the parent div
        parent = link.parent
        if parent:
            img = parent.find('img')
            if img:
                img_src = img.get('src') or img.get('data-src')
                if img_src:
                    # Make absolute URL
                    img_url = urljoin(url, img_src)
                    team_data.append({
                        'slug': team_slug,
                        'name': team_slug.replace('-', ' ').title(),
                        'icon_url': img_url,
                        'pdf_url': pdf_url
                    })
    
    return team_data

def download_image(url, output_path):
    """Download an image from URL and save it."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    
    # Save image
    img = Image.open(io.BytesIO(response.content))
    img.save(output_path)
    
    return img.size

def extract_team_name_from_image(img_path):
    """
    Try to extract team name from the image.
    
    This could use OCR (pytesseract) to read text from the image,
    or we could do it manually by examining the images.
    """
    # For now, return None - we'll match manually
    return None

def main():
    """Main extraction workflow."""
    url = "https://www.warhammer-community.com/en-gb/articles/xfV8vUOg/download-the-kill-team-app-and-faction-rules-today/"
    output_dir = Path(__file__).parent.parent / "config" / "team-icons-raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Kill Team Icon Extractor (Warhammer Community)")
    print("=" * 60)
    
    # Fetch team data
    try:
        team_data = fetch_team_icons(url)
    except Exception as e:
        print(f"Error fetching page: {e}")
        print("\nNote: You may need to install dependencies:")
        print("  poetry add requests beautifulsoup4")
        return
    
    if not team_data:
        print("\nNo team icons found. The page structure may have changed.")
        print("Try visiting the page directly:")
        print(f"  {url}")
        return
    
    print(f"\nFound {len(team_data)} teams")
    
    # Save metadata
    metadata_file = output_dir / "teams_metadata.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(team_data, f, indent=2)
    print(f"\n✓ Saved metadata to {metadata_file}")
    
    # Download icons
    print(f"\nDownloading {len(team_data)} team icons...")
    for team in team_data:
        try:
            filename = f"{team['slug']}.png"
            output_path = output_dir / filename
            
            size = download_image(team['icon_url'], output_path)
            print(f"  ✓ {team['name']:<30} ({size[0]}x{size[1]}) -> {filename}")
        except Exception as e:
            print(f"  ✗ {team['name']:<30} Failed: {e}")
    
    print(f"\n✓ Images saved to {output_dir}")
    print("\nNext steps:")
    print("1. Review images in config/team-icons-raw/")
    print("2. Extract/crop just the icon portion from each image")
    print("3. Process icons for custom backside designs")
    print("4. Match with existing teams in your processed data")

if __name__ == "__main__":
    main()
