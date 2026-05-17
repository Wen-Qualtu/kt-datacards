"""Extract team icons from full team list screenshots.

Uses OCR to match team names next to each icon and saves the icon crop to
config/teams/{team}/tts-image/{team}-icon.png.
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2
import numpy as np
import yaml


def _normalize_name(s: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in s).split())


def _load_team_names(config_path: Path) -> Dict[str, str]:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    teams = config.get("teams", {}) or {}
    mapping: Dict[str, str] = {}
    for team_slug, data in teams.items():
        canon = str(data.get("canonical_name") or team_slug.replace("-", " ").title())
        mapping[_normalize_name(canon)] = team_slug
    return mapping


def _find_button_rects(img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thr = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rects: List[Tuple[int, int, int, int]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 700 or h < 110 or h > 200:
            continue
        rects.append((x, y, w, h))
    rects.sort(key=lambda r: r[1])
    return rects


def _crop_icon_from_button(
    roi: np.ndarray,
    *,
    icon_size: int = 128,
    offset_xy: Tuple[int, int] | None = None,
) -> np.ndarray:
    h, w = roi.shape[:2]
    if offset_xy is not None:
        ox, oy = offset_xy
        ox = max(0, min(ox, w - icon_size))
        oy = max(0, min(oy, h - icon_size))
        return roi[oy : oy + icon_size, ox : ox + icon_size]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    max_x = min(220, w - icon_size)
    max_y = max(0, h - icon_size)

    best_score = None
    best_xy = (0, 0)
    for y in range(0, max_y + 1, 2):
        for x in range(0, max_x + 1, 2):
            score = int(edges[y : y + icon_size, x : x + icon_size].sum())
            if best_score is None or score > best_score:
                best_score = score
                best_xy = (x, y)

    bx, by = best_xy
    return roi[by : by + icon_size, bx : bx + icon_size]


def _load_icon_templates(output_root: Path, team_map: Dict[str, str]) -> list[np.ndarray]:
    templates: list[np.ndarray] = []
    for team_slug in set(team_map.values()):
        icon_path = output_root / team_slug / "tts-image" / f"{team_slug}-icon.png"
        if not icon_path.exists():
            continue
        img = cv2.imread(str(icon_path))
        if img is None:
            continue
        if img.shape[0] != 128 or img.shape[1] != 128:
            img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA)
        templates.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    return templates


def _infer_icon_offset(button: np.ndarray, templates: list[np.ndarray]) -> Tuple[int, int] | None:
    if not templates:
        return None
    roi = button[:, : min(240, button.shape[1])]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    best = None
    best_xy = None
    for templ in templates:
        th, tw = templ.shape[:2]
        if gray.shape[0] < th or gray.shape[1] < tw:
            continue
        res = cv2.matchTemplate(gray, templ, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)
        if best is None or max_val > best:
            best = max_val
            best_xy = max_loc
    if best is None or best < 0.4:
        return None
    return int(best_xy[0]), int(best_xy[1])


def _ocr_text(img: np.ndarray) -> str:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        cv2.imwrite(tmp.name, thr)
        cmd = ["tesseract", tmp.name, "stdout", "--psm", "7", "-l", "eng"]
        result = subprocess.run(cmd, capture_output=True, text=True)
    text = result.stdout.strip() if result.returncode == 0 else ""
    return text


def _match_team(text: str, team_map: Dict[str, str]) -> Tuple[str | None, float]:
    norm = _normalize_name(text)
    if not norm:
        return None, 0.0

    best_name = None
    best_score = 0.0
    for canonical_norm in team_map.keys():
        score = difflib.SequenceMatcher(None, norm, canonical_norm).ratio()
        if score > best_score:
            best_score = score
            best_name = canonical_norm

    if best_name is None:
        return None, 0.0
    return team_map[best_name], best_score


def extract_icons(
    screenshots: Iterable[Path],
    team_map: Dict[str, str],
    output_root: Path,
    only_teams: set[str] | None = None,
) -> None:
    templates = _load_icon_templates(output_root, team_map)
    for screenshot in screenshots:
        img = cv2.imread(str(screenshot))
        if img is None:
            print(f"⚠ Failed to read {screenshot}")
            continue

        rects = _find_button_rects(img)
        if not rects:
            print(f"⚠ No button rects found in {screenshot}")
            continue

        print(f"{screenshot.name}: {len(rects)} button(s)")

        inferred_offset = None
        for x, y, w, h in rects:
            button = img[y : y + h, x : x + w]
            inferred_offset = _infer_icon_offset(button, templates)
            if inferred_offset is not None:
                break

        for idx, (x, y, w, h) in enumerate(rects, start=1):
            button = img[y : y + h, x : x + w]
            icon = _crop_icon_from_button(button, offset_xy=inferred_offset)

            # Text region: right of icon
            text_x = x + 200
            text_y = y + 8
            text_w = w - 220
            text_h = h - 16
            text_roi = img[text_y : text_y + text_h, text_x : text_x + text_w]
            text = _ocr_text(text_roi)

            team_slug, score = _match_team(text, team_map)
            if team_slug is None or score < 0.55:
                print(f"  #{idx}: OCR='{text}' (score {score:.2f}) -> no match")
                continue

            if only_teams and team_slug not in only_teams:
                continue

            dest_dir = output_root / team_slug / "tts-image"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{team_slug}-icon.png"
            cv2.imwrite(str(dest_path), icon)
            print(f"  ✓ {team_slug} (score {score:.2f}) -> {dest_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract team icons from screenshots")
    parser.add_argument("--screenshots", nargs="+", required=True, help="Screenshot PNG files")
    parser.add_argument(
        "--teams",
        nargs="*",
        default=None,
        help="Optional team slugs to extract (e.g., celestian-insidiants murderwings)",
    )
    parser.add_argument(
        "--config",
        default="config/team-config.yaml",
        help="Path to team config",
    )
    parser.add_argument(
        "--output-root",
        default="config/teams",
        help="Root output directory for team icons",
    )

    args = parser.parse_args()

    team_map = _load_team_names(Path(args.config))
    only_teams = set(args.teams) if args.teams else None
    screenshots = [Path(p) for p in args.screenshots]

    extract_icons(screenshots, team_map, Path(args.output_root), only_teams=only_teams)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
