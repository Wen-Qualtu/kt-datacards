"""Shared card type + name detection from a single-card PDF's text layer.

Used by BOTH ``build_structure`` tracks (kt-app and warcom) so the same physical
card always yields the same ``(type, name)`` — the only way to guarantee that the
two sources emit identical ``{team}-{type}-{name}.pdf`` filenames downstream.

Why this is safe to share (unlike the front-end card split):
  - It reads the PDF *text layer* only (``get_text``), never rasters. Render DPI /
    cv2 marker detection live in the per-track front end and never reach here.
  - Both tracks hand us a single-card PDF whose text layer is intact, with the
    same header order: line 0 = TEAM, line 1 = TYPE, line 2 = NAME.

Classification uses a line-index heuristic. The ``(CARD x/y)`` rule-name handling
keeps the slash-separated card index intact ("ELITE FIELDCRAFT (CARD 1/3)" ->
``...-card-1``, not ``...-card-13``).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from . import naming

logger = logging.getLogger(__name__)

# Header (line 1) text -> card-type token. Order matters: token-guide is a more
# specific match than faction-rule. Tokens match the warcom folder vocabulary so
# the existing WARCOM_TYPE_TO_KEY map keeps working.
_TYPE_HEADERS: Tuple[Tuple[str, str], ...] = (
    ("MARKER/TOKEN GUIDE", "token-guide"),
    ("FACTION RULE", "faction-rules"),
    ("EQUIPMENT", "equipment"),
    ("FIREFIGHT PLOY", "ploys/firefight"),
    ("STRATEGY PLOY", "ploys/strategy"),
)

# Faction rules that list several named options on sub-cards.
_MULTI_OPTION_RULES = ("ACCURSED GIFTS", "SANGUAVITAE")

# ---------------------------------------------------------------------------
# Special-case multi-card rule groups (HARDCODED — see note below)
# ---------------------------------------------------------------------------
# These are messy GW card groups where only the FIRST card carries the rule
# name and the continuation card(s) have no header (just option text + a
# "continues on the other side" marker). The generic line-2 name extractor
# cannot recover the rule name on those headerless continuation pages, so we
# pin the grouping by the rule name detected on the first card. Both tracks
# share this list so they group these rules identically.
#
# Kept as an explicit per-team table on purpose (for now): the layouts are
# bespoke and there is no reliable structural signal to generalise them.
#
# 3-card: one front shared across two different backs.
_THREE_CARD_SPECIAL: Tuple[Tuple[str, str], ...] = (
    ("elucidian-starstriders", "WARRANT OF TRADE"),
    ("gellerpox-infected", "TECHNO-CURSE"),
    ("hunter-clade", "DOCTRINA IMPERATIVES"),
    ("pathfinders", "MARKERLIGHTS"),
)

# 4-card: two front/back pairs (0,1) and (2,3).
_FOUR_CARD_SPECIAL: Tuple[Tuple[str, str], ...] = (
    ("angels-of-death", "CHAPTER TACTICS"),
    ("warpcoven", "BOONS OF TZEENTCH"),
)


def is_three_card_special_case(team_name: str, text: str) -> bool:
    """True for the 3-card special cases (same front, two different backs)."""
    text_upper = text.upper()
    return any(
        team_name == team and rule in text_upper
        for team, rule in _THREE_CARD_SPECIAL
    )


def is_four_card_special_case(team_name: str, text: str) -> bool:
    """True for the 4-card special cases (two pairs: 0+1, 2+3)."""
    text_upper = text.upper()
    return any(
        team_name == team and rule in text_upper
        for team, rule in _FOUR_CARD_SPECIAL
    )


def special_case_group_size(
    team_name: str, card_type: Optional[str], card_name: Optional[str], text: str
) -> int:
    """Physical-card count of a hardcoded multi-card faction rule, else 0.

    Returns 4 or 3 only when ``card`` is the *header* of a special-case rule:
    it must be a ``faction-rules`` card whose extracted name equals the rule
    slug. Requiring the name match (not just a substring of ``text``) stops the
    detector firing on unrelated cards that merely mention the rule in their
    body (e.g. pathfinders equipment referencing "markerlights").
    """
    if card_type not in ("faction-rules", "faction_rules") or not card_name:
        return 0
    text_upper = text.upper()
    for team, rule in _FOUR_CARD_SPECIAL:
        if team_name == team and rule in text_upper and naming.slug(rule) == naming.slug(card_name):
            return 4
    for team, rule in _THREE_CARD_SPECIAL:
        if team_name == team and rule in text_upper and naming.slug(rule) == naming.slug(card_name):
            return 3
    return 0


# ---------------------------------------------------------------------------
# Text reading
# ---------------------------------------------------------------------------

def read_lines(pdf_path: Path) -> List[str]:
    """Text lines of the card's first page, sorted top-to-bottom, left-to-right."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return []
        blocks = doc[0].get_text("blocks")
        doc.close()
    except Exception as e:
        logger.warning(f"text-block read failed for {pdf_path.name}: {e}")
        return []

    lines: List[str] = []
    for block in sorted(blocks, key=lambda b: (b[1], b[0])):
        for line in block[4].split("\n"):
            line = line.strip()
            if line:
                lines.append(line)
    return lines


def read_text(pdf_path: Path) -> str:
    """Raw text of the card's first page."""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            return ""
        text = doc[0].get_text()
        doc.close()
        return text
    except Exception as e:
        logger.warning(f"text read failed for {pdf_path.name}: {e}")
        return ""


def is_notes(text: str) -> bool:
    """True if the card is just a blank "NOTES" card (should be skipped)."""
    return text.strip().upper().replace(":", "").strip() == "NOTES"


