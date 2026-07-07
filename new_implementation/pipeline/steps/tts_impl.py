"""
Step 7: Generate TTS Objects (with embedded stats)

Generates Tabletop Simulator (TTS) JSON save files from classified cards.
Embeds operative stats (GMNotes + Lua scripts) directly during generation.

Prerequisites:
    Step 3: Team data extracted (for stat embedding)
    Step 6: TTS assets (mesh/texture) generated

Input:
    layers/kt-app/classified/{team}/structure.json - Card organization
    output/{team}/cards/{card_type}/*.jpg - Card images
    output/{team}/cardbox/*.obj/*.jpg - 3D assets from step 6
    output/{team}/tokens/ - Token files
    output/{team}/data/{team}-team-data.json - Operative stats (optional)
    config/team-config.yaml - Team metadata
    
Output:
    output/{team}/tts_objects/{Team Name}.json - TTS card box as bare Custom_Model_Bag
        (clean/primary format, referenced by output/team-urls.json)
    output/{team}/tts_objects/{Team Name} Box.json - Slim save-file wrapper
        (legacy entry point for in-the-wild boxes; per-card LuaScripts stripped)
    output/{team}/tts_objects/{Team Name} Box.png - Preview image
"""

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import yaml
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
import sys

# Add templates to path
from .templates.tts_templates import (
    create_single_card, create_deck, create_bag, create_custom_dice,
    generate_guid
)
from ..utils import paths as _paths

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = _paths.ROOT  # new_implementation/ sandbox root
PIPELINE_METADATA_FILE = PROJECT_ROOT / "layers" / "metadata.json"
OUTPUT_METADATA_FILE = PROJECT_ROOT / "output" / "metadata.json"
URL_BRANCH = os.environ.get("KT_DATACARDS_URL_BRANCH", "main")
# Base path (under the repo) that hosts the generated output. The sandbox lives
# in new_implementation/output, so URLs must include that segment to resolve
# once pushed. Overridable via env for a future production promotion.
URL_OUTPUT_BASE = os.environ.get(
    "KT_DATACARDS_URL_BASE",
    "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/new_implementation/output",
)


# ===================================================================
# BARE/CLEAN BOX FORMAT HELPERS
# ===================================================================
# Pipeline emits two TTS box files per team:
#   {Team}.json     - bare/clean Custom_Model_Bag object (NEW primary format).
#                     Spawned via spawnObjectJSON; referenced by team-urls.json.
#   {Team} Box.json - slim save-file wrapper with per-card LuaScripts stripped
#                     (legacy entry point for in-the-wild boxes via
#                     output_v2/tts-card-boxes.json / tts-metadata.json).
# The updater Lua in tts-update-rules-in-box-script.lua handles both formats.

def _strip_sub_lua(node) -> int:
    """Recursively clear nested LuaScript fields on cards/decks/sub-objects.

    Leaves the top-level (box-level) LuaScript untouched — that's the caller's
    job. Used to slim the legacy wrapper so its only purpose is to cascade an
    Update click to the full clean box.
    """
    stripped = 0
    if isinstance(node, dict):
        for child in node.get("ContainedObjects") or []:
            if isinstance(child, dict):
                if child.get("LuaScript"):
                    child["LuaScript"] = ""
                    stripped += 1
                stripped += _strip_sub_lua(child)
        # Decks contain cards under "ContainedObjects" too — handled above.
    elif isinstance(node, list):
        for item in node:
            stripped += _strip_sub_lua(item)
    return stripped


def _empty_save_wrapper() -> dict:
    """Minimal TTS save-file envelope. Grid is left null/None — only valid as
    a GridState object at top level, never as a bool here."""
    return {
        "SaveName": "",
        "Date": "",
        "VersionNumber": "",
        "GameMode": "",
        "GameType": "",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "",
        "Sky": "",
        "Note": "",
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [],
    }


def _bare_from_wrapper(bag_obj: dict) -> dict:
    """Extract the Custom_Model_Bag from a wrapper dict, or return as-is if
    already bare."""
    if isinstance(bag_obj, dict) and bag_obj.get("ObjectStates"):
        return bag_obj["ObjectStates"][0]
    return bag_obj


# Volatile timestamp keys inside LuaScriptState JSON blobs. Stamping these on
# every run would otherwise cascade-bust every team's box hash (and thus its
# object-urls.json entry) even when nothing meaningful changed.
_VOLATILE_LUA_STATE_KEYS = ("lastUpdate", "lastCardUpdate", "lastTokenUpdate")


