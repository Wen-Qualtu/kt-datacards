"""
Step 1: Scrape Kill Team PDFs from Warhammer Community downloads page.
Uses Playwright to render JavaScript and extract PDF links from collapsible sections.
"""

import requests
from pathlib import Path
import argparse
import time
import asyncio
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


async def extract_pdf_urls_from_page(url: str) -> list[str]:
    """
    Extract PDF URLs from the Warhammer Community Kill Team page.
    Uses Playwright to render JavaScript and expand collapsible sections.
    """
    logger.info("Launching browser to fetch Kill Team downloads page...")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        logger.info(f"Loading page: {url}")
        await page.goto(url, wait_until='networkidle')
        
        logger.info("Waiting for page to load...")
        await page.wait_for_timeout(2000)  # Wait 2 seconds for initial load
        
        # Handle cookie consent banner if present
        try:
            logger.info("Checking for cookie banner...")
            # Try to close/hide the cookie banner by injecting CSS or clicking reject/close
            await page.evaluate("document.getElementById('onetrust-consent-sdk')?.remove()")
            await page.wait_for_timeout(500)
        except:
            pass
        
        # First, try to get PDF links that are already in the DOM
        logger.info("Extracting PDF URLs from DOM...")
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
        
        logger.info(f"Found {len(pdf_urls_found)} PDFs already in DOM")
        
        # Find and expand the Team Rules section specifically
        logger.info("Looking for Team Rules section...")
        
        team_rules_pdfs = []
        try:
            # Try to find the Team Rules heading/section
            # Common patterns: h2, h3, or button with "Team Rules" text
            team_rules_container = None
            
            # Try different selectors to find Team Rules section
            selectors_to_try = [
                'h2:has-text("Team Rules")',
                'h3:has-text("Team Rules")',
                'button:has-text("Team Rules")',
                'summary:has-text("Team Rules")',
                '[aria-label*="Team Rules"]'
            ]
            
            for selector in selectors_to_try:
                try:
                    elem = page.locator(selector).first
                    if await elem.count() > 0:
                        logger.info(f"Found Team Rules section with: {selector}")
                        
                        # Check if it's a collapsible button
                        aria_expanded = await elem.get_attribute('aria-expanded')
                        if aria_expanded == 'false':
                            logger.info("Expanding Team Rules section...")
                            await elem.click(timeout=3000)
                            await page.wait_for_timeout(2000)
                        
                        # Get the parent container (section, div, details, etc.)
                        # Navigate up to find the container with all PDFs
                        team_rules_container = elem.locator('xpath=ancestor::section | ancestor::div[contains(@class, "accordion")] | ancestor::details').first
                        if await team_rules_container.count() > 0:
                            logger.info("Found Team Rules container")
                            break
                        else:
                            # Try sibling approach - next element might be the content
                            team_rules_container = elem.locator('xpath=following-sibling::*[1]').first
                            if await team_rules_container.count() > 0:
                                logger.info("Found Team Rules container (sibling)")
                                break
                except Exception as e:
                    continue
            
            # If we found the container, get all PDF links within it
            if team_rules_container and await team_rules_container.count() > 0:
                logger.info("Extracting PDFs from Team Rules section...")
                pdf_links = await team_rules_container.locator('a[href*=".pdf"]').all()
                
                for link in pdf_links:
                    href = await link.get_attribute('href')
                    text = await link.inner_text()
                    if href:
                        # Make absolute URL
                        if href.startswith('http'):
                            full_url = href
                        elif href.startswith('/'):
                            full_url = f"https://www.warhammer-community.com{href}"
                        else:
                            full_url = f"https://assets.warhammer-community.com/{href}"
                        
                        # Filter out obvious non-team files
                        filename = Path(full_url).name.lower()
                        text_lower = text.lower()
                        
                        # Exclude mission packs, key downloads, and other non-team files
                        exclude_patterns = [
                            'key_download', 'key-download',
                            'mission_pack', 'missionpack', 'mission-pack',
                            'mission pack',  # Match text content
                            'ctesiphus_expedition', 'ctesiphus-expedition',
                            'core_rules', 'core-rules',
                            'update_log', 'update-log',
                            'universal_equipment', 'universal-equipment',
                            'lite_rules', 'lite-rules',
                            'sniper_rules', 'sniper-rules',
                            'key rule', 'critical operation',  # Additional patterns
                            'gallowdark', 'into the dark',  # Mission pack names
                            'shadowvaults', 'chalnath', 'octarius'  # More mission packs
                        ]
                        
                        should_include = True
                        for pattern in exclude_patterns:
                            if pattern in filename or pattern in text_lower:
                                should_include = False
                                break
                        
                        if should_include:
                            team_rules_pdfs.append((full_url, text.strip()))
                
                logger.info(f"Found {len(team_rules_pdfs)} PDFs in Team Rules section")
            else:
                logger.warning("Could not locate Team Rules container, falling back to filename filtering...")
                raise Exception("Fallback to old method")
                
        except Exception as e:
            logger.warning(f"Team Rules section approach failed: {e}")
            logger.info("Falling back to expand all sections and filter by filename...")
            
            # Fallback: expand all collapsed sections
            try:
                # Look for various button types that might expand sections
                button_selectors = [
                    'button[aria-expanded="false"]',
                    '[role="button"][aria-expanded="false"]',
                    'summary',
                    '.accordion-button'
                ]
                
                for selector in button_selectors:
                    try:
                        buttons = await page.locator(selector).all()
                        for btn in buttons[:10]:
                            try:
                                await btn.click(timeout=2000, force=True)
                                await page.wait_for_timeout(300)
                            except:
                                pass
                    except:
                        pass
                
                await page.wait_for_timeout(2000)
            except:
                pass
        
        # If we successfully got PDFs from Team Rules section, use those
        # Otherwise fall back to getting all PDFs and filtering
        if team_rules_pdfs:
            pdf_urls = team_rules_pdfs
        else:
            logger.info("Using fallback: extracting all PDFs and filtering...")
            # Get PDF links again after expanding
            pdf_links = await page.locator('a[href*=".pdf"]').all()
            
            pdf_urls = []
            for link in pdf_links:
                href = await link.get_attribute('href')
                text = await link.inner_text()
                if href:
                    # Make absolute URL
                    if href.startswith('http'):
                        pdf_urls.append((href, text.strip()))
                    elif href.startswith('/'):
                        pdf_urls.append((f"https://www.warhammer-community.com{href}", text.strip()))
                    else:
                        pdf_urls.append((f"https://assets.warhammer-community.com/{href}", text.strip()))
            
            # Filter to team rules only
            team_rules_pdfs = []
            for url, text in pdf_urls:
                filename = Path(url).name.lower()
                if ('team_rules' in filename or 'teamrules' in filename or '_online_rules' in filename) and \
                   'key_download' not in filename and \
                   'mission_pack' not in filename and \
                   'ctesiphus_expedition' not in filename and \
                   'core_rules' not in filename:
                    team_rules_pdfs.append((url, text))
            
            pdf_urls = team_rules_pdfs
        
        await browser.close()
        
        # Remove duplicates (same URL can appear multiple times)
        pdf_urls = list(dict.fromkeys(pdf_urls))  # Preserves order, removes duplicates
        
        # Debug: show what we found
        logger.info(f"Found {len(pdf_urls)} team rule PDFs (after deduplication)")
        if pdf_urls:
            logger.info("\nTeam Rules PDFs:")
            for url, text in sorted(pdf_urls, key=lambda x: x[1])[:10]:
                logger.info(f"  '{text}' -> {Path(url).name}")
            if len(pdf_urls) > 10:
                logger.info(f"  ... and {len(pdf_urls) - 10} more")
        
        # Return just the URLs
        return [url for url, text in pdf_urls]


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
        logger.error(f"    x Error: {e}")
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
    
    logger.info("=" * 70)
    logger.info("Step 1: Scrape Warhammer Community Kill Team Downloads")
    logger.info("=" * 70)
    logger.info("")
    
    # Extract PDF URLs from the page
    try:
        team_pdf_urls = asyncio.run(extract_pdf_urls_from_page(url))
    except Exception as e:
        logger.error(f"Error extracting PDF URLs: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'downloaded': 0, 'skipped': 0, 'failed': 0}
    
    if not team_pdf_urls:
        logger.error("No team PDFs found!")
        return {'success': False, 'downloaded': 0, 'skipped': 0, 'failed': 0}
    
    logger.info("")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Downloading {len(team_pdf_urls)} PDFs:")
    logger.info("-" * 70)
    
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
            logger.info(f"  [{idx}/{len(team_pdf_urls)}] {filename}")
            logger.info(f"    * Already exists, skipping")
            skipped_count += 1
            continue
        
        logger.info(f"  [{idx}/{len(team_pdf_urls)}] {filename}")
        logger.info(f"    Downloading...")
        
        if download_pdf(pdf_url, output_path):
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"    + Downloaded: {file_size_mb:.2f} MB")
            downloaded_count += 1
        else:
            logger.error(f"    x Failed to download")
            failed_count += 1
        
        # Delay between downloads to be respectful
        if idx < len(team_pdf_urls):
            time.sleep(delay)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Download complete!")
    logger.info(f"  Downloaded: {downloaded_count}")
    logger.info(f"  Skipped: {skipped_count}")
    logger.info(f"  Failed: {failed_count}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 70)
    
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
