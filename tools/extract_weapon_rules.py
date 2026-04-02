"""
Extract Weapon Rules from Kill Team Lite Rules PDF

Extracts special weapon rules and their descriptions from the last page of the
Kill Team Lite Rules PDF and saves them as JSON.

Input:  layers/warcom/staging/eng_*_kt_lite_rules*.pdf
Output: config/weapon_rules.json

Usage:
    python tools/extract_weapon_rules.py
    python tools/extract_weapon_rules.py --output config/weapon_rules.yaml
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

import fitz  # PyMuPDF

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def find_lite_rules_pdf() -> Path:
    """Find the Kill Team Lite Rules PDF in staging."""
    staging_dir = Path("layers/warcom/staging")
    
    # Look for lite rules PDF
    pdfs = list(staging_dir.glob("*lite*rules*.pdf"))
    
    if not pdfs:
        raise FileNotFoundError(
            f"No lite rules PDF found in {staging_dir}. "
            "Please run the warcom scraper first."
        )
    
    if len(pdfs) > 1:
        logger.warning("Multiple lite rules PDFs found, using: %s", pdfs[0].name)
    
    return pdfs[0]


def extract_weapon_rules_from_pdf(pdf_path: Path) -> Dict[str, str]:
    """Extract weapon rules from the last page of the PDF.
    
    Weapon rules are formatted as:
    - Each rule is in its own text block
    - Rule name in bold (may include variables in italic): "Accurate x:"
    - Description in regular font within the same block
    
    Returns:
        Dictionary mapping rule names to descriptions
    """
    doc = fitz.open(pdf_path)
    
    # Get last page
    last_page_num = len(doc) - 1
    page = doc[last_page_num]
    
    logger.info("Extracting from page %d of %d", last_page_num + 1, len(doc))
    
    # Get text blocks
    blocks_dict = page.get_text("dict")
    blocks = blocks_dict.get("blocks", [])
    
    weapon_rules = {}
    
    # Process each block
    for block in blocks:
        if block.get("type") != 0:  # Skip non-text blocks
            continue
        
        # Collect all spans in this block
        block_spans = []
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text:
                    continue
                
                font = span.get("font", "")
                is_bold = "Bd" in font or span.get("flags", 0) & 16
                
                block_spans.append({
                    "text": text,
                    "bold": is_bold
                })
        
        if not block_spans:
            continue
        
        # Check if block starts with bold text (potential rule)
        if not block_spans[0]["bold"]:
            continue
        
        # Extract rule name: collect bold text until colon
        rule_parts = []
        description_parts = []
        found_colon = False
        
        for i, span in enumerate(block_spans):
            text = span["text"]
            
            if not found_colon:
                if ":" in text:
                    # Split at colon
                    before, after = text.split(":", 1)
                    rule_parts.append(before)
                    # Add text after colon to description
                    if after.strip():
                        description_parts.append(after)
                    found_colon = True
                else:
                    rule_parts.append(text)
            else:
                # After colon found, everything is description
                description_parts.append(text)
        
        if not found_colon:
            continue
        
        rule_name = "".join(rule_parts).strip()
        
        # Skip headers/footers
        if any(skip in rule_name.upper() for skip in [
            'WEAPON RULES', 'KILL TEAM', 'PAGE',
            'WARHAMMER', 'COPYRIGHT', 'GAMES WORKSHOP'
        ]):
            continue
        
        # Collect description
        description = "".join(description_parts).strip()
        
        # Clean up description
        description = re.sub(r'©\s*Copyright.*$', '', description, flags=re.IGNORECASE).strip()
        description = re.sub(r'\s+', ' ', description)  # Normalize whitespace
        
        # Only add if we have both name and description
        if rule_name and description and len(description) > 10:
            weapon_rules[rule_name] = description
            logger.info("  ✓ %s", rule_name)
    
    doc.close()
    return weapon_rules


def save_weapon_rules(rules: Dict[str, str], output_path: Path, format: str = 'json'):
    """Save weapon rules to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format == 'json':
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
    elif format == 'yaml':
        import yaml
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(rules, f, default_flow_style=False, allow_unicode=True)
    
    logger.info("Saved %d weapon rules to: %s", len(rules), output_path)


def main():
    parser = argparse.ArgumentParser(
        description='Extract weapon rules from Kill Team Lite Rules PDF'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path('config/weapon_rules.json'),
        help='Output file path (default: config/weapon_rules.json)'
    )
    parser.add_argument(
        '--format', '-f',
        choices=['json', 'yaml'],
        default='json',
        help='Output format (default: json)'
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Kill Team Weapon Rules Extractor")
    logger.info("=" * 60)
    
    # Find PDF
    pdf_path = find_lite_rules_pdf()
    logger.info("Found: %s", pdf_path.name)
    
    # Extract rules
    weapon_rules = extract_weapon_rules_from_pdf(pdf_path)
    
    if not weapon_rules:
        logger.error("No weapon rules extracted!")
        return 1
    
    # Save
    save_weapon_rules(weapon_rules, args.output, args.format)
    
    logger.info("=" * 60)
    logger.info("Extraction complete: %d rules", len(weapon_rules))
    logger.info("=" * 60)
    
    return 0


if __name__ == '__main__':
    exit(main())