def _strip_volatile_lua_states(obj) -> None:
    """In-place: walk the object tree and blank volatile timestamp values in
    every parsed LuaScriptState dict. Leaves non-dict / unparseable
    LuaScriptState strings untouched.
    """
    if isinstance(obj, dict):
        lss = obj.get("LuaScriptState")
        if isinstance(lss, str) and lss:
            try:
                state = json.loads(lss)
            except (json.JSONDecodeError, TypeError):
                state = None
            if isinstance(state, dict):
                touched = False
                for k in _VOLATILE_LUA_STATE_KEYS:
                    if k in state:
                        state[k] = ""
                        touched = True
                if touched:
                    obj["LuaScriptState"] = json.dumps(state)
        for v in obj.values():
            _strip_volatile_lua_states(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_volatile_lua_states(v)


def _normalize_for_compare(data, top_level_volatile_keys=()) -> str | None:
    """Return a deterministic JSON repr with volatile fields blanked, or None
    if `data` can't be parsed. Accepts a dict/list, raw bytes, or a JSON
    string.
    """
    import copy

    if isinstance(data, (bytes, bytearray)):
        try:
            data = json.loads(data.decode("utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    elif isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    snap = copy.deepcopy(data)
    _strip_volatile_lua_states(snap)
    if isinstance(snap, dict):
        for k in top_level_volatile_keys:
            if k in snap:
                snap[k] = ""
    return json.dumps(snap, sort_keys=True)


def _write_json_stable(path: Path, data, *, indent: int = 2,
                       ensure_ascii: bool = True,
                       top_level_volatile_keys: tuple = (),
                       prior_bytes: bytes | None = None,
                       prior_mtime: float | None = None) -> bool:
    """Write `data` as JSON to `path`. If the prior file's normalized content
    matches the new content, restore the prior bytes AND mtime so the file is
    byte-identical to the previous generation. Returns True when the prior
    file was restored, False otherwise.

    If `prior_bytes` / `prior_mtime` are provided, they're used as the baseline
    (useful when caller already wrote a placeholder over the real prior file).
    Otherwise the function reads the file at `path` before writing.

    Downstream cache busters (sha256 of file bytes, mtime-based ?v= params)
    therefore stay quiet when nothing meaningful changed.
    """
    if prior_bytes is None and path.exists():
        try:
            prior_bytes = path.read_bytes()
            prior_mtime = path.stat().st_mtime
        except OSError:
            prior_bytes = None

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)

    if prior_bytes is None:
        return False  # no prior — nothing to preserve

    prior_norm = _normalize_for_compare(prior_bytes, top_level_volatile_keys)
    new_norm = _normalize_for_compare(data, top_level_volatile_keys)
    if prior_norm is None or new_norm is None or prior_norm != new_norm:
        return False  # meaningful change — keep new bytes

    # Content unchanged — restore prior bytes and mtime.
    path.write_bytes(prior_bytes)
    if prior_mtime is not None:
        import os
        os.utime(path, (prior_mtime, prior_mtime))
    return True


def write_team_box_files(bag_obj: dict, team_output_dir: Path, team_display_name: str,
                         intermediate_lua: str = "",
                         clean_prior_bytes: bytes | None = None,
                         clean_prior_mtime: float | None = None) -> tuple[Path, Path]:
    """Write both the clean bare object and the slim legacy wrapper.

    If `clean_prior_bytes`/`clean_prior_mtime` are provided, they're used as
    the baseline for byte-stable preservation of the clean file (since the
    caller may have already written a placeholder over the real prior file).

    Returns: (clean_path, wrapper_path)
    """
    import copy

    inner = _bare_from_wrapper(bag_obj)

    clean_path = team_output_dir / f"{team_display_name}.json"
    wrapper_path = team_output_dir / f"{team_display_name} Box.json"

    # Clean: full bare object exactly as TTS expects via spawnObjectJSON.
    _write_json_stable(
        clean_path, inner, indent=2, ensure_ascii=True,
        prior_bytes=clean_prior_bytes, prior_mtime=clean_prior_mtime,
    )

    # Wrapper: ruthlessly slimmed copy. Sole purpose is to be a one-click hop
    # to the clean file. We strip:
    #   - all per-card LuaScripts (legacy cards still updatable via clean box)
    #   - full updater Lua at box level -> replaced with minimal updater
    #   - LuaScriptState (memoryList, cached timestamps) -> empty, no Reset use
    # Description nudges the user toward the Update button.
    slim_inner = copy.deepcopy(inner)
    _strip_sub_lua(slim_inner)
    if intermediate_lua:
        slim_inner["LuaScript"] = intermediate_lua
    slim_inner["LuaScriptState"] = ""
    slim_inner["Description"] = (
        "OUTDATED VERSION. Click the red UPDATE button (or right-click -> "
        "Update to latest) to replace this with the full current team box. "
        "This intermediate is a one-time bridge and should not be reused."
    )

    wrapper = _empty_save_wrapper()
    wrapper["SaveName"] = inner.get("Nickname") or team_display_name
    wrapper["ObjectStates"] = [slim_inner]
    _write_json_stable(wrapper_path, wrapper, indent=2, ensure_ascii=True)

    return clean_path, wrapper_path


# ===================================================================
# METADATA MANAGEMENT
# ===================================================================

class MetadataManager:
    """Manages pipeline metadata with hash-based change detection"""

    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"pipeline_version": "2.0", "last_full_run": None, "teams": {}}

    def save_metadata(self):
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update_file(self, team: str, step: str, file_key: str, file_path: Path):
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {"outputs": {}}
        if "outputs" not in self.metadata["teams"][team]["steps"][step]:
            self.metadata["teams"][team]["steps"][step]["outputs"] = {}
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata["teams"][team]["steps"][step]["outputs"][file_key] = {
            "path": str(file_path), "hash": file_hash, "modified": timestamp
        }

    def mark_step_complete(self, team: str, step: str):
        if team not in self.metadata["teams"]:
            self.metadata["teams"][team] = {"steps": {}}
        if "steps" not in self.metadata["teams"][team]:
            self.metadata["teams"][team]["steps"] = {}
        if step not in self.metadata["teams"][team]["steps"]:
            self.metadata["teams"][team]["steps"][step] = {}
        self.metadata["teams"][team]["steps"][step]["completed"] = datetime.now(timezone.utc).isoformat()


class OutputMetadataManager:
    """Manages shared output metadata across pipelines"""

    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict:
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"version": "1.0", "last_updated": None, "files": {}}

    def save_metadata(self):
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def update_file(self, rel_path: str, file_path: Path, pipeline: str, step: str):
        file_hash = self.compute_hash(file_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata.setdefault("files", {})[rel_path] = {
            "hash": file_hash, "modified": timestamp, "pipeline": pipeline, "step": step
        }


def generate_urls_json_v3(repo_branch: str = URL_BRANCH):
    """Generate flat list format for internal use (backwards compatibility)"""
    output_dir = PROJECT_ROOT / 'output'
    base_url = URL_OUTPUT_BASE.format(branch=repo_branch)
    
    all_entries = []
    
    # Scan all team directories
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team = team_dir.name
        cards_dir = team_dir / 'cards'
        cardbox_dir = team_dir / 'cardbox'
        
        if not cards_dir.exists():
            continue
        
        # Add cardbox assets (mesh and texture)
        if cardbox_dir.exists():
            for asset_file in cardbox_dir.glob('*'):
                if asset_file.suffix in ['.obj', '.jpg']:
                    asset_mtime = int(asset_file.stat().st_mtime)
                    asset_url = f"{base_url}/{team}/cardbox/{asset_file.name}?v={asset_mtime}"
                    all_entries.append({
                        'team': team,
                        'type': 'tts',
                        'name': asset_file.stem,
                        'url': asset_url
                    })
        
        # Scan card types
        for card_type_dir in sorted(cards_dir.iterdir()):
            if not card_type_dir.is_dir():
                continue
            
            card_type = card_type_dir.name
            
            # Convert v3 naming (underscores) to v2 naming (dashes)
            type_mappings = {
                'operatives_selection': 'operative-selection',
                'faction_rules': 'faction-rules',
                'firefight_ploys': 'firefight-ploys',
                'strategy_ploys': 'strategy-ploys',
                'token_guide': 'token-guide'
            }
            card_type_v2 = type_mappings.get(card_type, card_type.replace('_', '-'))
            
            # Regular card type
            for card_file in sorted(card_type_dir.glob('*.jpg')):
                # Convert filename format from "{team}-{card}-front.jpg" to "{team}-{card}_front"
                name = card_file.stem
                if name.endswith('-front') or name.endswith('-back'):
                    name = name.rsplit('-', 1)
                    name = f"{name[0]}_{name[1]}"

                card_mtime = int(card_file.stat().st_mtime)
                card_url = f"{base_url}/{team}/cards/{card_type}/{card_file.name}?v={card_mtime}"
                all_entries.append({
                    'team': team,
                    'type': card_type_v2,
                    'name': name,
                    'url': card_url
                })
    
    return all_entries


def _sha256_of_files(paths) -> str:
    """Combined SHA-256 hex of one or more files (order-sensitive)."""
    import hashlib
    h = hashlib.sha256()
    for p in paths:
        try:
            with open(p, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    h.update(chunk)
        except Exception:
            h.update(b"<missing>")
        h.update(b"\x00")  # boundary
    return h.hexdigest()


def _load_prev_team_urls(output_dir: Path, team: str) -> dict:
    """Load the previous object-urls.json for a team (empty dict if absent)."""
    team_file = output_dir / team / f"{team}-object-urls.json"
    if not team_file.exists():
        return {}
    try:
        with open(team_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _git_unchanged_from_head(file_path: Path) -> bool | None:
    """Return True if file content matches git HEAD, False if it differs,
    or None if git is unavailable / file is not tracked. Used only as a
    bootstrap heuristic when prior entries lack a `hash` field."""
    try:
        import subprocess
        rel = file_path.relative_to(PROJECT_ROOT).as_posix()
        r = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "diff", "--quiet", "HEAD", "--", rel],
            capture_output=True
        )
        if r.returncode == 0:
            return True
        if r.returncode == 1:
            return False
        return None
    except Exception:
        return None


def generate_object_urls_json(repo_branch: str = URL_BRANCH):
    """
    Generate team detail URL metadata for TTS update checks.
    
    Structure: Keyed by team for efficient lookup in TTS Lua scripts.
    Each team has:
    - box: The TTS save JSON file with modified timestamp
    - objects: Array of all assets (cards, cardbox, tokens, lua script) with URLs and timestamps

    Cache-busting policy: each entry stores a content hash. When the underlying
    file(s) haven't changed (hash matches the previously-saved entry), the
    previous `url` and `modified` are reused verbatim so downstream consumers
    (TTS update checks) only see churn for objects that actually changed.
    Legacy entries without `hash` use a git HEAD comparison as a bootstrap
    heuristic — preserve on clean, regenerate on real diff.
    """
    output_dir = PROJECT_ROOT / 'output'
    config_dir = PROJECT_ROOT / 'config'
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{repo_branch}/output"
    
    teams_data = {}

    def _reuse_or_new_single(prev_entry, file_path, url, entry):
        """Single-file entry: reuse prev url/modified if hash matches."""
        new_hash = _sha256_of_files([file_path])
        prev_hash = (prev_entry or {}).get("hash")
        if prev_entry and prev_hash == new_hash:
            entry["url"] = prev_entry.get("url", url)
            entry["modified"] = prev_entry.get("modified")
        elif prev_entry and prev_hash is None:
            git_clean = _git_unchanged_from_head(file_path)
            if git_clean is False:
                mtime = file_path.stat().st_mtime
                entry["url"] = f"{url}?v={int(mtime)}"
                entry["modified"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            else:
                entry["url"] = prev_entry.get("url", url)
                entry["modified"] = prev_entry.get("modified")
        else:
            mtime = file_path.stat().st_mtime
            entry["url"] = f"{url}?v={int(mtime)}"
            entry["modified"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        entry["hash"] = new_hash
        return entry

    def _reuse_or_new_pair(prev_entry, file_a, file_b, url_a, url_b, key_a, key_b, entry):
        """Two-file entry (mesh/texture, front/back): reuse if combined hash matches."""
        new_hash = _sha256_of_files([file_a, file_b])
        prev_hash = (prev_entry or {}).get("hash")

        def _emit_new():
            mtime_a = file_a.stat().st_mtime
            mtime_b = file_b.stat().st_mtime
            entry[key_a] = f"{url_a}?v={int(mtime_a)}"
            entry[key_b] = f"{url_b}?v={int(mtime_b)}"
            entry["modified"] = datetime.fromtimestamp(
                max(mtime_a, mtime_b), tz=timezone.utc
            ).isoformat()

        def _emit_prev():
            entry[key_a] = prev_entry.get(key_a, url_a)
            entry[key_b] = prev_entry.get(key_b, url_b)
            entry["modified"] = prev_entry.get("modified")

        if prev_entry and prev_hash == new_hash:
            _emit_prev()
        elif prev_entry and prev_hash is None:
            clean_a = _git_unchanged_from_head(file_a)
            clean_b = _git_unchanged_from_head(file_b)
            if clean_a is False or clean_b is False:
                _emit_new()
            else:
                _emit_prev()
        else:
            _emit_new()
        entry["hash"] = new_hash
        return entry

    # Scan all team directories
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team = team_dir.name
        team_display_name = team.replace('-', ' ').title()

        # Load previous entries for change-detection
        prev_data = _load_prev_team_urls(output_dir, team)
        prev_box = prev_data.get("box") or None
        prev_objs_by_key = {
            (o.get("type"), o.get("name")): o
            for o in (prev_data.get("objects") or [])
        }

        # Initialize team entry
        team_entry = {
            "team": team,
            "box": None,
            "objects": []
        }
        
        # Add TTS box JSON file. Point at the bare {Team}.json (clean format)
        # which is what spawnObjectJSON in the updater Lua expects.
        tts_objects_dir = team_dir / 'tts_objects'
        box_file = tts_objects_dir / f"{team_display_name}.json"
        if box_file.exists():
            box_base = f"{base_url}/{team}/tts_objects/{box_file.name.replace(' ', '%20')}"
            team_entry["box"] = _reuse_or_new_single(prev_box, box_file, box_base, {})
        
        # Add Lua script
        lua_script_path = config_dir / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
        if lua_script_path.exists():
            lua_base = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{repo_branch}/config/defaults/tts-script/tts-update-rules-in-box-script.lua"
            entry = {"type": "lua-script", "name": "update-script"}
            prev = prev_objs_by_key.get(("lua-script", "update-script"))
            team_entry["objects"].append(_reuse_or_new_single(prev, lua_script_path, lua_base, entry))
        
        # Add cardbox assets (mesh and texture)
        cardbox_dir = team_dir / 'cardbox'
        if cardbox_dir.exists():
            for asset_file in sorted(cardbox_dir.glob('*')):
                if asset_file.suffix == '.obj':
                    obj_type = 'cardbox-mesh'
                elif asset_file.suffix == '.jpg':
                    obj_type = 'cardbox-texture'
                else:
                    continue
                
                asset_base = f"{base_url}/{team}/cardbox/{asset_file.name}"
                entry = {"type": obj_type, "name": asset_file.stem}
                prev = prev_objs_by_key.get((obj_type, asset_file.stem))
                team_entry["objects"].append(_reuse_or_new_single(prev, asset_file, asset_base, entry))
        
        # Add tokens
        tokens_dir = team_dir / 'tokens'
        if tokens_dir.exists():
            for token_obj in sorted(tokens_dir.glob('*.obj')):
                token_png = token_obj.with_suffix('.png')
                if not token_png.exists():
                    continue
                
                obj_url = f"{base_url}/{team}/tokens/{token_obj.name}"
                png_url = f"{base_url}/{team}/tokens/{token_png.name}"
                entry = {"type": "token", "name": token_obj.stem}
                prev = prev_objs_by_key.get(("token", token_obj.stem))
                team_entry["objects"].append(_reuse_or_new_pair(
                    prev, token_obj, token_png, obj_url, png_url,
                    "mesh_url", "texture_url", entry
                ))
            
            # Add token bag mesh and icon
            tokenbag_dir = tokens_dir / 'tokenbag'
            if tokenbag_dir.exists():
                bag_mesh = tokenbag_dir / f'{team}-token-bag.obj'
                bag_icon = tokenbag_dir / f'{team}-token-bag-icon.png'
                
                if bag_mesh.exists() and bag_icon.exists():
                    mesh_url = f"{base_url}/{team}/tokens/tokenbag/{bag_mesh.name}"
                    icon_url = f"{base_url}/{team}/tokens/tokenbag/{bag_icon.name}"
                    entry = {"type": "token-bag", "name": f"{team}-token-bag"}
                    prev = prev_objs_by_key.get(("token-bag", f"{team}-token-bag"))
                    team_entry["objects"].append(_reuse_or_new_pair(
                        prev, bag_mesh, bag_icon, mesh_url, icon_url,
                        "mesh_url", "icon_url", entry
                    ))
        
        # Add card images
        cards_dir = team_dir / 'cards'
        if cards_dir.exists():
            for card_type_dir in sorted(cards_dir.iterdir()):
                if not card_type_dir.is_dir():
                    continue
                
                card_type = card_type_dir.name
                
                # Group front/back pairs
                card_pairs = {}
                for card_file in card_type_dir.glob('*.jpg'):
                    name = card_file.stem
                    if name.endswith('-front'):
                        base_name = name[:-6]
                        if base_name not in card_pairs:
                            card_pairs[base_name] = {}
                        card_pairs[base_name]['front'] = card_file
                    elif name.endswith('-back'):
                        base_name = name[:-5]
                        if base_name not in card_pairs:
                            card_pairs[base_name] = {}
                        card_pairs[base_name]['back'] = card_file
                
                # Add paired cards
                for base_name, files in sorted(card_pairs.items()):
                    front_file = files.get('front')
                    back_file = files.get('back')
                    
                    if not front_file:
                        continue
                    
                    front_url = f"{base_url}/{team}/cards/{card_type}/{front_file.name}"
                    back_url = f"{base_url}/{team}/cards/{card_type}/{back_file.name}" if back_file else front_url
                    effective_back = back_file if back_file else front_file
                    entry = {"type": card_type, "name": base_name}
                    prev = prev_objs_by_key.get((card_type, base_name))
                    team_entry["objects"].append(_reuse_or_new_pair(
                        prev, front_file, effective_back, front_url, back_url,
                        "face_url", "back_url", entry
                    ))
        
        # Add team to result if it has a box
        if team_entry["box"]:
            teams_data[team] = team_entry
    
    return teams_data


def _to_stamp(ts: str) -> int:
    """Convert ISO-like timestamp strings to comparable numeric stamp."""
    return int(''.join(ch for ch in str(ts or '') if ch.isdigit()) or 0)


def generate_object_urls_summary(teams_data: dict, repo_branch: str = URL_BRANCH) -> dict:
    """Build lightweight global summary for fast box-level update checks."""
    summary = {}
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{repo_branch}/output"

    for team, team_entry in sorted(teams_data.items()):
        max_modified = ""
        max_stamp = 0

        box = team_entry.get("box") or {}
        box_modified = box.get("modified") or ""
        box_stamp = _to_stamp(box_modified)
        if box_stamp > max_stamp:
            max_stamp = box_stamp
            max_modified = box_modified

        for obj in team_entry.get("objects") or []:
            obj_modified = (obj or {}).get("modified") or ""
            obj_stamp = _to_stamp(obj_modified)
            if obj_stamp > max_stamp:
                max_stamp = obj_stamp
                max_modified = obj_modified

        team_url = f"{base_url}/{team}/{team}-object-urls.json"
        summary[team] = {
            "team": team,
            "modified": max_modified,
            "team_url": f"{team_url}?v={max_stamp}",
            "box": team_entry.get("box"),
        }

    return summary


def save_object_urls_team_files(teams_data: dict, output_dir: Path) -> list[Path]:
    """Write per-team object URL metadata files for faster in-game update checks."""
    written_files: list[Path] = []

    for team, team_entry in sorted(teams_data.items()):
        team_meta_dir = output_dir / team
        team_meta_dir.mkdir(parents=True, exist_ok=True)
        team_file = team_meta_dir / f"{team}-object-urls.json"
        with open(team_file, 'w', encoding='utf-8') as f:
            json.dump(team_entry, f, indent=2, ensure_ascii=False)
        written_files.append(team_file)

        # Cleanup previous team-local filename from earlier implementation.
        old_team_file = team_meta_dir / "object-urls.json"
        if old_team_file.exists():
            try:
                old_team_file.unlink()
            except Exception:
                logger.warning(f"Could not remove legacy team metadata file: {old_team_file}")

    # Cleanup legacy central folder from earlier implementation.
    legacy_team_meta_dir = output_dir / 'object-urls'
    if legacy_team_meta_dir.exists():
        for existing_file in legacy_team_meta_dir.glob('*.json'):
            try:
                existing_file.unlink()
            except Exception:
                logger.warning(f"Could not remove legacy team metadata file: {existing_file}")
        try:
            legacy_team_meta_dir.rmdir()
        except OSError:
            pass

    return written_files


def load_lua_script(config_dir: Path) -> str:
    """Load the Lua script from config defaults folder"""
    script_path = config_dir / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
    try:
        with open(script_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            content = content.replace('\n', '\r\n')
            return content
    except Exception as e:
        logger.warning(f"Could not load Lua script: {e}")
        return ""


def load_intermediate_updater_script(config_dir: Path) -> str:
    """Slim updater embedded in the legacy save-file wrapper {Team} Box.json.

    Sole job: fetch team-urls.json, download the bare {Team}.json, respawn.
    Keeps the wrapper lean so spawning it (the slow save-file code path in
    TTS) stays as cheap as possible.
    """
    script_path = config_dir / "defaults" / "tts-script" / "intermediate-updater.lua"
    try:
        with open(script_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            content = content.replace('\n', '\r\n')
            return content
    except Exception as e:
        logger.warning(f"Could not load intermediate updater script: {e}")
        return ""


def load_single_object_updater_script(config_dir: Path) -> str:
    """Load reusable per-object updater Lua script from defaults folder.

    Embedded on every card/deck/token bag so users can right-click any single
    object and update it in place. Lives in both the standalone per-object
    JSON files and the in-box copies inside the clean {Team}.json. Whole-box
    spawn stays fast because the clean bare object skips TTS's slow save-file
    parser. The intermediate {Team} Box.json wrapper still strips this script
    (one-off bridge, lean as possible).
    """
    script_path = config_dir / "defaults" / "tts-script" / "single-object-updater.lua"
    try:
        with open(script_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            content = content.replace('\n', '\r\n')
            return content
    except Exception as e:
        logger.warning(f"Could not load single-object updater script: {e}")
        return ""


def load_display_table_manager_script(config_dir: Path) -> str:
    """Load display table manager Lua script from defaults folder."""
    script_path = config_dir / "defaults" / "tts-script" / "display-table-manager-script.lua"
    try:
        with open(script_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            content = content.replace('\n', '\r\n')
            return content
    except Exception as e:
        logger.warning(f"Could not load display manager script: {e}")
        return ""


def load_box_description(config_dir: Path) -> str:
    """Load default box description text from config defaults folder."""
    description_path = config_dir / "defaults" / "box" / "card-box-description.txt"
    try:
        with open(description_path, 'r', encoding='utf-8-sig') as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"Could not load box description: {e}")
        return (
            "This box has two kinds of controls: table buttons and right-click (context menu) buttons.\n\n"
            "Table buttons:\n"
            "- Place: Puts cards/tokens in their play positions.\n"
            "- KT table: Places items using the Kill Team table layout.\n"
            "- Recall: Pulls tracked items back into the box.\n\n"
            "Right-click (context menu) buttons:\n"
            "- Update: Refreshes card stats/rules from this box onto matching cards already on the table.\n"
            "- Reset: Resets this box and respawns its tracked contents.\n"
            "- Clear Layout: Clears any saved custom layout and reverts Place behavior to defaults."
        )


def _build_token_memory_list(token_objects: list) -> dict:
    """Build default grid layout for token bag memory list (ml).
    
    Lays tokens out in rows of 4, spaced 1.5 units apart, starting at
    x=-2.25, z=-3.0 — matching the old pipeline's default layout.
    """
    cols = 4
    x_start = -2.25
    x_step = 1.5
    z_start = -3.0
    z_step = -1.5
    y = 0.0213

    ml = {}
    for i, token_obj in enumerate(token_objects):
        guid = token_obj.get("GUID")
        if not guid:
            continue
        col = i % cols
        row = i // cols
        ml[guid] = {
            "lock": False,
            "pos": {"x": x_start + col * x_step, "y": y, "z": z_start + row * z_step},
            "rot": {"x": 0.0, "y": 180.0, "z": 0.0},
        }
    return ml


def _build_token_tags_map(team_name: str, config_dir: Path) -> dict:
    """Build a mapping of normalized token name -> KTUI tags from team-config.

    The KTUI tags determine whether an object behaves as a token or a marker in
    the Kill Team UI mod. Driven by the config `type` field:
      - marker  -> ["KTUIToken", "KTUIMarker"]
      - token   -> ["KTUIToken", "KTUITokenSimple"]
      - custom  -> ["KTUIToken"] + the tags listed in config
    """
    tags_by_name = {}
    team_config_path = config_dir / "team-config.yaml"
    try:
        with open(team_config_path, 'r', encoding='utf-8') as f:
            team_config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not load team-config for token tags ({team_name}): {e}")
        return tags_by_name

    tokens_cfg = team_config.get('teams', {}).get(team_name, {}).get('tokens', []) or []
    for token_cfg in tokens_cfg:
        name = token_cfg.get('name', '')
        if not name:
            continue
        normalized = ' '.join(name.lower().split())
        token_type = (token_cfg.get('type') or '').strip().lower()

        if token_type == 'marker':
            tags = ["KTUIToken", "KTUIMarker"]
        elif token_type == 'both':
            # A marker that can also be picked up / attached to a model.
            tags = ["KTUIToken", "KTUIMarker", "KTUITokenSimple"]
        elif token_type == 'custom':
            cfg_tags = token_cfg.get('tags', []) or []
            tags = ["KTUIToken"] + [t for t in cfg_tags if t != "KTUIToken"]
        else:
            # token (default for empty/unknown types)
            tags = ["KTUIToken", "KTUITokenSimple"]

        tags_by_name[normalized] = tags

    return tags_by_name


def load_token_bag(team_name: str, faction: str, sample_url: str, config_dir: Path, output_dir: Path, single_object_updater_script: str = "") -> tuple:
    """
    Generate token bag from output/{team}/tokens/ files.
    
    Returns:
        Tuple of (token bag object dict, token timestamp) or (None, None) if no tokens exist
    """
    tokens_dir = output_dir / team_name / 'tokens'
    
    if not tokens_dir.exists():
        return None, None
    
    # Find all token .obj files (excluding tokenbag folder)
    token_files = []
    for obj_file in tokens_dir.glob('*.obj'):
        png_file = obj_file.with_suffix('.png')
        if png_file.exists():
            token_files.append((obj_file.stem, obj_file, png_file))
    
    if not token_files:
        return None, None
    
    # Check for token bag mesh and icon
    tokenbag_dir = tokens_dir / 'tokenbag'
    bag_mesh_file = tokenbag_dir / f'{team_name}-token-bag.obj'
    bag_icon_file = tokenbag_dir / f'{team_name}-token-bag-icon.png'
    
    if not bag_mesh_file.exists() or not bag_icon_file.exists():
        logger.warning(f"Token bag mesh or icon not found for {team_name}")
        return None, None
    
    # Extract github base URL from sample card URL
    github_base = ""
    if sample_url and '/output/' in sample_url:
        github_base = sample_url.split('/output/')[0]
    elif sample_url and '/output_v2/' in sample_url:
        github_base = sample_url.split('/output_v2/')[0]
    
    if not github_base:
        logger.warning(f"Could not extract github base URL, using placeholder")
        github_base = "https://github.com/user/repo/raw/main"
    
    # Build a lookup of token name -> KTUI tags driven by the config `type`.
    # marker -> KTUIMarker, token -> KTUITokenSimple, custom -> config tags.
    token_tags_by_name = _build_token_tags_map(team_name, config_dir)
    
    # Generate token objects (Custom_Model_Infinite_Bag, each containing a Custom_Token)
    token_objects = []
    for token_name, obj_path, png_path in sorted(token_files):
        display_name = token_name.replace(f'{team_name}-', '').replace('-', ' ').title()
        normalized_name = ' '.join(token_name.replace(f'{team_name}-', '').replace('-', ' ').lower().split())
        token_tags = token_tags_by_name.get(normalized_name, ["KTUIToken", "KTUITokenSimple"])
        
        mesh_mtime = int(obj_path.stat().st_mtime)
        png_mtime = int(png_path.stat().st_mtime)
        mesh_url = f"{github_base}/output/{team_name}/tokens/{obj_path.name}?v={mesh_mtime}"
        diffuse_url = f"{github_base}/output/{team_name}/tokens/{png_path.name}?v={png_mtime}"
        
        inner_token = {
            "GUID": generate_guid(f"{team_name}:customtoken:{token_name}"),
            "Name": "Custom_Token",
            "Transform": {
                "posX": 0.0,
                "posY": 1.63,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": 0.21,
                "scaleY": 1.0,
                "scaleZ": 0.21
            },
            "Nickname": display_name,
            "Description": display_name,
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": list(token_tags),
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
            "CustomImage": {
                "ImageURL": diffuse_url,
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": 6.0,
                    "StandUp": False,
                    "Stackable": False
                }
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
        
        display_token = {
            "GUID": generate_guid(f"{team_name}:displaytoken:{token_name}"),
            "Name": "Custom_Token",
            "Transform": {
                "posX": 0.0, "posY": 0.0, "posZ": 0.0,
                "rotX": 0.0, "rotY": 0.0, "rotZ": 0.0,
                "scaleX": 0.21, "scaleY": 1.0, "scaleZ": 0.21
            },
            "Nickname": display_name,
            "Description": display_name,
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": list(token_tags),
            "Locked": True,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
            "CustomImage": {
                "ImageURL": diffuse_url,
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": 6.0,
                    "StandUp": False,
                    "Stackable": False
                }
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }

        token_obj = {
            "GUID": generate_guid(f"{team_name}:token:{token_name}"),
            "Name": "Custom_Model_Infinite_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 1.03,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.8351557,
                "scaleY": 0.1,
                "scaleZ": 1.7720486
            },
            "Nickname": display_name,
            "Description": f"Infinite {display_name} tokens",
            "GMNotes": "",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": [f"_{team_name}_tokens"],
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "Hands": False,
            "CustomMesh": {
                "MeshURL": mesh_url,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 7,
                "CastShadows": True
            },
            "Bag": {"Order": 0},
            "ContainedObjects": [inner_token],
            "ChildObjects": [display_token],
            "LuaScript": single_object_updater_script,
            "LuaScriptState": "",
            "XmlUI": ""
        }
        token_objects.append(token_obj)
    
    # Save individual token JSONs
    for idx, token_obj in enumerate(token_objects, start=1):
        save_individual_token_json(token_obj, team_name, idx, output_dir)
    
    # Build token bag mesh and icon URLs
    bag_mesh_mtime = int(bag_mesh_file.stat().st_mtime)
    bag_icon_mtime = int(bag_icon_file.stat().st_mtime)
    bag_mesh_url = f"{github_base}/output/{team_name}/tokens/tokenbag/{bag_mesh_file.name}?v={bag_mesh_mtime}"
    bag_icon_url = f"{github_base}/output/{team_name}/tokens/tokenbag/{bag_icon_file.name}?v={bag_icon_mtime}"
    
    # Create token bag
    token_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Load token bag Lua script
    lua_script_path = config_dir / 'defaults' / 'tts-token' / 'token-bag-script.lua'
    lua_script = ""
    if lua_script_path.exists():
        with open(lua_script_path, 'r', encoding='utf-8') as f:
            lua_script = f.read()
    
    canonical_name = team_name.replace('-', ' ').title()

    token_bag = {
        "GUID": generate_guid(f"{team_name}:tokenbag"),
        "Name": "Custom_Model_Bag",
        "Transform": {
            "posX": 0.0,
            "posY": 1.01,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 270.0,
            "rotZ": 0.0,
            "scaleX": 1.47,
            "scaleY": 0.1,
            "scaleZ": 1.47
        },
        "Nickname": f"{canonical_name} tokens",
        "Description": "If errors pop up, just wait for few sec and try again",
        "GMNotes": f"_{team_name}_tokens",
        "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
        "Tags": [f"_{team_name}", "KTCardsTokenBag"],
        "Locked": False,
        "Grid": True,
        "Snap": True,
        "Autoraise": True,
        "Sticky": True,
        "Tooltip": True,
        "Hands": False,
        "Number": 0,
        "CustomMesh": {
            "MeshURL": bag_mesh_url,
            "DiffuseURL": "",
            "NormalURL": "",
            "ColliderURL": bag_mesh_url,
            "Convex": True,
            "MaterialIndex": 0,
            "TypeIndex": 6,
            "CastShadows": True
        },
        "Bag": {"Order": 0},
        "LuaScript": lua_script,
        "LuaScriptState": json.dumps({"ml": _build_token_memory_list(token_objects), "rr": 270, "lastUpdate": token_timestamp}),
        "XmlUI": "",
        "ChildObjects": [
            {
                "GUID": generate_guid(f"{team_name}:tokenbag:icon"),
                "Name": "Custom_Tile",
                "Transform": {
                    "posX": 0.0, "posY": -0.5, "posZ": 0.0,
                    "rotX": 0.0, "rotY": 270.0, "rotZ": 0.0,
                    "scaleX": 0.5, "scaleY": 10.0, "scaleZ": 0.5
                },
                "Nickname": "",
                "Description": "",
                "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
                "Locked": False,
                "Grid": True,
                "Snap": True,
                "Autoraise": True,
                "Sticky": True,
                "Tooltip": True,
                "Hands": False,
                "CustomImage": {
                    "ImageURL": bag_icon_url,
                    "ImageSecondaryURL": bag_icon_url,
                    "ImageScalar": 1.0,
                    "WidthScale": 0.0,
                    "CustomTile": {
                        "Type": 0,
                        "Thickness": 0.1,
                        "Stackable": False,
                        "Stretch": True
                    }
                }
            }
        ],
        "ContainedObjects": token_objects
    }
    
    logger.info(f"Generated token bag for {team_name} with {len(token_objects)} tokens from output")
    return token_bag, token_timestamp


def load_dice_objects(team_name: str, sample_url: Optional[str], output_dir: Path, repo_branch: str = URL_BRANCH) -> list:
    """
    Create TTS Custom_Dice objects for a team (team, light, dark variants).
    Saves individual JSON files to output/{team}/tts_objects/dice/ and returns
    the list of objects to be included in the main box.
    """
    dice_dir = output_dir / team_name / "dice"
    if not dice_dir.exists():
        return []

    github_base = ""
    if sample_url:
        if "/output/" in sample_url:
            github_base = sample_url.split("/output/")[0]
        elif "/output_v2/" in sample_url:
            github_base = sample_url.split("/output_v2/")[0]
    if not github_base:
        github_base = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{repo_branch}"

    team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
    display = team_name.replace("-", " ").title()

    variants = [
        ("team",  f"{team_name}-dice-team.jpg",  f"{display} Dice"),
        ("light", f"{team_name}-dice-light.jpg", f"{display} Light Dice"),
        ("dark",  f"{team_name}-dice-dark.jpg",  f"{display} Dark Dice"),
    ]

    dice_objects = []
    out_dir = output_dir / team_name / "tts_objects" / "dice"
    out_dir.mkdir(parents=True, exist_ok=True)

    for variant, filename, nickname in variants:
        texture_file = dice_dir / filename
        if not texture_file.exists():
            continue

        mtime = int(texture_file.stat().st_mtime)
        texture_url = f"{github_base}/output/{team_name}/dice/{filename}?v={mtime}"

        dice_obj = create_custom_dice(nickname, texture_url, team_tag, variant)
        dice_objects.append(dice_obj)

        # Save individual dice JSON
        out_name = f"{team_name}-dice.json" if variant == "team" else f"{team_name}-{variant}-dice.json"
        with open(out_dir / out_name, "w", encoding="utf-8") as f:
            json.dump({"ObjectStates": [dice_obj]}, f, indent=2)

    if dice_objects:
        logger.info(f"  Added {len(dice_objects)} dice for {team_name}")
    return dice_objects


def copy_preview_image(team_folder_name: str, team_display_name: str, config_dir: Path, output_dir: Path):
    """Copy preview/icon image for a team.

    Priority:
      1. config/teams/{team}/tts-image/{team}-icon.png   — manual override
      2. config/teams/{team}/tts-image/{team}-preview.png — manual override (alt)
      3. layers/integration/{team}/artwork/icons/{team}-icon-token.jpg — auto-source
      4. config/defaults/tts-image/default-icon.png       — generic fallback
      5. config/defaults/tts-image/default-preview.png    — generic fallback (alt)
    """
    team_icon    = config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-icon.png"
    team_preview = config_dir / "teams" / team_folder_name / "tts-image" / f"{team_folder_name}-preview.png"
    integ_icon   = _paths.artwork_team_dir(team_folder_name) / "icons" / f"{team_folder_name}-icon-token.jpg"
    default_icon    = config_dir / "defaults" / "tts-image" / "default-icon.png"
    default_preview = config_dir / "defaults" / "tts-image" / "default-preview.png"

    # Priority: team icon > team preview > integration icon > default icon > default preview
    if team_icon.exists():
        source_preview = team_icon
    elif team_preview.exists():
        source_preview = team_preview
    elif integ_icon.exists():
        source_preview = integ_icon
    elif default_icon.exists():
        source_preview = default_icon
    else:
        source_preview = default_preview
    
    if source_preview.exists():
        team_output_dir = output_dir / team_folder_name / 'tts_objects'
        team_output_dir.mkdir(parents=True, exist_ok=True)
        dest_preview = team_output_dir / f"{team_display_name} Box.png"
        shutil.copy2(source_preview, dest_preview)
    else:
        logger.warning(f"No preview/icon image found for {team_folder_name}")


def rebuild_kill_team_card_boxes_example(output_dir: Path) -> tuple[int, Optional[Path]]:
    """Refresh manager bag contents with latest generated team boxes.

    Source template is loaded from dev/examples (or existing generated output
    if present), while the generated artifact is written to
    output/_generic-tts-objects/Kill Team Card Boxes.json.
    Only `ContainedObjects` is rewritten. Manager bag Lua script, buttons,
    description, and other top-level settings remain unchanged.
    """
    manager_template_path = PROJECT_ROOT / "dev" / "examples" / "Kill Team Card Boxes.json"
    manager_output_dir = output_dir / "_generic-tts-objects"
    manager_output_dir.mkdir(parents=True, exist_ok=True)
    manager_output_path = manager_output_dir / "Kill Team Card Boxes.json"

    source_path = manager_template_path
    if not source_path.exists():
        logger.warning(f"Manager bag template file not found: {source_path}")
        return 0, None

    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            manager_data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read manager bag file: {e}")
        return 0, None

    object_states = manager_data.get("ObjectStates") or []
    if not object_states or not isinstance(object_states[0], dict):
        logger.warning("Manager bag JSON has no valid ObjectStates[0]")
        return 0, None

    manager_obj = object_states[0]
    # Build manager bag contents from scratch each run to avoid stale nested state.
    manager_obj["ContainedObjects"] = []

    # Keep manager bag script synced with defaults so UI changes are always propagated.
    manager_script = load_display_table_manager_script(PROJECT_ROOT / "config")
    if manager_script:
        manager_obj["LuaScript"] = manager_script

    team_box_objects = []
    for team_tts_dir in sorted(output_dir.glob("*/tts_objects")):
        # Prefer the bare {Team}.json (clean format). Fall back to extracting
        # ObjectStates[0] from the legacy wrapper for backwards compatibility.
        clean_candidates = sorted(
            p for p in team_tts_dir.glob("*.json")
            if not p.name.endswith(" Box.json") and "urls" not in p.name.lower()
        )
        if clean_candidates:
            box_file = clean_candidates[0]
            try:
                with open(box_file, 'r', encoding='utf-8') as f:
                    team_obj = json.load(f)
                if not isinstance(team_obj, dict) or team_obj.get("Name") != "Custom_Model_Bag":
                    continue
            except Exception as e:
                logger.warning(f"Could not read clean team box for manager bag ({box_file}): {e}")
                continue
        else:
            team_box_files = sorted(team_tts_dir.glob("* Box.json"))
            if not team_box_files:
                continue
            box_file = team_box_files[0]
            try:
                with open(box_file, 'r', encoding='utf-8') as f:
                    team_data = json.load(f)
                team_obj = (team_data.get("ObjectStates") or [None])[0]
                if not isinstance(team_obj, dict):
                    continue
            except Exception as e:
                logger.warning(f"Could not read team box for manager bag ({box_file}): {e}")
                continue

        team_box_objects.append(team_obj)

    team_box_objects.sort(key=lambda obj: obj.get("Nickname", ""))
    manager_obj["ContainedObjects"] = team_box_objects

    try:
        with open(manager_output_path, 'w', encoding='utf-8') as f:
            json.dump(manager_obj, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Could not write manager bag file: {e}")
        return 0, None

    logger.info(f"Updated manager bag contents: {len(team_box_objects)} teams -> {manager_output_path}")

    # Also write a save-file-wrapped copy of the manager bag so users can drop
    # it into TTS via Game -> Save & Load -> Saved Objects. The bare file
    # (Kill Team Card Boxes.json) is what the manager Lua self-update flow
    # downloads at runtime via spawnObjectJSON.
    wrapped_path = manager_output_dir / "Kill Team Card Boxes (saved object).json"
    wrapped_obj = {
        "SaveName": "Kill Team Card Boxes",
        "Date": "", "VersionNumber": "", "GameMode": "", "GameType": "",
        "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5,
        "Table": "", "Sky": "", "Note": "", "Rules": "", "XmlUI": "",
        "CustomUIAssets": [], "LuaScript": "", "LuaScriptState": "",
        "ObjectStates": [manager_obj],
        "TabStates": {}, "Lighting": {}, "Hands": {}, "ComponentTags": {},
        "Turns": {}, "Grid": {}, "CameraStates": [], "DecalPallet": [],
        "VectorLines": [],
    }
    try:
        with open(wrapped_path, "w", encoding="utf-8") as f:
            json.dump(wrapped_obj, f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote manager bag (saved object): {wrapped_path}")
    except Exception as e:
        logger.warning(f"Could not write wrapped manager bag: {e}")

    # Generate the per-team Kill Team Spawner (save-file wrapper) from the
    # current team-spawner-clean-script.lua. Small object users drop into TTS
    # to pick & spawn an individual team box without loading the full manager.
    spawner_lua_path = PROJECT_ROOT / "config" / "defaults" / "tts-script" / "team-spawner-clean-script.lua"
    if spawner_lua_path.exists():
        try:
            spawner_lua = spawner_lua_path.read_text(encoding="utf-8")
            spawner_tile = {
                "Name": "Custom_Tile",
                "Transform": {
                    "posX": 0.0, "posY": 1.0, "posZ": 0.0,
                    "rotX": 0.0, "rotY": 180.0, "rotZ": 0.0,
                    "scaleX": 3.5, "scaleY": 1.0, "scaleZ": 2.5,
                },
                "Nickname": "Kill Team Spawner",
                "Description": "Click button to spawn a Kill Team card box.",
                "GMNotes": "",
                "ColorDiffuse": {"r": 0.2, "g": 0.8, "b": 0.3},
                "Locked": False, "Grid": True, "Snap": True, "IgnoreFoW": False,
                "MeasureMovement": False, "DragSelectable": True, "Autoraise": True,
                "Sticky": True, "Tooltip": True, "GridProjection": False,
                "HideWhenFaceDown": False, "Hands": False,
                "CustomImage": {
                    "ImageURL": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/_generic-tts-objects/team-spawner-image.png",
                    "ImageSecondaryURL": "",
                    "ImageScalar": 1.0,
                    "WidthScale": 0.0,
                    "CustomTile": {"Type": 0, "Thickness": 0.1, "Stackable": False, "Stretch": True},
                },
                "LuaScript": spawner_lua,
                "LuaScriptState": "", "XmlUI": "", "States": {},
                "GUID": "spawnc",
            }
            spawner_save = {
                "SaveName": "Kill Team Spawner",
                "Date": "", "VersionNumber": "", "GameMode": "", "GameType": "",
                "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5,
                "Table": "", "Sky": "", "Note": "", "Rules": "", "XmlUI": "",
                "CustomUIAssets": [], "LuaScript": "", "LuaScriptState": "",
                "ObjectStates": [spawner_tile],
                "TabStates": {}, "Lighting": {}, "Hands": {}, "ComponentTags": {},
                "Turns": {}, "Grid": {}, "CameraStates": [], "DecalPallet": [],
                "VectorLines": [],
            }
            spawner_path = manager_output_dir / "Kill Team Spawner.json"
            with open(spawner_path, "w", encoding="utf-8") as f:
                json.dump(spawner_save, f, indent=2, ensure_ascii=False)
            logger.info(f"Wrote team spawner: {spawner_path}")
        except Exception as e:
            logger.warning(f"Could not write team spawner: {e}")

    return len(team_box_objects), manager_output_path


def embed_datacard_stats(bag_obj: dict, team_name: str, output_dir: Path, config_dir: Path, single_object_updater_script: str = "") -> bool:
    """
    Embed operative stats into datacards within the TTS bag object.
    Returns True if stats were embedded, False if skipped.
    """
    # Load team data
    team_data_path = output_dir / team_name / "data" / f"{team_name}-team-data.json"
    if not team_data_path.exists():
        logger.debug(f"  No team data found for {team_name}, skipping stat embedding")
        return False
    
    logger.debug(f"  Loading team data from {team_data_path}")
    with open(team_data_path, 'r', encoding='utf-8') as f:
        team_data = json.load(f)
    
    # Load weapon rules
    weapon_rules_path = config_dir / "weapon_rules.json"
    with open(weapon_rules_path, 'r', encoding='utf-8') as f:
        weapon_rules = json.load(f)
    
    # Load team config
    team_config_path = config_dir / "team-config.yaml"
    with open(team_config_path, 'r', encoding='utf-8') as f:
        team_config = yaml.safe_load(f)
    
    # Load selection data from roster.json (output_v2)
    faction = team_config.get('teams', {}).get(team_name, {}).get('faction', '')
    roster_selection: dict = {}
    roster_exclusive_sets: dict = {}
    if faction:
        roster_path = PROJECT_ROOT / 'output_v2' / faction / team_name / 'statlines' / 'roster.json'
        if roster_path.exists():
            try:
                with open(roster_path, 'r', encoding='utf-8') as f:
                    roster_data = json.load(f)
                roster_selection = roster_data.get('selection', {})
                roster_exclusive_sets = roster_data.get('exclusive_sets', {})
                logger.debug(f"  Loaded selection for {sum(1 for v in roster_selection.values() if v)} operatives")
            except Exception as e:
                logger.warning(f"  Could not load roster.json for {team_name}: {e}")

    # Load datacard Lua script
    lua_script_path = config_dir / "defaults" / "tts-script" / "datacard-load-stats.lua"
    with open(lua_script_path, 'r', encoding='utf-8') as f:
        datacard_lua_script = f.read()
    
    # Find all datacard objects in the bag
    datacards = _find_datacards(bag_obj)
    if not datacards:
        logger.debug(f"  No datacards found in TTS object for {team_name}")
        return False
    
    logger.info(f"  Embedding stats for {len(datacards)} datacards")
    
    patched = 0
    for card in datacards:
        nickname = card.get("Nickname", "")
        
        # Match card to operative
        operative = _match_card_to_operative(nickname, team_name, team_data)
        if not operative:
            logger.debug(f"    No match for card '{nickname}'")
            continue
        
        # Look up selection groups for this operative (keyed by UPPERCASE name in roster)
        op_name_upper = operative.get('name', '').upper()
        selection_groups = roster_selection.get(op_name_upper) or []
        op_exclusive_sets = roster_exclusive_sets.get(op_name_upper) if roster_exclusive_sets else None

        # Build GMNotes
        try:
            gm_notes_data = _build_gm_notes(operative, team_data, weapon_rules,
                                             selection_groups=selection_groups,
                                             exclusive_sets=op_exclusive_sets)
            gm_notes_json = json.dumps(gm_notes_data, separators=(",", ":"), ensure_ascii=False)
            
            # Get faction rule code if applicable
            faction_rule_code = _get_faction_rule_code(team_name, team_data, operative, team_config)
            lua_script = datacard_lua_script + "\n\n" + faction_rule_code + "\n\n" + (single_object_updater_script or "")
            
            # Set GMNotes and Lua script
            card["GMNotes"] = gm_notes_json
            card["LuaScript"] = lua_script
            
            patched += 1
            logger.debug(f"    Embedded stats for '{nickname}'")
        except Exception as e:
            logger.error(f"    Error embedding stats for '{nickname}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    # Update bag timestamp
    _update_bag_timestamp(bag_obj)
    
    logger.info(f"  Embedded stats for {patched}/{len(datacards)} datacards")
    return True


def _find_datacards(tts_data: dict) -> list:
    """Find all datacard objects in TTS JSON."""
    datacards = []
    
    def recurse(obj):
        if isinstance(obj, dict):
            nickname = obj.get("Nickname", "")
            
            if ("CardID" in obj or "CustomDeck" in obj) and nickname:
                excluded_patterns = [
                    "Datacards", "Equipment", "Strategy Ploys", "Firefight Ploys",
                    "OPERATIVE SELECTION", "TOKEN GUIDE", "SKILL AT ARMS", "Faction Rules"
                ]
                
                is_excluded = any(pattern in nickname for pattern in excluded_patterns)
                if not is_excluded:
                    datacards.append(obj)
            
            for key, value in obj.items():
                if key not in ["CustomDeck", "CustomImage"]:
                    recurse(value)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item)
    
    recurse(tts_data)
    return datacards


def _match_card_to_operative(nickname: str, team: str, team_data: dict) -> Optional[dict]:
    """Match a card nickname to an operative in team_data."""
    def normalize(s):
        return s.lower().strip().replace("-", " ").replace("_", " ")
    
    nickname_norm = normalize(nickname)
    team_norm = normalize(team)
    
    # Strip -card1, -card2, etc. suffix for multi-page operatives (e.g. Necron leaders)
    nickname_base = re.sub(r'\s+card\d+$', '', nickname_norm)
    
    datacards = team_data.get('datacards', [])
    for operative in datacards:
        op_name = operative.get('name', '')
        op_name_norm = normalize(op_name)
        
        if op_name_norm == nickname_norm or op_name_norm == nickname_base:
            return operative
        
        if op_name_norm.startswith(team_norm):
            op_type = op_name_norm[len(team_norm):].strip()
            if op_type == nickname_norm or op_type == nickname_base:
                return operative
    
    return None


# ─── Weapon classification patterns (ported from script/embed_datacard_stats.py) ───
_RANGED_RULES_PAT = re.compile(r"(range\s*\d|blast|torrent|silent)", re.IGNORECASE)
_RANGED_NAME_PAT = re.compile(
    r"(pistol|rifle|carbine|blaster|bolter|cannon|gun|launcher|"
    r"flamer|melta|plasma|las(?:cutter|gun|cannon)|auto|bolt|stubber|grenade|"
    r"needle|sniper|mortar|missile|photon|radium|phosphor|igniter|"
    r"scattergun|bow|fusil|jezzail|splinter|shuriken|starcannon|"
    r"deathspitter|strangler|devourer|fleshborer|spinefist)",
    re.IGNORECASE,
)
_MELEE_NAME_PAT = re.compile(
    r"(sword|blade|claw|fist|axe|hammer|mace|glaive|talons?|"
    r"pincer|pike|spear|staff|whip|maul|scythe|gauntlet|"
    r"bayonet|knife|dagger|spike|club|choppa|stave|fangs|"
    r"halberd|trident|sabre|falchion|cleaver|maw|beak|sabres|"
    r"claws|pincers|bonesword|lash|tendril|proboscis|crusher)",
    re.IGNORECASE,
)
_UNICODE_NORMALIZE_MAP = {
    "\u2019": "'", "\u2018": "'",
    "\u201c": '"', "\u201d": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2033": '"', "\u2032": "'",
    "\u00e2": "a", "\u00f4": "o",
}


def _normalize_text(s: str) -> str:
    """Strip control characters and normalize Unicode to ASCII equivalents."""
    s = re.sub(r"[\x07\x08]", "", s)
    for uchar, replacement in _UNICODE_NORMALIZE_MAP.items():
        s = s.replace(uchar, replacement)
    return s.strip()


def _classify_weapon(weapon: dict) -> str:
    rules = weapon.get('special_rules', '')
    name = weapon.get('name', '')
    if _MELEE_NAME_PAT.search(name) and not _RANGED_RULES_PAT.search(rules):
        return 'melee'
    if _RANGED_RULES_PAT.search(rules):
        return 'ranged'
    if _RANGED_NAME_PAT.search(name):
        return 'ranged'
    return 'melee'


def _match_weapon_rules(special_rules: str, all_rules: dict) -> dict:
    if not special_rules:
        return {}
    matched = {}
    for rule_name, desc in all_rules.items():
        base = rule_name.replace(' x', '').replace(' x+', '')
        if re.search(re.escape(base), special_rules, re.IGNORECASE):
            matched[rule_name] = desc
    return matched


def _build_selection_for_gmnotes(selection_groups: list, weapons: list, exclusive_sets: dict = None) -> Optional[dict]:
    """
    Convert string-based selection groups to index-based format for GMNotes.
    Mirrors script/embed_datacard_stats.py _build_selection_for_gmnotes().
    """
    if not selection_groups or not weapons:
        return None
    weapon_names_lower = [(w.get('plain_name') or w.get('name', '')).lower() for w in weapons]
    all_matched = set()
    result_groups = []
    for group in selection_groups:
        group_options = []
        for option_label in group:
            fragments = [f.strip().lower() for f in re.split(r'\s*;\s*|\s+and\s+', option_label)]
            matched = set()
            for frag in fragments:
                sub_frags = [sf.strip() for sf in frag.split(' or ')]
                for sf in sub_frags:
                    for i, wname in enumerate(weapon_names_lower):
                        if wname.startswith(sf):
                            matched.add(i)
            all_matched.update(matched)
            group_options.append({'label': option_label, 'weapons': sorted(matched)})
        result_groups.append(group_options)
    fixed = [i for i in range(len(weapons)) if i not in all_matched]
    result: dict = {'groups': result_groups, 'fixed': fixed}
    if exclusive_sets:
        result['exclusive_sets'] = exclusive_sets
    return result


def _build_gm_notes(operative: dict, team_data: dict, weapon_rules: dict,
                    selection_groups: list = None, exclusive_sets: dict = None) -> dict:
    """Build GMNotes JSON structure with operative stats."""
    def parse_move(s: str) -> int:
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 6

    def parse_save(s: str) -> int:
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 5

    stats = {
        'APL': operative.get('apl', 2),
        'Move': parse_move(operative.get('movement', '6')),
        'Save': parse_save(operative.get('save', '5+')),
        'Wounds': operative.get('wounds', 1)
    }

    # base_size is extracted by content_analysis (e.g. 28 for a 28mm base).
    base_size = operative.get('base_size')
    if base_size is not None:
        stats['Base'] = base_size

    keywords = ['Operative'] + [_normalize_text(k) for k in operative.get('keywords', [])]

    weapons = []
    weapon_rules_found = {}
    for weapon in operative.get('weapons', []):
        weapon_name = weapon.get('name', '')
        special_rules = weapon.get('special_rules', '')
        prefix = '[F4641D]M[-]' if _classify_weapon(weapon) == 'melee' else '[1E87FF]R[-]'
        full_name = f'{prefix} {weapon_name}'
        weapons.append({
            'name': full_name,
            'plain_name': weapon_name,
            'stats': {
                'ATK': weapon.get('attacks', ''),
                'HIT': weapon.get('hit', ''),
                'DMG': weapon.get('damage', ''),
                'WR': special_rules
            }
        })
        weapon_rules_found.update(_match_weapon_rules(special_rules, weapon_rules))

    abilities = []
    for ability in operative.get('passive_abilities', []):
        name = _normalize_text(ability.get('name', ''))
        text = _normalize_text(ability.get('description', ''))
        if name:
            abilities.append({'name': name, 'text': text})

    actions = []
    for action in operative.get('unique_actions', []):
        name = _normalize_text(action.get('name', ''))
        text = _normalize_text(action.get('description', ''))
        if name:
            actions.append({'name': name, 'text': text})

    description_lines = [
        f"[D36B3E][[84E680]APL[-] [ffffff]{stats['APL']}[-]] [[84E680]MOVE[-] [ffffff]{stats['Move']}\"[-]]",
        f"[[84E680]SAVE[-] [ffffff]{stats['Save']}+[-]] [[84E680]WOUNDS[-] [ffffff]{stats['Wounds']}[-]][-]"
    ]

    if keywords:
        description_lines.append('[C5C5C5]' + ', '.join(keywords) + '[-]')

    description_lines.append('[31B32B]Weapons[-]')
    for w in weapons:
        description_lines.append(w['name'])
        w_stats = w['stats']
        description_lines.append(
            f"[84E680]ATK[-] {w_stats['ATK']} [84E680]HIT[-] {w_stats['HIT']} [84E680]DMG[-] {w_stats['DMG']}"
        )
        if w_stats['WR']:
            description_lines.append(f"[84E680]WR[-]: {w_stats['WR']}")
        description_lines.append('')

    if abilities:
        description_lines.append('---')
        description_lines.append('[31B32B]Abilities[-]')
        for ab in abilities:
            description_lines.append(f"- [EF8450]{ab['name']}[-]")

    if actions:
        description_lines.append('---')
        description_lines.append('[31B32B]Unique Actions[-]')
        for act in actions:
            description_lines.append(f"- [EF8450]{act['name']}[-]")

    description = '\n'.join(description_lines)

    result = {
        'name': operative.get('name', ''),
        'stats': stats,
        'keywords': keywords,
        'weapons': weapons,
        'abilities': abilities,
        'actions': actions,
        'weapon_rules': weapon_rules_found,
        'description': description
    }

    if selection_groups:
        indexed = _build_selection_for_gmnotes(selection_groups, weapons, exclusive_sets)
        if indexed:
            result['selection'] = indexed

    return result


def _build_select1_lua(rule_name: str, lua_options: str) -> str:
    """Generate Lua for single-choice faction rule (select: 1)."""
    return f'''

-- ===== FACTION RULE: {rule_name.upper()} =====

FACTION_RULE_NAME = "{rule_name}"
FACTION_RULE_OPTIONS = {lua_options}

local frPendingModel = nil
local frPendingPlayerColor = nil
local frSelection = 1

function buildFactionRulePanel()
    local rows = ""

    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frSelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_%d" isOn="%s" '
            .. 'onValueChanged="onFrToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    local optionCount = #FACTION_RULE_OPTIONS
    local panelHeight = 70 + optionCount * 22

    return string.format([[
<Panel id="frPanel" active="true"
       width="240" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="22">]] .. FACTION_RULE_NAME .. [[</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="frApply" onClick="onFrApply"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="frCancel" onClick="onFrCancel"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], panelHeight, rows)
end

function onFrToggle(player, value, id)
    local idx = tonumber(id:match("fr_(%d+)"))
    if not idx then return end
    if value == "True" then
        frSelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_" .. i, "isOn", "false")
            end
        end
    else
        if frSelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrApply(player, value, id)
    self.UI.setXml("")

    if not frPendingModel then
        broadcastToColor("No model pending.", frPendingPlayerColor or player.color, Color.Red)
        return
    end

    local model = frPendingModel
    local pc = frPendingPlayerColor or player.color

    local msRaw = model.script_state or "{{}}"
    local ok, ms = pcall(function() return JSON.decode(msRaw) end)
    if not ok or not ms then ms = {{}} end
    ms.info = ms.info or {{}}
    ms.info.abilities = ms.info.abilities or {{}}

    local kept = {{}}
    for _, ab in ipairs(ms.info.abilities) do
        local isFactionRule = false
        for _, opt in ipairs(FACTION_RULE_OPTIONS) do
            if ab.name == opt.name or ab.name == opt.name .. " (Primary)" or ab.name == opt.name .. " (Secondary)" then
                isFactionRule = true
                break
            end
        end
        if not isFactionRule then
            table.insert(kept, ab)
        end
    end

    local selected = FACTION_RULE_OPTIONS[frSelection]
    table.insert(kept, {{name = selected.name .. " (Primary)", text = selected.text}})

    ms.info.abilities = kept

    local descLines = {{}}
    local oldDesc = model.getDescription() or ""
    local inFactionSection = false
    for line in oldDesc:gmatch("([^\\n]*)\\n?") do
        if line:find("^%[31B32B%]" .. FACTION_RULE_NAME) then
            inFactionSection = true
        elseif inFactionSection and (line:find("^%[31B32B%]") or line:find("^%-%-%-")) then
            inFactionSection = false
            table.insert(descLines, line)
        elseif not inFactionSection then
            table.insert(descLines, line)
        end
    end

    table.insert(descLines, "---")
    table.insert(descLines, "[31B32B]" .. FACTION_RULE_NAME .. "[-]")
    table.insert(descLines, "- [EF8450]" .. selected.name .. " (Primary)[-]")

    model.setDescription(table.concat(descLines, "\\n"))
    model.script_state = JSON.encode(ms)
    Wait.frames(function() model.reload() end, 5)

    broadcastToColor(string.format("%s applied: %s (Primary)",
        FACTION_RULE_NAME, selected.name), pc, Color.Green)

    frPendingModel = nil
    frPendingPlayerColor = nil
end

function onFrCancel(player, value, id)
    self.UI.setXml("")
    broadcastToColor(FACTION_RULE_NAME .. " selection cancelled.", frPendingPlayerColor or player.color, Color.White)
    frPendingModel = nil
    frPendingPlayerColor = nil
end

function applyFactionRule(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    frPendingModel = model
    frPendingPlayerColor = playerColor
    frSelection = 1
    self.UI.setXml(buildFactionRulePanel())
    broadcastToColor("Select " .. FACTION_RULE_NAME .. ", then click Apply.", playerColor, Color.Yellow)
end

local frBaseOnLoad = onLoad
function onLoad()
    if frBaseOnLoad then frBaseOnLoad() end
    self.addContextMenuItem("{rule_name}", applyFactionRule)
end

-- ===== END FACTION RULE =====
'''


def _build_select2_lua(rule_name: str, lua_options: str) -> str:
    """Generate Lua for dual-choice faction rule (select: 2, primary + secondary)."""
    return f'''

-- ===== FACTION RULE: {rule_name.upper()} =====

FACTION_RULE_NAME = "{rule_name}"
FACTION_RULE_OPTIONS = {lua_options}

local frPendingModel = nil
local frPendingPlayerColor = nil
local frPrimarySelection = 1
local frSecondarySelection = 2

function buildFactionRulePanel()
    local rows = ""

    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Primary:</Text>\\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frPrimarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_p_%d" isOn="%s" '
            .. 'onValueChanged="onFrPrimaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    rows = rows .. '<Image color="rgba(255,255,255,0.3)" preferredHeight="1" />\\n'

    rows = rows .. '<Text fontSize="11" fontStyle="Bold" color="#FF6600" '
        .. 'preferredHeight="20" alignment="MiddleLeft">Secondary:</Text>\\n'
    for i, opt in ipairs(FACTION_RULE_OPTIONS) do
        local isOn = (i == frSecondarySelection) and "true" or "false"
        local label = opt.name:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
        rows = rows .. string.format(
            '<Toggle id="fr_s_%d" isOn="%s" '
            .. 'onValueChanged="onFrSecondaryToggle" '
            .. 'fontSize="10" textColor="#FFFFFF" colors="#444444|#666666|#333333|#222222" '
            .. 'toggleWidth="16" toggleHeight="16">%s</Toggle>\\n',
            i, isOn, label
        )
    end

    local optionCount = #FACTION_RULE_OPTIONS
    local panelHeight = 80 + optionCount * 22 * 2 + 40

    return string.format([[
<Panel id="frPanel" active="true"
       width="240" height="%d"
       color="rgba(0,0,0,0.92)"
       padding="6 6 6 6"
       position="0 0 -50"
       rotation="0 0 180"
       allowDragging="true">
  <VerticalLayout spacing="2" childForceExpandWidth="true" childForceExpandHeight="false">
    <Text fontSize="12" fontStyle="Bold" color="#FF9900"
          alignment="MiddleCenter" preferredHeight="22">]] .. FACTION_RULE_NAME .. [[</Text>
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    %s
    <Image color="rgba(255,255,255,0.15)" preferredHeight="1" />
    <HorizontalLayout spacing="4" preferredHeight="24">
      <Button id="frApply" onClick="onFrApply"
              fontSize="10" fontStyle="Bold"
              colors="#2E7D32|#388E3C|#1B5E20|#555555"
              textColor="#FFFFFF">Apply</Button>
      <Button id="frCancel" onClick="onFrCancel"
              fontSize="10"
              colors="#C62828|#D32F2F|#B71C1C|#555555"
              textColor="#FFFFFF">Cancel</Button>
    </HorizontalLayout>
  </VerticalLayout>
</Panel>
]], panelHeight, rows)
end

function onFrPrimaryToggle(player, value, id)
    local idx = tonumber(id:match("fr_p_(%d+)"))
    if not idx then return end
    if value == "True" then
        frPrimarySelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_p_" .. i, "isOn", "false")
            end
        end
    else
        if frPrimarySelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrSecondaryToggle(player, value, id)
    local idx = tonumber(id:match("fr_s_(%d+)"))
    if not idx then return end
    if value == "True" then
        frSecondarySelection = idx
        for i = 1, #FACTION_RULE_OPTIONS do
            if i ~= idx then
                self.UI.setAttribute("fr_s_" .. i, "isOn", "false")
            end
        end
    else
        if frSecondarySelection == idx then
            self.UI.setAttribute(id, "isOn", "true")
        end
    end
end

function onFrApply(player, value, id)
    self.UI.setXml("")

    if not frPendingModel then
        broadcastToColor("No model pending.", frPendingPlayerColor or player.color, Color.Red)
        return
    end

    if frPrimarySelection == frSecondarySelection then
        broadcastToColor("Primary and secondary must be different.", frPendingPlayerColor or player.color, Color.Orange)
        self.UI.setXml(buildFactionRulePanel())
        return
    end

    local model = frPendingModel
    local pc = frPendingPlayerColor or player.color

    local msRaw = model.script_state or "{{}}"
    local ok, ms = pcall(function() return JSON.decode(msRaw) end)
    if not ok or not ms then ms = {{}} end
    ms.info = ms.info or {{}}
    ms.info.abilities = ms.info.abilities or {{}}

    local kept = {{}}
    for _, ab in ipairs(ms.info.abilities) do
        local isFactionRule = false
        for _, opt in ipairs(FACTION_RULE_OPTIONS) do
            if ab.name == opt.name or ab.name == opt.name .. " (Primary)" or ab.name == opt.name .. " (Secondary)" then
                isFactionRule = true
                break
            end
        end
        if not isFactionRule then
            table.insert(kept, ab)
        end
    end

    local primary = FACTION_RULE_OPTIONS[frPrimarySelection]
    local secondary = FACTION_RULE_OPTIONS[frSecondarySelection]

    table.insert(kept, {{name = primary.name .. " (Primary)", text = primary.text}})
    table.insert(kept, {{name = secondary.name .. " (Secondary)", text = secondary.text}})

    ms.info.abilities = kept

    local descLines = {{}}
    local oldDesc = model.getDescription() or ""
    local inFactionSection = false
    for line in oldDesc:gmatch("([^\\n]*)\\n?") do
        if line:find("^%[31B32B%]" .. FACTION_RULE_NAME) then
            inFactionSection = true
        elseif inFactionSection and (line:find("^%[31B32B%]") or line:find("^%-%-%-")) then
            inFactionSection = false
            table.insert(descLines, line)
        elseif not inFactionSection then
            table.insert(descLines, line)
        end
    end

    table.insert(descLines, "---")
    table.insert(descLines, "[31B32B]" .. FACTION_RULE_NAME .. "[-]")
    table.insert(descLines, "- [EF8450]" .. primary.name .. " (Primary)[-]")
    table.insert(descLines, "- [EF8450]" .. secondary.name .. " (Secondary)[-]")

    model.setDescription(table.concat(descLines, "\\n"))
    model.script_state = JSON.encode(ms)
    Wait.frames(function() model.reload() end, 5)

    broadcastToColor(string.format("%s applied: %s (Primary) + %s (Secondary)",
        FACTION_RULE_NAME, primary.name, secondary.name), pc, Color.Green)

    frPendingModel = nil
    frPendingPlayerColor = nil
end

function onFrCancel(player, value, id)
    self.UI.setXml("")
    broadcastToColor(FACTION_RULE_NAME .. " selection cancelled.", frPendingPlayerColor or player.color, Color.White)
    frPendingModel = nil
    frPendingPlayerColor = nil
end

function applyFactionRule(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    frPendingModel = model
    frPendingPlayerColor = playerColor
    frPrimarySelection = 1
    frSecondarySelection = 2
    self.UI.setXml(buildFactionRulePanel())
    broadcastToColor("Select primary and secondary " .. FACTION_RULE_NAME .. ", then click Apply.", playerColor, Color.Yellow)
end

local frBaseOnLoad = onLoad
function onLoad()
    if frBaseOnLoad then frBaseOnLoad() end
    self.addContextMenuItem("{rule_name}", applyFactionRule)
end

-- ===== END FACTION RULE =====
'''


_OPERATIVE_COUNTER_LUA_TEMPLATE = r'''

-- ===== OPERATIVE COUNTER: <<NAME_UPPER>> =====

OC_NAME = "<<NAME>>"
OC_INIT_VALUE = <<INIT_VALUE>>
OC_MIN_VAL = <<MIN_VAL>>
OC_MAX_VAL = <<MAX_VAL>>

OC_HELPER_FUNCS = [==[<<HELPER_BLOCK>>]==]

OC_ASSET_LINES = [==[<<ASSET_BLOCK>>
]==]

OC_PANEL_XML = "\n    <Panel color=\"#80808000\" outline=\"#FFFF00\" outlineSize=\"3 3\" width=\"45\" height=\"45\" offsetXY=\"0 -10\">"
    .. "\n      <Image id=\"ktcnid-status-operative-counter\" image=\""
    .. "]]..getOperativeCounterImage()..[["
    .. "\" preserveAspect=\"true\" rectAlignment=\"MiddleCenter\" onClick=\"change_operative_counter\" />"
    .. "\n    </Panel>"

function addOperativeCounterToModel(playerColor)
    local model = findModelOnCard()
    if model == nil then
        broadcastToColor("Place a KTUIMini model on this card first.", playerColor, Color.Orange)
        return
    end

    local modelLua = model.getLuaScript() or ""
    if modelLua == "" then
        broadcastToColor("Model has no Lua script (not a KTUI model?).", playerColor, Color.Red)
        return
    end

    if modelLua:find("ktcnid%-status%-operative%-counter") then
        broadcastToColor("Model already has " .. OC_NAME .. " counter.", playerColor, Color.White)
        return
    end

    local xmlPattern = "(<HorizontalLayout spacing=\"3\" width=\"@totalAtt\")"
    if modelLua:find(xmlPattern) then
        modelLua = modelLua:gsub(xmlPattern, OC_PANEL_XML .. "\n    %1")
    else
        broadcastToColor("Could not find attachment layout in model.", playerColor, Color.Red)
        return
    end

    local bundlePattern = "({name=\"Wound_red\"[^\n]+)"
    if modelLua:find(bundlePattern) then
        modelLua = modelLua:gsub(bundlePattern, "%1" .. OC_ASSET_LINES)
    end

    modelLua = modelLua .. OC_HELPER_FUNCS

    local modelState = model.script_state or "{}"
    local ok, mState = pcall(function() return JSON.decode(modelState) end)
    if not ok or not mState then mState = {} end
    if not mState.operative_counter then
        mState.operative_counter = {
            name = OC_NAME,
            current = OC_INIT_VALUE,
            min = OC_MIN_VAL,
            max = OC_MAX_VAL
        }
    end
    model.script_state = JSON.encode(mState)

    model.setLuaScript(modelLua)
    Wait.frames(function() model.reload() end, 10)

    broadcastToColor("Added " .. OC_NAME .. " counter to model!", playerColor, Color.Green)
end

local ocBaseOnLoad = onLoad
function onLoad()
    if ocBaseOnLoad then ocBaseOnLoad() end
    self.addContextMenuItem("Add " .. OC_NAME, addOperativeCounterToModel)
end

-- ===== END OPERATIVE COUNTER =====
'''


def _operative_matches_counter(operative: dict, applies) -> bool:
    if applies in (None, "all", True):
        return True
    if isinstance(applies, str):
        applies = [applies]
    if not isinstance(applies, list):
        return False
    op_kw = {kw.upper() for kw in operative.get('keywords', [])}
    return any(kw.upper() in op_kw for kw in applies)


def _build_operative_counter_lua(team: str, counter_cfg: dict, url_branch: str) -> str:
    """Generate Lua that adds a left/right-click cycling image counter to a model placed on the card."""
    name = str(counter_cfg.get('name', 'Counter'))
    min_val = int(counter_cfg.get('min', 0))
    max_val = int(counter_cfg.get('max', 1))
    raw_states = counter_cfg.get('states') or []
    states = sorted(raw_states, key=lambda s: int(s.get('value', 0)))
    if not states:
        return ""

    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{url_branch}/output/{team}/tokens"

    def asset_name(v: int) -> str:
        return f"oc_asset_{v}"

    def lua_str(s: str) -> str:
        return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

    labels_lua = "{" + ", ".join(
        f'[{int(s["value"])}]={lua_str(s.get("label", ""))}'
        for s in states
    ) + "}"

    assets_table_lua = "{" + ", ".join(
        f'[{int(s["value"])}]="{asset_name(int(s["value"]))}"'
        for s in states
    ) + "}"

    default_value = int(states[0]["value"])
    default_asset = asset_name(default_value)

    helper_block = f"""

-- {name} Counter (auto-injected)
function getOperativeCounterImage()
  if not state or not state.operative_counter then return "{default_asset}" end
  local v = state.operative_counter.current or {default_value}
  local assets = {assets_table_lua}
  return assets[v] or "{default_asset}"
end

function change_operative_counter(player, value, id)
  if not state.operative_counter then return end
  local current = state.operative_counter.current or {default_value}
  local maxv = state.operative_counter.max or {max_val}
  local minv = state.operative_counter.min or {min_val}
  if value == "-1" then
    if current > minv then current = current - 1 end
  elseif value == "-2" then
    if current < maxv then current = current + 1 end
  end
  state.operative_counter.current = current
  if refreshUI then refreshUI() end
  local labels = {labels_lua}
  broadcastToColor({lua_str(name + ': ')} .. (labels[current] or "?"), player.color, Color.Yellow)
end
"""

    asset_lines = []
    for s in states:
        token_file = s.get("token", "")
        url = f"{base_url}/{token_file}"
        asset_lines.append(f'    {{name="{asset_name(int(s["value"]))}", url=[=[{url}]=]}},')
    asset_block = "\n" + "\n".join(asset_lines)

    return (
        _OPERATIVE_COUNTER_LUA_TEMPLATE
        .replace("<<NAME_UPPER>>", name.upper())
        .replace("<<NAME>>", name)
        .replace("<<INIT_VALUE>>", str(default_value))
        .replace("<<MIN_VAL>>", str(min_val))
        .replace("<<MAX_VAL>>", str(max_val))
        .replace("<<HELPER_BLOCK>>", helper_block)
        .replace("<<ASSET_BLOCK>>", asset_block)
    )


def _get_faction_rule_code(team: str, team_data: dict, operative: dict, team_config: dict) -> str:
    """Generate faction rule Lua code if applicable, using inline Lua builders."""
    team_info = team_config.get('teams', {}).get(team, {})

    # Operative counter takes precedence over standard faction_rule popup UI
    counter_cfg = team_info.get('operative_counter')
    if counter_cfg and _operative_matches_counter(operative, counter_cfg.get('operatives', 'all')):
        counter_lua = _build_operative_counter_lua(team, counter_cfg, URL_BRANCH)
        if counter_lua:
            return counter_lua

    rule_cfg = team_info.get('faction_rule')
    if not rule_cfg:
        return ""

    faction_rules = team_data.get('faction_rules', [])
    if not faction_rules:
        return ""

    # Check applies_to keyword filter
    applies_to = rule_cfg.get('applies_to')
    if applies_to:
        op_keywords = [kw.upper() for kw in operative.get('keywords', [])]
        if not any(kw.upper() in op_keywords for kw in applies_to):
            return ""

    # Optional explicit options override from team-config.
    options_override = rule_cfg.get('options')
    if options_override:
        rule_name = rule_cfg.get('name', 'Faction Rule')
        options = options_override

        # Build lookup of extracted option text by normalized name, so config
        # options inherit text from the PDF extraction (step 3) without
        # requiring rule text to be hand-maintained in YAML.
        extracted_text_by_name: dict[str, str] = {}
        for r in faction_rules:
            for o in (r.get('options') or []):
                key = (o.get('name') or '').strip().lower()
                txt = (o.get('text') or '').strip()
                if key and txt and key not in extracted_text_by_name:
                    extracted_text_by_name[key] = txt

        lua_options = "{\n"
        for opt in options:
            opt_name = opt.get('name', '')
            text = opt.get('text') or extracted_text_by_name.get(opt_name.strip().lower(), '')
            name_esc = opt_name.replace('"', '\\"')
            text_esc = text.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')
            lua_options += f'    {{name = "{name_esc}", text = "{text_esc}"}},\n'
        lua_options += "}"

        select_count = rule_cfg.get('select', 2)
        operative_select_count = rule_cfg.get('operative_select_count')
        if operative_select_count:
            op_keywords = [kw.upper() for kw in operative.get('keywords', [])]
            for kw in op_keywords:
                if kw.upper() in operative_select_count:
                    select_count = operative_select_count[kw.upper()]
                    break

        if select_count == 1:
            return _build_select1_lua(rule_name, lua_options)
        return _build_select2_lua(rule_name, lua_options)

    # Find the rule entry with options
    rule_entry = next((r for r in faction_rules if r.get('options')), None)
    if not rule_entry:
        return ""

    # Use canonical rule name from team-config (proper casing), fall back to extracted name
    rule_name = rule_cfg.get('name', rule_entry['name'])
    options = rule_entry['options']

    # Build Lua table literal for options
    lua_options = "{\n"
    for opt in options:
        name_esc = opt.get('name', '').replace('"', '\\"')
        text_esc = opt.get('text', '').replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', '\\n')
        lua_options += f'    {{name = "{name_esc}", text = "{text_esc}"}},\n'
    lua_options += "}"

    # Determine select count (support per-operative overrides)
    select_count = rule_cfg.get('select', 2)
    operative_select_count = rule_cfg.get('operative_select_count')
    if operative_select_count:
        op_keywords = [kw.upper() for kw in operative.get('keywords', [])]
        for kw in op_keywords:
            if kw.upper() in operative_select_count:
                select_count = operative_select_count[kw.upper()]
                break

    if select_count == 1:
        return _build_select1_lua(rule_name, lua_options)
    else:
        return _build_select2_lua(rule_name, lua_options)


def _update_bag_timestamp(tts_data: dict) -> None:
    """Update lastCardUpdate in the top-level bag's LuaScriptState."""
    obj = tts_data.get("ObjectStates", [{}])[0]
    lss = obj.get("LuaScriptState", "")
    try:
        state = json.loads(lss) if lss else {}
    except (json.JSONDecodeError, TypeError):
        state = {}
    
    # Use UTC to stay consistent with box.modified (file mtime in UTC) in
    # team-urls.json, so the in-game up-to-date comparison isn't skewed by the
    # generating machine's local timezone.
    state["lastCardUpdate"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    obj["LuaScriptState"] = json.dumps(state)


def save_individual_card_json(card_obj: dict, team_name: str, card_type: str, card_index: int, output_dir: Path) -> tuple:
    """
    Save individual card JSON to tts_objects/cards/{card_type}/.
    
    Args:
        card_obj: Single card TTS object
        team_name: Team slug
        card_type: Card type (datacards, equipment, etc.)
        card_index: Card index for filename (fallback)
        output_dir: output directory
    
    Returns:
        (file_path, modification_timestamp)
    """
    import os
    
    # Create card type subdirectory
    card_type_dir = output_dir / team_name / 'tts_objects' / 'cards' / card_type
    card_type_dir.mkdir(parents=True, exist_ok=True)
    
    # Use card nickname for filename, fallback to index
    card_nickname = card_obj.get('Nickname', f'card-{card_index:03d}')
    # Sanitize filename (lowercase, replace spaces with hyphens)
    safe_name = card_nickname.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.json"
    file_path = card_type_dir / filename
    
    # Save JSON
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(card_obj, f, indent=2)
    
    # Get modification time
    file_mtime = os.path.getmtime(file_path)
    timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
    
    return file_path, timestamp


def save_individual_token_json(token_obj: dict, team_name: str, token_index: int, output_dir: Path) -> tuple:
    """
    Save individual token JSON to tts_objects/tokens/.
    
    Args:
        token_obj: Single token TTS object
        team_name: Team slug
        token_index: Token index for filename (fallback)
        output_dir: output directory
    
    Returns:
        (file_path, modification_timestamp)
    """
    import os
    
    # Create tokens subdirectory
    tokens_dir = output_dir / team_name / 'tts_objects' / 'tokens'
    tokens_dir.mkdir(parents=True, exist_ok=True)
    
    # Use token nickname for filename, fallback to index
    token_nickname = token_obj.get('Nickname', f'token-{token_index:03d}')
    # Sanitize filename (lowercase, replace spaces with hyphens)
    safe_name = token_nickname.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')
    filename = f"{safe_name}.json"
    file_path = tokens_dir / filename
    
    # Save JSON
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(token_obj, f, indent=2)
    
    # Get modification time
    file_mtime = os.path.getmtime(file_path)
    timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')
    
    return file_path, timestamp


def generate_team_tts_object(team_name: str, cards: list, lua_script: str, box_description: str, single_object_updater_script: str, texture_url: str,
                            mesh_url: str, config_dir: Path, output_dir: Path, repo_branch: str = URL_BRANCH,
                            intermediate_lua: str = ""):
    """Generate TTS object for a single team"""
    # Extract faction from first card's URL
    faction = None
    if cards:
        first_url = cards[0].get('url', '')
        if '/output/' in first_url:
            parts = first_url.split('/output/')[1].split('/')
            if len(parts) > 0:
                faction = parts[0]
    
    # Group cards by type
    cards_by_type = defaultdict(list)
    for card in cards:
        cards_by_type[card['type']].append(card)
    
    # Extract markertoken cards from faction-rules
    if 'faction-rules' in cards_by_type:
        markertoken_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' in c['name'].lower()]
        faction_rules_cards = [c for c in cards_by_type['faction-rules'] if 'markertoken' not in c['name'].lower()]
        
        if markertoken_cards:
            cards_by_type['markertokens'] = markertoken_cards
        cards_by_type['faction-rules'] = faction_rules_cards
    
    # Build contained objects
    contained_objects = []
    deck_id_counter = 1000
    type_order = ['operative-selection', 'faction-rules', 'token-guide', 'markertokens', 'datacards', 'equipment', 'firefight-ploys', 'strategy-ploys']
    
    # Add token bag if tokens exist for this team
    sample_url = cards[0]['url'] if cards else None
    token_bag, token_timestamp = load_token_bag(team_name, faction, sample_url, config_dir, output_dir, single_object_updater_script)
    if token_bag:
        contained_objects.append(token_bag)
        logger.info(f"Added token bag for {team_name}")

    for dice_obj in load_dice_objects(team_name, sample_url, output_dir, repo_branch):
        contained_objects.append(dice_obj)

    for card_type in type_order:
        if card_type not in cards_by_type:
            continue
        
        type_cards = cards_by_type[card_type]
        
        # Group cards by base name (without _front/_back suffix)
        card_groups = defaultdict(lambda: {'front': None, 'back': None})
        
        for card in type_cards:
            name = card['name']
            url = card['url']
            
            if name.endswith('_front'):
                base_name = name[:-6]
                card_groups[base_name]['front'] = url
            elif name.endswith('_back'):
                base_name = name[:-5]
                card_groups[base_name]['back'] = url
        
        # Prepare cards data
        type_cards_data = []
        for card_name, urls in sorted(card_groups.items()):
            front_url = urls['front']
            back_url = urls['back'] or front_url
            
            if not front_url:
                continue
            
            type_cards_data.append({
                'name': card_name,
                'front': front_url,
                'back': back_url
            })
        
        # Create deck or single card
        team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
        
        if len(type_cards_data) == 1:
            card_data = type_cards_data[0]
            
            # Transform card name to match production format
            card_name = card_data['name']
            if card_type == 'operative-selection':
                card_name = f"{team_name}-operatives"
            elif card_type == 'token-guide':
                card_name = f"{team_name}-markertoken-guide"
            
            card_obj = create_single_card(
                card_name,
                card_data['front'],
                card_data['back'],
                team_tag,
                str(deck_id_counter),
                card_type,
                single_object_updater_script,
            )
            
            # Save individual card JSON
            save_individual_card_json(card_obj, team_name, card_type, 1, output_dir)
            
            contained_objects.append(card_obj)
            deck_id_counter += 1
        elif len(type_cards_data) > 1:
            type_nickname = card_type.replace('-', ' ').title()
            deck_obj = create_deck(type_nickname, team_tag, type_cards_data, deck_id_counter, card_type, single_object_updater_script)
            
            # Save individual card JSONs from deck
            for idx, card_obj in enumerate(deck_obj['ContainedObjects'], start=1):
                save_individual_card_json(card_obj, team_name, card_type, idx, output_dir)
            
            contained_objects.append(deck_obj)
            deck_id_counter += len(type_cards_data)
    
    # Create the bag
    team_display_name = team_name.replace('-', ' ').title()
    team_tag = f"_{team_name.replace('-', '_').title().replace('_', ' ')}"
    
    # Get output file path
    team_output_dir = output_dir / team_name / 'tts_objects'
    team_output_dir.mkdir(parents=True, exist_ok=True)
    # Two outputs: bare {Team}.json (clean, primary) and slim {Team} Box.json
    # (legacy wrapper for in-the-wild boxes). See write_team_box_files docstring.
    clean_file = team_output_dir / f"{team_display_name}.json"
    output_file = team_output_dir / f"{team_display_name} Box.json"
    
    # Create bag with placeholder timestamp
    import os
    placeholder_timestamp = "2000-01-01T00:00:00"
    placeholder_token_timestamp = ""
    
    bag_obj = create_bag(
        team_display_name,
        team_tag,
        contained_objects,
        lua_script,
        texture_url,
        mesh_url,
        faction,
        placeholder_timestamp,
        placeholder_token_timestamp,
        box_description,
        repo_branch,
    )
    
    # Initial write to establish file mtime (used as the canonical timestamp
    # baked into LuaScriptState below). Only writes the clean file — wrapper
    # is regenerated on the final pass. Capture the prior generation's bytes
    # first so write_team_box_files can byte-stably preserve unchanged content.
    clean_prior_bytes: bytes | None = None
    clean_prior_mtime: float | None = None
    if clean_file.exists():
        try:
            clean_prior_bytes = clean_file.read_bytes()
            clean_prior_mtime = clean_file.stat().st_mtime
        except OSError:
            clean_prior_bytes = None
    with open(clean_file, 'w', encoding='utf-8') as f:
        json.dump(_bare_from_wrapper(bag_obj), f, indent=2)

    # Get actual file timestamp
    file_mtime = os.path.getmtime(clean_file)
    actual_timestamp = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%dT%H:%M:%S')

    # Mirror MeshURL → ColliderURL (URLs already have correct per-file ?v= timestamps)
    def mirror_collider_urls(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'MeshURL' and isinstance(value, str) and value:
                    obj['ColliderURL'] = value
                else:
                    mirror_collider_urls(value)
        elif isinstance(obj, list):
            for item in obj:
                mirror_collider_urls(item)

    mirror_collider_urls(bag_obj)

    # Recreate bag with actual timestamp
    bag_obj = create_bag(
        team_display_name,
        team_tag,
        contained_objects,
        lua_script,
        texture_url,
        mesh_url,
        faction,
        actual_timestamp,
        token_timestamp or "",
        box_description,
        repo_branch,
    )

    # Apply collider mirroring again
    mirror_collider_urls(bag_obj)
    
    # Embed datacard stats (optional - skips if no team data)
    embed_datacard_stats(bag_obj, team_name, output_dir, config_dir, single_object_updater_script)
    
    # Write final versions: clean (full bare) + slim wrapper.
    write_team_box_files(
        bag_obj, team_output_dir, team_display_name, intermediate_lua,
        clean_prior_bytes=clean_prior_bytes, clean_prior_mtime=clean_prior_mtime,
    )
    
    # Copy preview image
    copy_preview_image(team_name, team_display_name, config_dir, output_dir)


def generate_all_tts_objects(urls_data: list, config_dir: Path, output_dir: Path, team_filter: list = None, repo_branch: str = URL_BRANCH) -> int:
    """Generate TTS objects for all teams"""
    # Load Lua script
    lua_script = load_lua_script(config_dir)
    intermediate_lua = load_intermediate_updater_script(config_dir)
    single_object_updater_script = load_single_object_updater_script(config_dir)
    box_description = load_box_description(config_dir)
    
    # Group cards by team and separate box assets
    teams = defaultdict(list)
    team_textures = {}
    team_meshes = {}
    
    for card in urls_data:
        team_key = card['team']
        if card['type'] == 'tts':
            if 'card-box-texture' in card['name']:
                team_textures[team_key] = card['url']
            elif 'card-box' in card['name'] and '.obj' in card['url']:
                team_meshes[team_key] = card['url']
        else:
            teams[team_key].append(card)
    
    # Generate TTS object for each team
    count = 0
    skipped = 0
    
    for team_name, cards in teams.items():
        # Skip if team filter is active and this team is not in the filter
        if team_filter and team_name not in team_filter:
            logger.debug(f"Skipping {team_name} (not in team filter)")
            skipped += 1
            continue
            
        logger.info(f"Generating TTS object for {team_name}")
        texture_url = team_textures.get(team_name)
        mesh_url = team_meshes.get(team_name)
        
        generate_team_tts_object(team_name, cards, lua_script, box_description, single_object_updater_script, texture_url, mesh_url, config_dir, output_dir, repo_branch, intermediate_lua)
        count += 1
    
    if skipped > 0:
        logger.info(f"Skipped {skipped} team(s) (no changes or filtered out)")
    
    return count


def main():
    parser = argparse.ArgumentParser(description='Generate TTS objects from classified cards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    logger.info("=" * 60)
    logger.info("TTS Object Generation (with embedded stats) - KT-App Pipeline")
    logger.info(f"URL branch: {URL_BRANCH}")
    logger.info("=" * 60)

    # Initialize metadata managers
    pipeline_meta = MetadataManager(PIPELINE_METADATA_FILE)
    output_meta = OutputMetadataManager(OUTPUT_METADATA_FILE)

    # Generate URLs JSON from v3 structure (flat format for internal use)
    logger.info("Scanning output structure...")
    urls_data = generate_urls_json_v3(URL_BRANCH)
    logger.info(f"Found {len(urls_data)} card/asset entries")

    # Generate TTS objects
    config_dir = PROJECT_ROOT / 'config'
    output_dir = PROJECT_ROOT / 'output'
    count = generate_all_tts_objects(urls_data, config_dir, output_dir, args.teams, URL_BRANCH)

    # Rebuild manager bag with latest team boxes.
    manager_count, manager_path = rebuild_kill_team_card_boxes_example(output_dir)

    # Build per-team metadata after Box.json files exist.
    logger.info("Generating team URL metadata for TTS update checks...")
    team_object_urls_data = generate_object_urls_json(URL_BRANCH)
    object_urls_data = generate_object_urls_summary(team_object_urls_data, URL_BRANCH)
    object_urls_file = PROJECT_ROOT / 'output' / 'team-urls.json'
    with open(object_urls_file, 'w', encoding='utf-8') as f:
        json.dump(object_urls_data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved summary team-urls.json with {len(object_urls_data)} teams")

    legacy_object_urls_file = PROJECT_ROOT / 'output' / 'object-urls.json'
    if legacy_object_urls_file.exists():
        try:
            legacy_object_urls_file.unlink()
            logger.info("Removed legacy output/object-urls.json")
        except Exception as e:
            logger.warning(f"Could not remove legacy output/object-urls.json: {e}")

    team_object_url_files = save_object_urls_team_files(team_object_urls_data, PROJECT_ROOT / 'output')
    logger.info(f"Saved {len(team_object_url_files)} team metadata files in output/{{team}}/{{team}}-object-urls.json")

    # Track metadata for all generated Box.json files
    for team_tts_dir in sorted(output_dir.glob("*/tts_objects")):
        team_slug = team_tts_dir.parent.name
        for f in team_tts_dir.glob("*.json"):
            rel = f"{team_slug}/tts_objects/{f.name}"
            pipeline_meta.update_file(team_slug, "7_generate_tts_objects", f.name, f)
            output_meta.update_file(rel, f, "kt-app", "7_generate_tts_objects")
        pipeline_meta.mark_step_complete(team_slug, "7_generate_tts_objects")

    # Track team-urls.json
    output_meta.update_file("team-urls.json", object_urls_file, "kt-app", "7_generate_tts_objects")
    output_meta.metadata.setdefault("files", {}).pop("object-urls.json", None)
    output_meta.metadata.setdefault("files", {}).pop("output_v2/tts-metadata.json", None)
    for team_file in team_object_url_files:
        rel = f"{team_file.parent.name}/{team_file.name}"
        output_meta.update_file(rel, team_file, "kt-app", "7_generate_tts_objects")
    if manager_path:
        output_meta.update_file("_generic-tts-objects/Kill Team Card Boxes.json", manager_path, "kt-app", "7_generate_tts_objects")

    # Save metadata
    pipeline_meta.metadata["last_full_run"] = datetime.now(timezone.utc).isoformat()
    pipeline_meta.save_metadata()
    output_meta.save_metadata()

    logger.info("=" * 60)
    logger.info("Generation Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {count}")
    logger.info(f"Output: {PROJECT_ROOT / 'output' / '{team}' / 'tts_objects'}")


if __name__ == '__main__':
    main()
