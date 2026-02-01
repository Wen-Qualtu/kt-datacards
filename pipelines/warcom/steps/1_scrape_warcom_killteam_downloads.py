"""
Step 1: Scrape Kill Team PDFs from Warhammer Community downloads page.
Uses Playwright to render JavaScript and extract PDF links from collapsible sections.
"""

import requests
from pathlib import Path
import argparse
import time
import asyncio
from playwright.async_api import async_playwright


async def extract_pdf_urls_from_page(url: str) -> list[str]:
    """
    Extract PDF URLs from the Warhammer Community Kill Team page.
    Uses Playwright to render JavaScript and expand collapsible sections.
    """
    print("Launching browser to fetch Kill Team downloads page...")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Loading page: {url}")
        await page.goto(url, wait_until='networkidle')
        
        print("Waiting for page to load...")
        await page.wait_for_timeout(2000)  # Wait 2 seconds for initial load
        
        # Handle cookie consent banner if present
        try:
            print("Checking for cookie banner...")
            # Try to close/hide the cookie banner by injecting CSS or clicking reject/close
            await page.evaluate("document.getElementById('onetrust-consent-sdk')?.remove()")
            await page.wait_for_timeout(500)
        except:
            pass
        
        # First, try to get PDF links that are already in the DOM
        print("Extracting PDF URLs from DOM...")
        pdf_links = await page.locator('a[href*=".pdf"]').all()
        
        pdf_urls_found = []
        for link in pdf_links:
            href = await link.get_attribute('href')
            if href and href.endswith('.pdf'):
                if href.startswith('http'):
                    pdf_urls_found.append(href)
                elif href.startswith('/'):
                    pdf_urls_found.append(f"https://www.warhammer-community.com{href}")
                else:
                    pdf_urls_found.append(f"https://assets.warhammer-community.com/{href}")
        
        print(f"Found {len(pdf_urls_found)} PDFs already in DOM")
        
        # If we didn't find many, try expanding sections
        if len(pdf_urls_found) < 10:
            print("Not many PDFs found, trying to expand collapsible sections...")
            
            # Find all collapsible buttons/headers and click them
            try:
                buttons = page.locator('button, [role="button"]').all()
                count = await buttons.count()
                print(f"Found {count} clickable elements, trying to expand...")
                
                for i in range(min(count, 20)):  # Limit to first 20 to avoid timeout
                    try:
                        btn = buttons.nth(i)
                        aria_expanded = await btn.get_attribute('aria-expanded')
                        if aria_expanded == 'false':
                            await btn.click(timeout=2000, force=True)
                            await page.wait_for_timeout(300)
                    except:
                        pass
            except:
                print("Could not expand sections, continuing with what we have...")
        
        # Get PDF links again after expanding
        print("Re-extracting PDF URLs...")
        pdf_links = await page.locator('a[href*=".pdf"]').all()
        
        pdf_urls = []
        for link in pdf_links:
            href = await link.get_attribute('href')
            if href:
                # Make absolute URL if needed
                if href.startswith('http'):
                    pdf_urls.append(href)
                elif href.startswith('/'):
                    pdf_urls.append(f"https://www.warhammer-community.com{href}")
                else:
                    pdf_urls.append(f"https://assets.warhammer-community.com/{href}")
        
        await browser.close()
        
        print(f"Found {len(pdf_urls)} PDF URLs")
        
        # Filter to only team rules PDFs
        team_pdfs = []
        for url in sorted(set(pdf_urls)):
            filename = Path(url).name.lower()
            
            # Include: team_rules or kt_teamrules
            # Exclude: key_download, mission_pack, ctesiphus_expedition, core_rules, etc.
            if ('team_rules' in filename or 'teamrules' in filename) and \
               'key_download' not in filename and \
               'mission_pack' not in filename and \
               'missionpack' not in filename and \
               'ctesiphus_expedition' not in filename:
                team_pdfs.append(url)
        
        print(f"Filtered to {len(team_pdfs)} team rule PDFs")
        
        return team_pdfs


def download_pdf(url: str, output_path: Path, chunk_size: int = 8192) -> bool:
    """Download a PDF file."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
        
        return True
    except Exception as e:
        print(f"    x Error: {e}")
        return False


def run(output_dir: Path = None, url: str = None, delay: float = 1.0) -> dict:
    """
    Main function to scrape and download Kill Team PDFs.
    
    Args:
        output_dir: Directory to save PDFs (default: layers/warcom/staging/)
        url: Warhammer Community downloads page URL
        delay: Delay between downloads in seconds
        
    Returns:
        dict with 'success', 'downloaded', 'skipped', 'failed' counts
    """
    if output_dir is None:
        output_dir = Path('layers/warcom/staging')
    
    if url is None:
        url = 'https://www.warhammer-community.com/en-gb/downloads/kill-team/'
    
    print("=" * 70)
    print("Step 1: Scrape Warhammer Community Kill Team Downloads")
    print("=" * 70)
    print()
    
    # Extract PDF URLs from the page
    try:
        team_pdf_urls = asyncio.run(extract_pdf_urls_from_page(url))
    except Exception as e:
        print(f"Error extracting PDF URLs: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'downloaded': 0, 'skipped': 0, 'failed': 0}
    
    if not team_pdf_urls:
        print("No team PDFs found!")
        return {'success': False, 'downloaded': 0, 'skipped': 0, 'failed': 0}
    
    print()
    print(f"Output: {output_dir}")
    print(f"Downloading {len(team_pdf_urls)} PDFs:")
    print("-" * 70)
    
    # Download each PDF
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0
    
    for idx, pdf_url in enumerate(team_pdf_urls, 1):
        # Extract filename from URL
        filename = Path(pdf_url).name
        output_path = output_dir / filename
        
        # Skip if already exists
        if output_path.exists():
            print(f"  [{idx}/{len(team_pdf_urls)}] {filename}")
            print(f"    * Already exists, skipping")
            skipped_count += 1
            continue
        
        print(f"  [{idx}/{len(team_pdf_urls)}] {filename}")
        print(f"    Downloading...", end='', flush=True)
        
        if download_pdf(pdf_url, output_path):
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"\r    + Downloaded: {file_size_mb:.2f} MB")
            downloaded_count += 1
        else:
            print(f"\r    x Failed to download")
            failed_count += 1
        
        # Delay between downloads to be respectful
        if idx < len(team_pdf_urls):
            time.sleep(delay)
    
    print()
    print("=" * 70)
    print(f"Download complete!")
    print(f"  Downloaded: {downloaded_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Output: {output_dir}")
    print("=" * 70)
    
    return {
        'success': failed_count == 0,
        'downloaded': downloaded_count,
        'skipped': skipped_count,
        'failed': failed_count
    }


def main():
    parser = argparse.ArgumentParser(
        description='Step 1: Scrape and download Kill Team PDFs from Warhammer Community'
    )
    parser.add_argument('--url', type=str,
                       default='https://www.warhammer-community.com/en-gb/downloads/kill-team/',
                       help='Kill Team downloads page URL')
    parser.add_argument('--output', type=Path, default=Path('layers/warcom/staging'),
                       help='Output directory (default: layers/warcom/staging)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between downloads in seconds (default: 1.0)')
    
    args = parser.parse_args()
    
    result = run(output_dir=args.output, url=args.url, delay=args.delay)
    
    # Exit with error code if failed
    if not result['success']:
        exit(1)


if __name__ == '__main__':
    main()
