"""Structure — per-track manifest describing each card.

layers/{track}/extracted/{team}/...  ->  layers/{track}/structure/{team}-structure.json

Per-track because the two extracted layouts differ (file naming, page/card order).
Both tracks must emit the SAME schema. Describes each card: name, type,
front/back presence, and card-group membership (multi-card rules, "CARD X/Y").

Ported from pipelines/kt-app/steps/2_classify_structure.py. Differences from the
production step:
  - Output path: layers/{track}/structure/{team}-structure.json (one file per team)
    instead of layers/kt-app/classified/{team}/structure.json.
  - Paths inside the JSON are relative to the repo ROOT.
  - No StateManager / hash change-detection (the orchestrator owns --force).
  - No token-metadata extraction (TokenExtractor). Token-guide pages are still
    classified into a `token_guide` entity list; the richer token text/labels are
    produced downstream by the dedicated token step from the content map + artwork.

The warcom track needs its own adapter to emit the same schema (see run()).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF

from ..utils import card_naming, paths
from ..utils.state import StateIndex, StateManager

logger = logging.getLogger(__name__)

# Base for relative paths written into the structure JSON.
ROOT = paths.ROOT


def _team_card_pdfs(extracted_dir: Path, team: str) -> list:
    """Every extracted card page for a team — the inputs to structure building."""
    cards_dir = extracted_dir / team / "cards"
    return sorted(cards_dir.rglob("*.pdf")) if cards_dir.exists() else []


# ===================================================================
# SPECIAL CASE DETECTION
# ===================================================================
# The hardcoded special-case rule names now live in the shared ``card_naming``
# module so both tracks group these messy multi-card rules identically.
is_three_card_special_case = card_naming.is_three_card_special_case
is_four_card_special_case = card_naming.is_four_card_special_case


# ===================================================================
# PAGE CLASSIFIER
# ===================================================================

class PageClassifier:
    """Classifies datacard pages as fronts or backs and extracts names."""

    @staticmethod
    def has_stat_header(pdf_path: Path) -> bool:
        """True if the page carries the operative stat header (APL/WOUNDS/SAVE/MOVE)
        in the top region — the primary datacard front-page signal."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                bbox = block["bbox"]
                if bbox[1] < 50:
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span.get("text", "")
                    if all(k in text for k in ("APL", "WOUNDS", "SAVE", "MOVE")):
                        doc.close()
                        return True
            doc.close()
            return False
        except Exception as e:
            logger.warning(f"Error checking stat header for {pdf_path}: {e}")
            return False

    @staticmethod
    def has_multi_card_pattern(pdf_path: Path) -> bool:
        """True if the page has a multi-card pattern like "(CARD 2/3)"."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            text = page.get_text()
            doc.close()
            text_normalized = " ".join(text.split())
            return bool(re.search(r"\(CARD\s+\d+/\d+\)", text_normalized))
        except Exception as e:
            logger.warning(f"Error checking multi-card pattern for {pdf_path}: {e}")
            return False

    @staticmethod
    def has_continue_on_back(pdf_path: Path) -> bool:
        """True if a front page indicates it continues on the back."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            text = page.get_text()
            doc.close()
            text_upper = text.upper()
            indicators = [
                "CONTINUE ON BACK",
                "CONTINUE ON OTHER SIDE",
                "CONTINUES ON OTHER SIDE",
                "RULES CONTINUE ON OTHER SIDE",
            ]
            return any(indicator in text_upper for indicator in indicators)
        except Exception as e:
            logger.warning(f"Error checking continuation for {pdf_path}: {e}")
            return False

    @staticmethod
    def has_own_cards_indicator(pdf_path: Path) -> bool:
        """True if a front page indicates actions/rules are on separate cards."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            text = page.get_text()
            doc.close()
            return "OWN CARD" in text.upper()
        except Exception as e:
            logger.warning(f"Error checking own cards indicator for {pdf_path}: {e}")
            return False

    @staticmethod
    def extract_operative_name(pdf_path: Path) -> Optional[str]:
        """Extract operative name from a datacard front page (top-left corner)."""
        try:
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return None
            page = doc[0]
            page_width = page.rect.width
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                if block.get("type") != 0:
                    continue
                bbox = block["bbox"]
                if bbox[0] < page_width * 0.6 and bbox[1] < 15:
                    text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text += span.get("text", "")
                    text = text.strip()
                    if "," in text or text.upper() in ["NAME", "ATK", "HIT", "DMG", "WR", "NOTES:", "NOTES"]:
                        continue
                    if "ACTIONS" in text.upper():
                        continue
                    if text.isupper() and 3 <= len(text) <= 50:
                        name = re.sub(r'\d+["\']?\d+\+?$', "", text).strip()
                        name = re.sub(r'\d{2,}["\']?\d+[+\-]?$', "", name).strip()
                        name = re.sub(r'^\d+["\']?\d+\+?\d*', "", name).strip()
                        name = name.rstrip('0123456789+"\'-').strip()
                        name = name.lstrip('0123456789+"\'-').strip()
                        if len(name) >= 3:
                            doc.close()
                            return name
            doc.close()
            return None
        except Exception as e:
            logger.warning(f"Error extracting name from {pdf_path}: {e}")
            return None

    @staticmethod
    def extract_card_name(pdf_path: Path) -> Optional[str]:
        """Extract card name from non-datacard pages (equipment, ploys, rules, ...).

        Delegates to the shared ``card_naming`` util so both tracks name the same
        physical card identically.
        """
        return card_naming.extract_name(card_naming.read_lines(pdf_path))


# ===================================================================
# STRUCTURE CLASSIFIER
# ===================================================================

NUMBER_PROP_NAMES = {
    "datacards": "datacard_number",
    "equipment": "equipment_number",
    "faction_rules": "faction_rule_number",
    "token_guide": "token_guide_number",
    "firefight_ploys": "ploy_number",
    "operatives_selection": "operative_selection_number",
    "strategy_ploys": "ploy_number",
}

CARD_TYPES = [
    ("datacards", "datacards"),
    ("equipment", "equipment"),
    ("faction-rules", "faction_rules"),
    ("token-guide", "token_guide"),
    ("firefight-ploys", "firefight_ploys"),
    ("operatives-selection", "operatives_selection"),
    ("strategy-ploys", "strategy_ploys"),
]


class StructureClassifier:
    """Classifies datacard pages and builds the structure mapping for one team."""

    def __init__(self, team: str, extracted_dir: Path):
        self.team = team
        self.extracted_dir = extracted_dir
        self.page_classifier = PageClassifier()
        self._token_guide_pages_cache: Optional[set] = None

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(ROOT)).replace("\\", "/")

    def _get_token_guide_pages(self) -> set:
        """Identify which faction-rules pages are token guides."""
        if self._token_guide_pages_cache is not None:
            return self._token_guide_pages_cache

        token_guide_pages: set = set()
        faction_rules_dir = self.extracted_dir / self.team / "cards" / "faction-rules"
        if not faction_rules_dir.exists():
            self._token_guide_pages_cache = token_guide_pages
            return token_guide_pages

        for page_file in faction_rules_dir.glob(f"{self.team}-faction-rules-page_*.pdf"):
            try:
                doc = fitz.open(page_file)
                text = doc[0].get_text()
                doc.close()
                if "MARKER/TOKEN GUIDE" in text:
                    token_guide_pages.add(page_file)
            except Exception as e:
                logger.debug(f"Error checking token guide in {page_file.name}: {e}")
                continue

        self._token_guide_pages_cache = token_guide_pages
        if token_guide_pages:
            logger.info(f"  Found {len(token_guide_pages)} token-guide pages in faction-rules")
        return token_guide_pages

    def classify(self) -> Optional[Dict]:
        """Classify all card types for this team into a structure dict."""
        cards_dir = self.extracted_dir / self.team / "cards"
        if not cards_dir.exists():
            logger.debug(f"No cards directory for {self.team}")
            return None

        structure: Dict = {"team": self.team}
        total_entities = 0
        for file_prefix, key in CARD_TYPES:
            result = self._classify_card_type(file_prefix, key)
            if result:
                structure[key] = result
                total_entities += len(result)

        if total_entities > 0:
            logger.info(f"    Classified {total_entities} entities across all types")
            return structure
        logger.debug(f"No cards found for {self.team}")
        return None

    def _classify_card_type(self, file_prefix: str, card_type_key: str) -> Optional[List]:
        type_dir = self.extracted_dir / self.team / "cards" / file_prefix

        if file_prefix == "token-guide":
            type_dir = self.extracted_dir / self.team / "cards" / "faction-rules"
            if not type_dir.exists():
                return None
            token_guide_pages = self._get_token_guide_pages()
            if not token_guide_pages:
                return None
            all_page_files = sorted(token_guide_pages)
        else:
            if not type_dir.exists():
                return None
            all_page_files = list(type_dir.glob(f"{self.team}-{file_prefix}-page_*.pdf"))
            if file_prefix == "faction-rules":
                token_guide_pages = self._get_token_guide_pages()
                all_page_files = [f for f in all_page_files if f not in token_guide_pages]
            all_page_files = sorted(all_page_files)

        if not all_page_files:
            return None

        all_page_files.sort(key=lambda f: int(f.stem.split("_")[-1]))
        logger.info(f"  Processing {len(all_page_files)} {file_prefix} pages")

        is_datacard_type = file_prefix == "datacards"
        is_operative_selection = file_prefix == "operatives-selection"
        is_token_guide = file_prefix == "token-guide"

        # Phase 1: identify "first" pages and extract names.
        first_pages: List[Dict] = []
        first_positions: set = set()
        last_front_name = None

        for pos, page_file in enumerate(all_page_files):
            if is_datacard_type:
                if not self.page_classifier.has_stat_header(page_file):
                    continue
                candidate_name = self.page_classifier.extract_operative_name(page_file)
                if not candidate_name or candidate_name == last_front_name:
                    continue
                name = candidate_name
                last_front_name = name
            elif is_operative_selection:
                name = "OPERATIVE SELECTION"
            elif is_token_guide:
                name = "TOKEN GUIDE"
            else:
                name = self.page_classifier.extract_card_name(page_file)

            has_own_cards = self.page_classifier.has_own_cards_indicator(page_file)
            has_continue = self.page_classifier.has_continue_on_back(page_file)

            first_pages.append({
                "position": pos,
                "path": self._rel(page_file),
                "name": name,
                "has_own_cards": has_own_cards,
                "has_continue": has_continue,
            })
            first_positions.add(pos)

        if is_datacard_type:
            logger.info(f"    Found {len(first_pages)} front pages (operatives)")
        else:
            logger.info(f"    Processing {len(all_page_files)} pages")

        # Phase 2: build card groups with pairing logic.
        cards: List[Dict] = []
        processed_positions: set = set()

        if len(first_pages) > 0:
            first_page_text = ""
            try:
                doc = fitz.open(all_page_files[first_pages[0]["position"]])
                first_page_text = doc[0].get_text()
                doc.close()
            except Exception:
                pass

            # 4-card special case: pairs (0,1) and (2,3). Faction rules only:
            # every hardcoded special case is a multi-card faction rule, and the
            # detector matches on a substring of the rule name, which also appears
            # in unrelated equipment/datacard bodies (e.g. pathfinders equipment
            # mentions "markerlights"). Scoping to faction_rules prevents those
            # false hits from corrupting other card types.
            if card_type_key == "faction_rules" and is_four_card_special_case(self.team, first_page_text):
                if len(all_page_files) >= 4:
                    logger.info("    Special case: 4-card group detected")
                    first_file = all_page_files[0]
                    if is_operative_selection:
                        card_name = "OPERATIVE SELECTION"
                    elif is_token_guide:
                        card_name = "TOKEN GUIDE"
                    else:
                        card_name = self.page_classifier.extract_card_name(first_file)

                    for pair_idx in range(2):
                        front_idx = pair_idx * 2
                        back_idx = front_idx + 1
                        if front_idx >= len(all_page_files) or back_idx >= len(all_page_files):
                            break
                        front_path = self._rel(all_page_files[front_idx])
                        back_path = self._rel(all_page_files[back_idx])
                        cards.append({
                            "card_number": len(cards) + 1,
                            "name": card_name,
                            "pages": [{
                                "type": "both",
                                "card_in_group": pair_idx + 1,
                                "front": front_path,
                                "back": back_path,
                            }],
                        })
                        processed_positions.add(front_idx)
                        processed_positions.add(back_idx)

            # 3-card special case: same front with 2 different backs. Faction rules only
            # (see the 4-card note above on why the type scope matters).
            elif card_type_key == "faction_rules" and is_three_card_special_case(self.team, first_page_text):
                if len(all_page_files) >= 3:
                    logger.info("    Special case: 3-card group detected")
                    front_path = self._rel(all_page_files[0])
                    back1_path = self._rel(all_page_files[1])
                    back2_path = self._rel(all_page_files[2])

                    if is_operative_selection:
                        name = "OPERATIVE SELECTION"
                    elif is_token_guide:
                        name = "TOKEN GUIDE"
                    else:
                        name = self.page_classifier.extract_card_name(all_page_files[0])

                    cards.append({
                        "card_number": 1,
                        "name": name,
                        "pages": [{
                            "type": "both",
                            "card_in_group": 1,
                            "front": front_path,
                            "back": back1_path,
                        }],
                    })
                    cards.append({
                        "card_number": 2,
                        "name": f"{name}-2",
                        "pages": [{
                            "type": "both",
                            "card_in_group": 1,
                            "front": front_path,
                            "back": back2_path,
                        }],
                    })
                    processed_positions.update({0, 1, 2})

        # Unified logic for all card types.
        for i, first_page in enumerate(first_pages):
            if first_page["position"] in processed_positions:
                continue

            card_name = first_page["name"]
            card_pages: List[Dict] = []

            if first_page["has_own_cards"]:
                group_start = first_page["position"]
                group_end = len(all_page_files)

                if is_datacard_type:
                    for j in range(i + 1, len(first_pages)):
                        next_first = first_pages[j]
                        if next_first["name"] != card_name:
                            group_end = next_first["position"]
                            break
                else:
                    for j in range(i + 1, len(first_pages)):
                        next_first = first_pages[j]
                        # Close the group at the next page that begins its own
                        # multi-card rule, OR whose rule title differs. Sub-cards
                        # of one rule share the same line-2 title (e.g. the five
                        # "Skill at Arms" cards), so a different title means a
                        # genuinely different rule that must not be absorbed into
                        # this group (e.g. kasrkin "Rapid Fire" following the
                        # "Skill at Arms" cards). Mirrors the warcom track, which
                        # names each card by its own header title.
                        if next_first["has_own_cards"] or next_first["name"] != card_name:
                            group_end = next_first["position"]
                            break

                pos = group_start
                card_in_group = 1
                while pos < group_end:
                    if pos in processed_positions:
                        pos += 1
                        continue

                    page_file = all_page_files[pos]
                    front_path = self._rel(page_file)
                    has_continue = self.page_classifier.has_continue_on_back(page_file)

                    if has_continue and pos + 1 < group_end:
                        current_has_card_num = self.page_classifier.has_multi_card_pattern(page_file)
                        next_has_card_num = False
                        if pos + 1 < len(all_page_files):
                            next_has_card_num = self.page_classifier.has_multi_card_pattern(all_page_files[pos + 1])

                        if current_has_card_num and next_has_card_num:
                            card_pages.append({
                                "type": "front",
                                "card_in_group": card_in_group,
                                "front": front_path,
                            })
                            processed_positions.add(pos)
                            pos += 1
                            card_in_group += 1
                            continue

                        if (pos + 1) not in first_positions or not is_datacard_type:
                            back_path = self._rel(all_page_files[pos + 1])
                            card_pages.append({
                                "type": "both",
                                "card_in_group": card_in_group,
                                "front": front_path,
                                "back": back_path,
                            })
                            processed_positions.add(pos)
                            processed_positions.add(pos + 1)
                            pos += 2
                            card_in_group += 1
                            continue

                    card_pages.append({
                        "type": "front",
                        "card_in_group": card_in_group,
                        "front": front_path,
                    })
                    processed_positions.add(pos)
                    pos += 1
                    card_in_group += 1
            else:
                front_path = first_page["path"]
                processed_positions.add(first_page["position"])

                if first_page["has_continue"]:
                    next_pos = first_page["position"] + 1
                    if next_pos < len(all_page_files):
                        current_file = all_page_files[first_page["position"]]
                        current_has_card_num = self.page_classifier.has_multi_card_pattern(current_file)
                        next_has_card_num = self.page_classifier.has_multi_card_pattern(all_page_files[next_pos])

                        if current_has_card_num and next_has_card_num:
                            card_pages.append({
                                "type": "front",
                                "card_in_group": 1,
                                "front": front_path,
                            })
                        else:
                            can_pair = not is_datacard_type or next_pos not in first_positions
                            if can_pair:
                                back_path = self._rel(all_page_files[next_pos])
                                card_pages.append({
                                    "type": "both",
                                    "card_in_group": 1,
                                    "front": front_path,
                                    "back": back_path,
                                })
                                processed_positions.add(next_pos)
                            else:
                                card_pages.append({
                                    "type": "front",
                                    "card_in_group": 1,
                                    "front": front_path,
                                })
                    else:
                        card_pages.append({
                            "type": "front",
                            "card_in_group": 1,
                            "front": front_path,
                        })
                else:
                    card_pages.append({
                        "type": "front",
                        "card_in_group": 1,
                        "front": front_path,
                    })

            if card_pages:
                cards.append({
                    "card_number": len(cards) + 1,
                    "name": card_name,
                    "pages": card_pages,
                })

        # Group cards by name into parent entities.
        grouped_entities: List[Dict] = []
        current_entity: Optional[Dict] = None

        for card in cards:
            card_name = card["name"]
            if current_entity is None or current_entity["name"] != card_name:
                if current_entity is not None:
                    grouped_entities.append(current_entity)
                number_prop = NUMBER_PROP_NAMES.get(card_type_key, f"{card_type_key}_number")
                current_entity = {
                    number_prop: len(grouped_entities) + 1,
                    "name": card_name,
                    "cards": [],
                }

            for page_data in card["pages"]:
                flattened_card = {
                    "card_number": len(current_entity["cards"]) + 1,
                    "type": page_data["type"],
                }
                if "front" in page_data:
                    flattened_card["front"] = page_data["front"]
                if "back" in page_data:
                    flattened_card["back"] = page_data["back"]
                current_entity["cards"].append(flattened_card)

        if current_entity is not None:
            grouped_entities.append(current_entity)

        logger.info(f"    Classified {len(grouped_entities)} {file_prefix}")
        return grouped_entities


# ===================================================================
# STEP ENTRY POINT
# ===================================================================

def _run_kt_app(teams: Optional[List[str]], force: bool) -> Dict:
    extracted_dir = paths.extracted_dir("kt-app")
    if not extracted_dir.exists():
        logger.error(f"No extracted directory: {extracted_dir}")
        return {"processed": 0, "skipped": 0, "failed": 0}

    if teams:
        team_dirs = [extracted_dir / t for t in teams if (extracted_dir / t).exists()]
    else:
        team_dirs = sorted(d for d in extracted_dir.iterdir() if d.is_dir())

    stats = {"processed": 0, "skipped": 0, "failed": 0, "total_cards": 0}
    structure_out_dir = paths.structure_dir("kt-app")
    structure_out_dir.mkdir(parents=True, exist_ok=True)

    for team_dir in team_dirs:
        team = team_dir.name
        logger.info(f"Processing: {team}")
        try:
            state = StateManager(team)
            inputs = _team_card_pdfs(extracted_dir, team)
            if state.can_skip("build_structure", inputs, force):
                logger.info("  = unchanged (skip)")
                stats["skipped"] += 1
                continue

            classifier = StructureClassifier(team, extracted_dir)
            structure = classifier.classify()
            if not structure:
                logger.info("  Skipped: no cards found")
                stats["skipped"] += 1
                continue

            output_file = paths.structure_file("kt-app", team)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)
            logger.info(f"  Saved: {output_file}")

            state.record_output("build_structure", "structure", output_file)
            state.record_inputs("build_structure", inputs)
            state.mark_complete("build_structure")
            state.save()

            stats["processed"] += 1
            for key in [
                "datacards", "equipment", "faction_rules", "token_guide",
                "firefight_ploys", "operatives_selection", "strategy_ploys",
            ]:
                for entity in structure.get(key, []):
                    stats["total_cards"] += len(entity["cards"])
        except Exception as e:
            logger.error(f"  Failed: {e}", exc_info=True)
            stats["failed"] += 1

    StateIndex().rebuild_and_save()
    logger.info(
        f"build_structure (kt-app) done: processed={stats['processed']} "
        f"cards={stats['total_cards']} skipped={stats['skipped']} failed={stats['failed']}"
    )
    return stats


# ===================================================================
# WARCOM ADAPTER
# ===================================================================
#
# The warcom front-end emits a flat folder of per-card single-page PDFs
# (kasrkin_pageNN_cardM_{orientation}.pdf). We classify each card with the shared
# ``card_naming`` util (same code path as kt-app), then build the SAME structure
# schema by grouping consecutive same-name cards into entities and pairing a
# "continue on the other side" card with the next card as its back.
#
# Multi-card faction-rule special cases (the hardcoded table in ``card_naming``)
# are handled inline below, mirroring the kt-app branch, so both tracks emit
# identical entities for those teams.

# warcom card-type label -> structure manifest key
WARCOM_TYPE_TO_KEY = {
    "datacards": "datacards",
    "equipment": "equipment",
    "faction-rules": "faction_rules",
    "token-guide": "token_guide",
    "ploys/firefight": "firefight_ploys",
    "ploys/strategy": "strategy_ploys",
    "operative-selection": "operatives_selection",
}


def _warcom_orientation(card_path: Path) -> str:
    return "landscape" if "landscape" in card_path.name.lower() else "portrait"


def _warcom_rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _classify_warcom_team(team: str, cards_dir: Path) -> Optional[Dict]:
    card_files = sorted(cards_dir.glob("*.pdf"))
    if not card_files:
        return None

    # Flat per-key list of (name, kind, front_rel, back_rel) preserving order.
    per_key: Dict[str, List[Dict]] = {k: [] for k in WARCOM_TYPE_TO_KEY.values()}

    skip_next = 0
    for idx, card_path in enumerate(card_files):
        if skip_next > 0:
            skip_next -= 1
            continue
        try:
            card_type, card_name = card_naming.classify(card_path, _warcom_orientation(card_path))
        except Exception as e:
            logger.warning(f"  classify failed {card_path.name}: {e}")
            continue

        if card_type == "notes" or card_type is None or not card_name:
            continue
        key = WARCOM_TYPE_TO_KEY.get(card_type)
        if key is None:
            logger.warning(f"  unmapped warcom type '{card_type}' ({card_path.name})")
            continue

        card_text = card_naming.read_text(card_path)

        # Special-case multi-card faction rules (same hardcoded table as kt-app).
        # The header card is followed by headerless continuation cards that would
        # otherwise classify as type=None and be dropped. Consume the whole group
        # here so both tracks emit identical entities. The group is always a
        # contiguous run in sorted card order (header + continuation cards).
        group_size = card_naming.special_case_group_size(team, card_type, card_name, card_text)
        if group_size and idx + group_size <= len(card_files):
            group = card_files[idx:idx + group_size]
            if group_size == 4:
                logger.info(f"    Special case: 4-card group ({card_name})")
                # Two pairs (0,1) and (2,3) -> one entity with two "both" cards.
                for a, b in ((0, 1), (2, 3)):
                    per_key[key].append({
                        "name": card_name,
                        "kind": "both",
                        "front": _warcom_rel(group[a]),
                        "back": _warcom_rel(group[b]),
                    })
            else:
                logger.info(f"    Special case: 3-card group ({card_name})")
                # Shared front, two different backs -> name and name-2.
                per_key[key].append({
                    "name": card_name,
                    "kind": "both",
                    "front": _warcom_rel(group[0]),
                    "back": _warcom_rel(group[1]),
                })
                per_key[key].append({
                    "name": f"{card_name}-2",
                    "kind": "both",
                    "front": _warcom_rel(group[0]),
                    "back": _warcom_rel(group[2]),
                })
            skip_next = group_size - 1
            continue

        # Datacard action-overflow (Necron "own cards"): the operative's stat card
        # is tagged OWN CARD and its actions sit on separate cards (not a front/back
        # pair). kt-app groups the stat card + following non-stat datacards under the
        # operative name; mirror that so both tracks emit operative-1/2/3.
        if card_type == "datacards" and card_naming.has_own_cards(card_text):
            group = [card_path]
            j = idx + 1
            while j < len(card_files):
                jtype, _ = card_naming.classify(card_files[j], _warcom_orientation(card_files[j]))
                jtext = card_naming.read_text(card_files[j])
                if jtype == "datacards" and not card_naming.is_datacard_front(jtext):
                    group.append(card_files[j])
                    j += 1
                else:
                    break
            for g in group:
                per_key[key].append({
                    "name": card_name, "kind": "front", "front": _warcom_rel(g), "back": None,
                })
            skip_next = len(group) - 1
            continue

        # Operative selection can span several cards (long operative lists). The
        # continuation cards are headerless (type=None) and would otherwise be
        # dropped. kt-app names every page "operative selection" and pairs them;
        # mirror that: gather this card + following headerless cards, then pair by
        # "continue on the other side".
        if card_type == "operative-selection":
            run = [card_path]
            j = idx + 1
            while j < len(card_files):
                jtype, _ = card_naming.classify(card_files[j], _warcom_orientation(card_files[j]))
                if jtype is None:
                    run.append(card_files[j])
                    j += 1
                else:
                    break
            k = 0
            while k < len(run):
                p = run[k]
                if card_naming.has_backside_continue(card_naming.read_text(p)) and k + 1 < len(run):
                    per_key[key].append({
                        "name": "OPERATIVE SELECTION", "kind": "both",
                        "front": _warcom_rel(p), "back": _warcom_rel(run[k + 1]),
                    })
                    k += 2
                else:
                    per_key[key].append({
                        "name": "OPERATIVE SELECTION", "kind": "front",
                        "front": _warcom_rel(p), "back": None,
                    })
                    k += 1
            skip_next = len(run) - 1
            continue

        # Faction rules can include sub-cards (e.g. inquisitorial requisition's
        # per-allied-army option cards) whose header band shows the RULE NAME
        # instead of "FACTION RULE", so detect_type returns None and they'd be
        # dropped. kt-app processes the whole faction-rules folder and names each
        # card by its line-2 title, pairing fronts with backs. Mirror that: gather
        # this header + following faction-rule / headerless cards, then pair each
        # front (named by its own title) with its continuation back.
        if card_type == "faction-rules":
            run = [card_path]
            j = idx + 1
            while j < len(card_files):
                jtype, _ = card_naming.classify(card_files[j], _warcom_orientation(card_files[j]))
                if jtype is None or jtype == "faction-rules":
                    run.append(card_files[j])
                    j += 1
                else:
                    break
            k = 0
            while k < len(run):
                p = run[k]
                pname = card_naming.extract_name(card_naming.read_lines(p))
                if card_naming.has_backside_continue(card_naming.read_text(p)) and k + 1 < len(run):
                    per_key[key].append({
                        "name": pname, "kind": "both",
                        "front": _warcom_rel(p), "back": _warcom_rel(run[k + 1]),
                    })
                    k += 2
                else:
                    per_key[key].append({
                        "name": pname, "kind": "front",
                        "front": _warcom_rel(p), "back": None,
                    })
                    k += 1
            skip_next = len(run) - 1
            continue

        front_rel = _warcom_rel(card_path)
        back_rel = None
        kind = "front"
        if card_naming.has_backside_continue(card_text) and idx + 1 < len(card_files):
            back_rel = _warcom_rel(card_files[idx + 1])
            kind = "both"
            skip_next = 1

        per_key[key].append({
            "name": card_name,
            "kind": kind,
            "front": front_rel,
            "back": back_rel,
        })

    # Group consecutive same-name cards into entities (mirrors kt-app grouping).
    structure: Dict = {"team": team}
    total = 0
    for key in [
        "datacards", "equipment", "faction_rules", "token_guide",
        "firefight_ploys", "operatives_selection", "strategy_ploys",
    ]:
        flat = per_key.get(key, [])
        if not flat:
            continue
        entities: List[Dict] = []
        current: Optional[Dict] = None
        for item in flat:
            if current is None or current["name"] != item["name"]:
                if current is not None:
                    entities.append(current)
                number_prop = NUMBER_PROP_NAMES.get(key, f"{key}_number")
                current = {number_prop: len(entities) + 1, "name": item["name"], "cards": []}
            card_obj = {"card_number": len(current["cards"]) + 1, "type": item["kind"], "front": item["front"]}
            if item["back"]:
                card_obj["back"] = item["back"]
            current["cards"].append(card_obj)
        if current is not None:
            entities.append(current)
        structure[key] = entities
        total += len(entities)

    return structure if total > 0 else None


def _run_warcom(teams: Optional[List[str]], force: bool) -> Dict:
    extracted_dir = paths.extracted_dir("warcom")
    if not extracted_dir.exists():
        logger.error(f"No extracted directory: {extracted_dir}")
        return {"processed": 0, "skipped": 0, "failed": 0}

    if teams:
        team_dirs = [extracted_dir / t for t in teams if (extracted_dir / t).exists()]
    else:
        team_dirs = sorted(d for d in extracted_dir.iterdir() if d.is_dir())

    stats = {"processed": 0, "skipped": 0, "failed": 0, "total_cards": 0}
    structure_out_dir = paths.structure_dir("warcom")
    structure_out_dir.mkdir(parents=True, exist_ok=True)

    for team_dir in team_dirs:
        team = team_dir.name
        cards_dir = team_dir / "cards"
        logger.info(f"Processing: {team}")
        try:
            state = StateManager(team)
            inputs = sorted(cards_dir.glob("*.pdf")) if cards_dir.exists() else []
            if state.can_skip("build_structure", inputs, force):
                logger.info("  = unchanged (skip)")
                stats["skipped"] += 1
                continue

            structure = _classify_warcom_team(team, cards_dir)
            if not structure:
                logger.info("  Skipped: no cards classified")
                stats["skipped"] += 1
                continue

            output_file = paths.structure_file("warcom", team)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(structure, f, indent=2, ensure_ascii=False)
            logger.info(f"  Saved: {output_file}")

            state.record_output("build_structure", "structure", output_file)
            state.record_inputs("build_structure", inputs)
            state.mark_complete("build_structure")
            state.save()

            stats["processed"] += 1
            for key in WARCOM_TYPE_TO_KEY.values():
                for entity in structure.get(key, []):
                    stats["total_cards"] += len(entity["cards"])
        except Exception as e:
            logger.error(f"  Failed: {e}", exc_info=True)
            stats["failed"] += 1

    StateIndex().rebuild_and_save()
    logger.info(
        f"build_structure (warcom) done: processed={stats['processed']} "
        f"cards={stats['total_cards']} skipped={stats['skipped']} failed={stats['failed']}"
    )
    return stats


def run(teams=None, source=None, force=False):
    if source == "kt-app":
        return _run_kt_app(teams, force)
    if source == "warcom":
        return _run_warcom(teams, force)
    raise SystemExit("build_structure requires --source kt-app|warcom")
