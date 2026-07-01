"""Front-end (kt-app track): identify type + split per page.

input/*.pdf  ->  layers/kt-app/extracted/{team}/cards/{type}/{team}-{type}-page_N.pdf

Single step (the production ``processed`` stage is dropped — straight to extracted).

PORT-FROM: pipelines/kt-app/steps/1_process_pdfs.py
  (PDFProcessor.identify_pdf -> _identify_card_type / _identify_team_name, split_pdf_to_pages)
SOURCE-DECISION: n/a (kt-app only). Identification is content-based, never filename.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from ..utils import paths
from ..utils.team_identification import CardType, Team, TeamIdentifier

logger = logging.getLogger(__name__)

TRACK = "kt-app"


# ---------------------------------------------------------------------------
# Content-based identification (ported from kt-app step 1)
# ---------------------------------------------------------------------------
def _identify_card_type(page) -> Optional[CardType]:
    all_text = page.get_text()
    lines = [line.strip() for line in all_text.split("\n") if line.strip()]

    stat_keywords = ["APL", "WS", "BS", "STR", "DF", "GA", "SV", "WOUNDS", "SAVE", "MOVE"]
    stats_found = []
    for line in lines[-15:]:
        line_upper = line.upper().strip()
        if line_upper in stat_keywords:
            stats_found.append(line_upper)
        else:
            for keyword in ["APL", "WS", "BS", "STR", "DF", "GA", "SV"]:
                if f" {keyword} " in f" {line_upper} " or f" {keyword}:" in f" {line_upper} ":
                    stats_found.append(keyword)
        if "RULES CONTINUE" in line_upper:
            return CardType.DATACARDS

    if len(set(stats_found)) >= 2:
        return CardType.DATACARDS

    text_dict = page.get_text("dict")
    text_by_size = []
    for block in text_dict["blocks"]:
        if block["type"] == 0:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    if text and len(text) > 3:
                        text_by_size.append((size, text.upper()))
    text_by_size.sort(reverse=True, key=lambda x: x[0])

    for _size, text in text_by_size[:30]:
        text_lower = text.lower()
        if "operatives" == text_lower.strip():
            return CardType.OPERATIVES
        elif "faction equipment" in text_lower or "equipment" == text_lower.strip():
            return CardType.EQUIPMENT
        elif "strategy ploy" in text_lower or "strategic ploy" in text_lower:
            return CardType.STRATEGY_PLOYS
        elif "firefight ploy" in text_lower:
            return CardType.FIREFIGHT_PLOYS
        elif "marker/token guide" in text_lower:
            return CardType.TOKEN_GUIDE
        elif "faction rule" in text_lower:
            return CardType.FACTION_RULES
    return None


def _identify_team_name(page, card_type: Optional[CardType], identifier: TeamIdentifier) -> Optional[str]:
    rect = page.rect
    is_landscape = rect.width > rect.height
    all_text = page.get_text()
    lines = [line.strip() for line in all_text.split("\n") if line.strip()]

    if card_type == CardType.DATACARDS and is_landscape:
        for line in lines[-30:]:
            if line.upper() in ["APL", "WOUNDS", "SAVE", "MOVE", "HIT", "DMG", "WR", "ATK", "NAME"]:
                continue
            if line.isdigit() or len(line) < 5:
                continue
            if "," in line and line.count(",") >= 2:
                team_candidate = [p.strip() for p in line.split(",")][0]
                if identifier.identify_team(team_candidate):
                    return team_candidate
    elif card_type == CardType.DATACARDS and not is_landscape:
        for line in lines[:10]:
            line_upper = line.upper()
            if " TEAM" in line_upper or line_upper.endswith("TEAM"):
                team_candidate = line_upper.replace(" TEAM", "").strip()
                if identifier.identify_team(team_candidate):
                    return team_candidate

    text_dict = page.get_text("dict")
    text_by_size = []
    for block in text_dict["blocks"]:
        if block["type"] == 0:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    size = span["size"]
                    if text and len(text) > 3:
                        text_by_size.append((size, text))
    text_by_size.sort(reverse=True, key=lambda x: x[0])

    for _size, text in text_by_size[:20]:
        if len(text) > 5:
            if identifier.identify_team(text):
                return text
            if "," in text:
                for part in text.split(","):
                    part = part.strip()
                    if len(part) > 3 and identifier.identify_team(part):
                        return part
            if " " in text:
                for word in text.split():
                    word = word.strip()
                    if len(word) > 3 and identifier.identify_team(word):
                        return word

    for line in lines:
        if len(line) > 5:
            if identifier.identify_team(line):
                return line
            for word in line.split():
                word = word.strip(",.;:")
                if len(word) > 3 and identifier.identify_team(word):
                    return word
    return None


def identify_pdf(pdf_path: Path, identifier: TeamIdentifier) -> tuple[Optional[Team], Optional[CardType]]:
    try:
        pdf = fitz.open(pdf_path)
        page = pdf[0]
        card_type = _identify_card_type(page)
        team_name = _identify_team_name(page, card_type, identifier)
        pdf.close()
        if not team_name or not card_type:
            logger.warning(f"Could not identify {pdf_path.name}: team={team_name}, type={card_type}")
            return None, None
        team = identifier.identify_team(team_name)
        if not team:
            logger.error(f"Team '{team_name}' not in config for {pdf_path.name}")
            return None, None
        return team, card_type
    except Exception as e:
        logger.error(f"Error identifying {pdf_path}: {e}")
        return None, None


def split_pdf_to_pages(pdf_path: Path, cards_dir: Path, prefix: str, card_type: str) -> list[Path]:
    type_dir = cards_dir / card_type
    type_dir.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open(pdf_path)
    page_files = []
    for page_num in range(len(pdf)):
        single = fitz.open()
        single.insert_pdf(pdf, from_page=page_num, to_page=page_num)
        out = type_dir / f"{prefix}-page_{page_num}.pdf"
        single.save(out)
        single.close()
        page_files.append(out)
    pdf.close()
    return page_files


# ---------------------------------------------------------------------------
# Step entry point
# ---------------------------------------------------------------------------
def run(teams=None, source=None, force=False):
    identifier = TeamIdentifier()
    input_pdfs = sorted(paths.INPUT.glob("*.pdf"))
    logger.info(f"Found {len(input_pdfs)} PDFs in {paths.INPUT}")

    stats = {"identified": 0, "processed": 0, "pages": 0, "skipped": 0, "failed": 0}

    for pdf_path in input_pdfs:
        team, card_type = identify_pdf(pdf_path, identifier)
        if not team or not card_type:
            stats["failed"] += 1
            continue
        stats["identified"] += 1
        if teams and team.name not in teams:
            stats["skipped"] += 1
            continue

        cards_dir = paths.extracted_dir(TRACK) / team.name / "cards"
        prefix = f"{team.name}-{card_type.value}"
        page_files = split_pdf_to_pages(pdf_path, cards_dir, prefix, card_type.value)
        logger.info(f"  {team.name}/{card_type.value}: {len(page_files)} pages -> {cards_dir / card_type.value}")
        stats["processed"] += 1
        stats["pages"] += len(page_files)

    logger.info(
        f"kt-app front-end done: identified={stats['identified']} processed={stats['processed']} "
        f"pages={stats['pages']} skipped={stats['skipped']} failed={stats['failed']}"
    )
    return stats
