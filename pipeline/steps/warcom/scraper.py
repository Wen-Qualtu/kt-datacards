"""Scrape + download Kill Team team-rules PDFs from warhammer-community.

Standalone port of the legacy step-1 scraper. Uses Playwright to render the
JavaScript download page, locate the "Team Rules" section, and collect PDF URLs;
``requests`` to download.
"""
from __future__ import annotations

import logging
from pathlib import Path

import requests
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

DOWNLOADS_URL = "https://www.warhammer-community.com/en-gb/downloads/kill-team/"

# Files that live in the Team Rules section but are not a single team's rules.
_EXCLUDE_PATTERNS = (
    "key_download", "key-download",
    "mission_pack", "missionpack", "mission-pack", "mission pack",
    "ctesiphus_expedition", "ctesiphus-expedition",
    "core_rules", "core-rules",
    "update_log", "update-log",
    "universal_equipment", "universal-equipment",
    "lite_rules", "lite-rules",
    "sniper_rules", "sniper-rules",
    "key rule", "critical operation",
    "gallowdark", "into the dark",
    "shadowvaults", "chalnath", "octarius",
)


def _absolute_url(href: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://www.warhammer-community.com{href}"
    return f"https://assets.warhammer-community.com/{href}"


def _is_team_rules_file(filename: str, link_text: str) -> bool:
    filename = filename.lower()
    link_text = link_text.lower()
    return not any(p in filename or p in link_text for p in _EXCLUDE_PATTERNS)


async def _expand_section(page, heading: str) -> object | None:
    """Find + expand a named download section and return its container locator.

    ``heading`` is the section title as shown on the page (e.g. ``"Team Rules"``
    or ``"Recently Added"``); matching is case-insensitive substring.
    """
    selectors = [
        f'h2:has-text("{heading}")',
        f'h3:has-text("{heading}")',
        f'h4:has-text("{heading}")',
        f'button:has-text("{heading}")',
        f'summary:has-text("{heading}")',
        f'[aria-label*="{heading}"]',
    ]
    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if await elem.count() == 0:
                continue
            logger.info(f"Found '{heading}' section with: {selector}")
            # The accordion toggle is the heading's enclosing button; expand if collapsed.
            toggle = elem.locator("xpath=ancestor-or-self::button[1]").first
            toggle = toggle if await toggle.count() > 0 else elem
            if await toggle.get_attribute("aria-expanded") == "false":
                await toggle.click(timeout=3000)
                await page.wait_for_timeout(2000)
            # This section's links live in its OWN accordion item (nearest ancestor
            # div with the item border class), NOT the outer <section> that wraps
            # every accordion (which would mix Recently Added + Team Rules + …).
            container = elem.locator(
                "xpath=ancestor::div[contains(@class,'border-b')][1]"
            ).first
            if await container.count() > 0:
                return container
            container = elem.locator(
                "xpath=ancestor::div[contains(@class, 'accordion')][1] | ancestor::details[1]"
            ).first
            if await container.count() > 0:
                return container
            sibling = elem.locator("xpath=following-sibling::*[1]").first
            if await sibling.count() > 0:
                return sibling
        except Exception:
            continue
    return None


async def extract_pdf_urls_from_page(
    url: str = DOWNLOADS_URL, section: str = "Team Rules"
) -> list[str]:
    """Return team-rules PDF URLs from a named section of the Kill Team downloads page.

    ``section`` selects which page accordion to read: the default ``"Team Rules"``
    (all teams) or ``"Recently Added"`` (only the PDFs updated in the latest
    balance dataslate / release). Non-team files (update logs, mission packs,
    companions, …) are filtered out of either section by ``_is_team_rules_file``.
    """
    logger.info("Launching browser to fetch Kill Team downloads page...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            logger.info(f"Loading page: {url}")
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Dismiss cookie consent overlay if present.
            try:
                await page.evaluate(
                    "document.getElementById('onetrust-consent-sdk')?.remove()"
                )
                await page.wait_for_timeout(500)
            except Exception:
                pass

            container = await _expand_section(page, section)

            team_pdfs: list[str] = []
            if container is not None:
                for link in await container.locator('a[href*=".pdf"]').all():
                    href = await link.get_attribute("href")
                    text = (await link.inner_text()) or ""
                    if not href:
                        continue
                    full_url = _absolute_url(href)
                    if _is_team_rules_file(Path(full_url).name, text):
                        team_pdfs.append(full_url)
            elif section == "Team Rules":
                logger.warning(
                    "Team Rules container not found; falling back to filename filter"
                )
                for link in await page.locator('a[href*=".pdf"]').all():
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    full_url = _absolute_url(href)
                    name = Path(full_url).name.lower()
                    if ("team_rules" in name or "teamrules" in name or "_online_rules" in name) \
                            and _is_team_rules_file(name, ""):
                        team_pdfs.append(full_url)
            else:
                logger.warning(
                    f"'{section}' section not found; no reliable filename fallback"
                )
        finally:
            await browser.close()

    team_pdfs = list(dict.fromkeys(team_pdfs))  # de-dup, preserve order
    logger.info(f"Found {len(team_pdfs)} PDFs in section '{section}'")
    return team_pdfs


def download_pdf(url: str, output_path: Path, chunk_size: int = 8192) -> bool:
    """Download a PDF to ``output_path``. Returns True on success."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"  download failed: {e}")
        return False
