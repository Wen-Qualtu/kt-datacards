#!/usr/bin/env python3
"""Debug script to inspect the Warhammer Community page structure."""

import requests
from bs4 import BeautifulSoup
import re

url = "https://www.warhammer-community.com/en-gb/articles/xfV8vUOg/download-the-kill-team-app-and-faction-rules-today/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

response = requests.get(url, headers=headers, timeout=30)
soup = BeautifulSoup(response.text, 'html.parser')

# Find all links to team rules PDFs
pdf_links = soup.find_all('a', href=re.compile(r'warcomprod.*\.pdf'))

print(f"Found {len(pdf_links)} PDF links\n")

for i, link in enumerate(pdf_links[:3], 1):  # Show first 3
    print(f"\n--- Link {i} ---")
    pdf_url = link.get('href')
    print(f"PDF URL: {pdf_url}")
    
    # Extract team name from URL
    match = re.search(r'team-rules/([^/]+)/', pdf_url)
    if match:
        team_slug = match.group(1)
        print(f"Team slug: {team_slug}")
    
    # Check parent div - icons might be background images
    parent = link.parent
    if parent:
        print(f"\nParent tag: {parent.name}")
        print(f"Parent classes: {parent.get('class')}")
        print(f"Parent style: {parent.get('style')}")
        
        # Check for background image in style
        style = parent.get('style', '')
        if 'background' in style:
            print(f"Has background!")
            # Extract URL from style
            bg_match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
            if bg_match:
                print(f"Background URL: {bg_match.group(1)}")
        
        # Check siblings
        siblings = parent.find_all(['img', 'picture'])
        print(f"Sibling images/pictures: {len(siblings)}")
        for sib in siblings:
            if sib.name == 'img':
                print(f"  - img src: {sib.get('src')}")
            elif sib.name == 'picture':
                sources = sib.find_all('source')
                for src in sources:
                    print(f"  - picture source: {src.get('srcset')}")