def has_backside_continue(text: str) -> bool:
    """True if the card states its rules continue on the other side."""
    return bool(re.search(r"CONTINUES?\s+ON\s+(?:THE\s+)?OTHER\s+SIDE", text.upper()))


def has_own_cards(text: str) -> bool:
    """True if a datacard states its actions/rules are on their own cards.

    This is the Necron "action overflow" tag line: the operative's stat card is
    followed by separate action cards (not a front/back pair).
    """
    return "OWN CARD" in text.upper()


def is_datacard_front(text: str) -> bool:
    """True if the text is an operative stat card (the NAME/ATK/HIT/WR header).

    Used to find where an operative's action-overflow group ends (the next
    operative's stat card). Action/ability overflow cards lack this header.
    """
    head = text[:150].upper()
    return "NAME" in head and ("ATK" in head or "WR" in head or "HIT" in head)


# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------

def detect_type(lines: List[str]) -> Optional[str]:
    """Card-type token from the header (line index 1), or None if unrecognised.

    Used by the warcom track, which has no per-type folders. The kt-app track
    already knows the type from the folder and only needs ``extract_name``.
    """
    if len(lines) < 2:
        return None
    header = lines[1].upper().strip()
    for needle, card_type in _TYPE_HEADERS:
        if needle in header:
            return card_type
    return None


# ---------------------------------------------------------------------------
# Name extraction
# ---------------------------------------------------------------------------

def _clean(value: str) -> str:
    """Strip trailing stat digits and return a slug."""
    return naming.slug(value.rstrip("0123456789").strip())


def extract_name(lines: List[str]) -> Optional[str]:
    """Slug name for a non-datacard card (equipment / ploy / rule / token guide).

    Header order is TEAM(0) / TYPE(1) / NAME(2). Handles, in priority order:
    token guides, ``(CARD x/y)`` multi-part rules, multi-option rules
    (Accursed Gifts / Sanguavitae), then the plain line-2 title.
    """
    if not lines:
        return None

    # Token-guide cards have a fixed name.
    if len(lines) >= 2:
        header = lines[1].upper()
        if "MARKER" in header and "TOKEN" in header:
            return "TOKEN GUIDE"

    # "(CARD x/y)" multi-part rule (e.g. "ELITE FIELDCRAFT (CARD 1/3)").
    # Keep the slash-separated card index instead of letting the slug collapse
    # "1/3" into "13".
    card_line = next((l for l in lines if re.search(r"\(CARD\s+\d+\s*/\s*\d+\)", l, re.IGNORECASE)), None)
    if card_line:
        m = re.search(r"\(CARD\s+(\d+)\s*/\s*(\d+)\)", card_line, re.IGNORECASE)
        rule = card_line[: card_line.upper().index("(CARD")].strip()
        if m and rule:
            return f"{naming.slug(rule)}-card-{m.group(1)}"

    # Multi-option rules list each option on its own sub-card.
    first_line = lines[0].strip().upper()
    if first_line in _MULTI_OPTION_RULES:
        base = naming.slug(first_line)
        for line in lines[1:6]:
            numbered = re.match(r"^(\d+)\.?\s+(.+)", line)
            if numbered:
                option = naming.slug(numbered.group(2))
                if option:
                    return f"{base}-{option}"
            elif line and line.upper() not in ("WHEN", "EFFECT", "GOREMONGER", "CHAOS CULT"):
                option = naming.slug(line)
                if option:
                    return f"{base}-{option}"
        return base

    # Plain portrait card: the name is line index 2.
    if len(lines) >= 3:
        name = _clean(lines[2])
        if name:
            return name

    # Fallback: first all-caps title-ish line.
    for line in lines:
        if line.isupper() and 3 <= len(line) <= 50:
            name = _clean(line)
            if name:
                return name
    return None


def extract_datacard_name(lines: List[str]) -> Optional[str]:
    """Slug name (operative) for a datacard (landscape) card.

    The operative name is the first meaningful text block, skipping the stat
    header keywords/values that may sit above it.
    """
    stat_words = {"APL", "WOUNDS", "SAVE", "MOVE", "GA", "DF", "SV"}
    stat_values = {"3+", "4+", "5+", "6\"", "7\"", "8\"", "5\"", "4\""}
    for line in lines[:10]:
        upper = line.upper()
        if upper in stat_words or upper in stat_values:
            continue
        if upper.replace('"', "").replace("'", "").replace("+", "").strip().isdigit():
            continue
        if len(line) > 3 and any(c.isalpha() for c in line):
            name = line.strip()
            if name and len(name) > 2:
                return name
    return None


# ---------------------------------------------------------------------------
# Convenience: full single-card classification (warcom front-end shape)
# ---------------------------------------------------------------------------

def classify(pdf_path: Path, orientation: str) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(card_type, name)`` for one warcom card PDF.

    ``orientation`` is 'landscape' (always a datacard) or 'portrait'.
    Returns ``('notes', None)`` for blank notes cards and ``(None, None)`` when the
    type is unrecognised.
    """
    text = read_text(pdf_path)
    if is_notes(text):
        return ("notes", None)

    if orientation == "landscape":
        return ("datacards", extract_datacard_name(read_lines(pdf_path)))

    # Portrait: operative-selection has a distinctive "KILL TEAM … ARCHETYPES" head.
    upper = text.upper()
    if "KILL" in upper[:300] and "TEAM" in upper[:300] and "ARCHETYPE" in upper:
        return ("operative-selection", "OPERATIVE SELECTION")

    lines = read_lines(pdf_path)
    card_type = detect_type(lines)
    if card_type is None:
        return (None, None)
    return (card_type, extract_name(lines))
