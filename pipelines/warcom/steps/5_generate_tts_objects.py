"""
Step 5: Generate TTS Objects from Extracted Cards

Generates Tabletop Simulator (TTS) JSON objects for all teams in the output folder.
Uses a self-contained TTS generation system with:
- Hash-based change detection for incremental updates
- Persistent GUIDs for stable object identity
- Hierarchical metadata tracking (team → cardbox → decks → cards)
- GitHub raw URLs for spawning objects in TTS

Input:  output/{team}/cards/**/*.jpg
Output: tts_objects/{team}/cardbox/*.json (nested structure)
        tts_objects/.tts-metadata.json (full tracking)

Architecture:
- Full metadata: Complete hierarchical structure with all components for repo tracking

Note: This file is self-contained - all TTS generation code is inlined to keep
      each pipeline step independent without external dependencies.
"""

import argparse
import json
import hashlib
import logging
import re
import shutil
import yaml
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


# ===================================================================
# CHANGE DETECTION SYSTEM
# ===================================================================

@dataclass
class ComponentMetadata:
    """Metadata for a single TTS component"""
    guid: str = ""
    url: str = ""
    component_type: str = ""
    content_hash: str = ""
    last_modified: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary maintaining field order"""
        return {
            "guid": self.guid,
            "url": self.url,
            "component_type": self.component_type,
            "content_hash": self.content_hash,
            "last_modified": self.last_modified
        }


class ChangeDetector:
    """Detects changes in TTS components using content hashing."""
    
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load existing metadata from file"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self):
        """Save metadata to file"""
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def compute_hash(self, content: Any) -> str:
        """Compute SHA-256 hash of content."""
        if isinstance(content, dict):
            content_str = json.dumps(content, sort_keys=True, ensure_ascii=False)
            content_bytes = content_str.encode('utf-8')
        elif isinstance(content, str):
            content_bytes = content.encode('utf-8')
        elif isinstance(content, bytes):
            content_bytes = content
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")
        
        return hashlib.sha256(content_bytes).hexdigest()
    
    def has_changed(self, component_path: str, content: Any, component_type: str) -> Tuple[bool, Optional[Dict]]:
        """Check if component content has changed since last generation."""
        current_hash = self.compute_hash(content)
        existing_meta = self._get_component_metadata(component_path)
        
        if existing_meta is None:
            return True, None
        
        stored_hash = existing_meta.get('content_hash')
        return current_hash != stored_hash, existing_meta
    
    def update_metadata(
        self,
        component_path: str,
        content: Any,
        component_type: str,
        guid: str = "",
        url: str = "",
        timestamp: Optional[str] = None
    ) -> ComponentMetadata:
        """Update metadata for a component."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        content_hash = self.compute_hash(content)
        
        # Preserve existing GUID and URL if not provided
        existing_meta = self._get_component_metadata(component_path)
        if not guid and existing_meta and 'guid' in existing_meta:
            guid = existing_meta['guid']
        if not url and existing_meta and 'url' in existing_meta:
            url = existing_meta['url']
        
        metadata = ComponentMetadata(
            guid=guid,
            url=url,
            component_type=component_type,
            content_hash=content_hash,
            last_modified=timestamp
        )
        
        self._set_component_metadata(component_path, metadata.to_dict())
        return metadata
    
    def _get_component_metadata(self, component_path: str) -> Optional[Dict]:
        """Get metadata for component at path"""
        parts = component_path.split('.')
        current = self.metadata
        
        if parts[-1] == "_self":
            parts = parts[:-1]
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        if isinstance(current, dict) and 'content_hash' in current:
            return current
        return None
    
    def _set_component_metadata(self, component_path: str, metadata: Dict):
        """Set metadata for component at path"""
        parts = component_path.split('.')
        current = self.metadata
        
        is_container = parts[-1] == "_self"
        if is_container:
            parts = parts[:-1]
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                raise ValueError(f"Cannot set nested path {component_path}: {part} is a leaf node")
            current = current[part]
        
        last_part = parts[-1]
        metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
        
        if last_part in current and isinstance(current[last_part], dict):
            children = {k: v for k, v in current[last_part].items() if k not in metadata_fields}
            current[last_part] = {**metadata, **children}
        else:
            current[last_part] = metadata
    
    def get_guid(self, component_path: str) -> Optional[str]:
        """Get stored GUID for component"""
        meta = self._get_component_metadata(component_path)
        return meta.get('guid') if meta else None


class ComponentRegistry:
    """Registry of generated components with their metadata."""
    
    def __init__(self, change_detector: ChangeDetector, force_update: bool = False):
        self.detector = change_detector
        self.force_update = force_update
        self.generated_components: Dict[str, ComponentMetadata] = {}
    
    def register(
        self,
        component_path: str,
        content: Any,
        component_type: str,
        guid: str = "",
        url: str = "",
        force_update: bool = False
    ) -> Tuple[bool, ComponentMetadata]:
        """Register a component for generation."""
        changed, existing_meta = self.detector.has_changed(component_path, content, component_type)
        
        if changed or force_update or self.force_update:
            metadata = self.detector.update_metadata(component_path, content, component_type, guid, url)
            self.generated_components[component_path] = metadata
            return True, metadata
        else:
            metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
            filtered_meta = {k: v for k, v in existing_meta.items() if k in metadata_fields}
            metadata = ComponentMetadata(**filtered_meta)
            self.generated_components[component_path] = metadata
            return False, metadata


# ===================================================================
# TTS TAGGING SYSTEM
# ===================================================================

class TTSTagGenerator:
    """Generate consistent tags for TTS objects"""
    
    CARD_TYPE_TAGS = {
        "datacards": "KTCardsDatacard",
        "operative-selection": "KTCardsOperativeSelection",
        "faction-rules": "KTCardsFactionRule",
        "firefight-ploys": "KTCardsFirefightPloy",
        "strategy-ploys": "KTCardsStrategyPloy",
        "equipment": "KTCardsEquipment",
        "tactical-ops": "KTCardsTacticalOps",
        "rare-equipment": "KTCardsRareEquipment",
        "spec-ops": "KTCardsSpecOps",
    }
    
    @classmethod
    def get_card_tags(card_type_class, team_name: str, card_type: str, has_back: bool = True) -> List[str]:
        """Generate tags for a card."""
        tags = []
        
        # Team tag
        team_pascal = ''.join(word.capitalize() for word in team_name.split('-'))
        tags.append(f"KT{team_pascal}")
        
        # Card type tag
        type_tag = card_type_class.CARD_TYPE_TAGS.get(card_type)
        if type_tag:
            tags.append(type_tag)
        
        # Generic card tag
        tags.append("KTCard")
        
        # Double-sided tag
        if has_back:
            tags.append("KTCardDoubleSided")
        
        return tags


def load_text_file(file_path: Path) -> str:
    """Load text from a file, returning an empty string if missing."""
    if not file_path.exists():
        logger.warning("Missing script file: %s", file_path)
        return ""
    # Read with UTF-8 BOM handling
    text = file_path.read_text(encoding="utf-8-sig")
    # Clean up any remaining BOM or special characters
    return text.replace('\ufeff', '').replace('\u200b', '')


def _ensure_bgr_alpha(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return (bgr, alpha) from a possibly alpha-less image."""
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        alpha = np.full((img.shape[0], img.shape[1]), 255, dtype=np.uint8)
        return bgr, alpha
    if img.shape[2] == 4:
        bgr = img[:, :, :3]
        alpha = img[:, :, 3]
        return bgr, alpha
    return img, np.full((img.shape[0], img.shape[1]), 255, dtype=np.uint8)


def _mask_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    x0 = int(xs.min())
    x1 = int(xs.max())
    y0 = int(ys.min())
    y1 = int(ys.max())
    return x0, y0, (x1 - x0 + 1), (y1 - y0 + 1)


def _alpha_from_white_bg(bgr: np.ndarray, existing_alpha: np.ndarray) -> np.ndarray:
    """Create alpha by removing near-white background while respecting existing alpha."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    white = ((v > 235) & (s < 20)) | (
        (bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235)
    )
    alpha = np.where(white, 0, 255).astype(np.uint8)
    if existing_alpha is not None:
        alpha = np.minimum(alpha, existing_alpha)
    return alpha


def _fit_template_mask(
    content_alpha: np.ndarray,
    template_mask: np.ndarray,
) -> np.ndarray:
    """Scale and center template mask to content bounds."""
    bbox = _mask_bbox(content_alpha)
    if bbox is None:
        return np.zeros_like(content_alpha, dtype=np.uint8)
    x, y, w, h = bbox
    if w <= 1 or h <= 1:
        return np.zeros_like(content_alpha, dtype=np.uint8)

    resized = cv2.resize(
        (template_mask > 0).astype(np.uint8),
        (w, h),
        interpolation=cv2.INTER_NEAREST,
    )
    out = np.zeros_like(content_alpha, dtype=np.uint8)
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(out.shape[1], x0 + w)
    y1 = min(out.shape[0], y0 + h)
    rw = x1 - x0
    rh = y1 - y0
    if rw > 0 and rh > 0:
        out[y0:y1, x0:x1] = resized[:rh, :rw]
    return out


def _apply_template_and_save(
    src_path: Path,
    dest_path: Path,
    template_mask: np.ndarray,
    target_size: Tuple[int, int],
) -> bool:
    img = cv2.imread(str(src_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False
    bgr, existing_alpha = _ensure_bgr_alpha(img)
    alpha = _alpha_from_white_bg(bgr, existing_alpha)
    content_mask = (alpha > 0).astype(np.uint8)

    fitted = _fit_template_mask(content_mask, template_mask)
    if fitted is None or fitted.sum() == 0:
        return False
    alpha = np.where(fitted > 0, alpha, 0).astype(np.uint8)

    # Crop to template bounds
    bbox = _mask_bbox(fitted)
    if bbox is not None:
        x, y, w, h = bbox
        bgr = bgr[y : y + h, x : x + w]
        alpha = alpha[y : y + h, x : x + w]

    target_w, target_h = target_size
    if (bgr.shape[1], bgr.shape[0]) != (target_w, target_h):
        bgr = cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
        alpha = cv2.resize(alpha, (target_w, target_h), interpolation=cv2.INTER_AREA)

    rgba = np.dstack([bgr, alpha])
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    return bool(cv2.imwrite(str(dest_path), rgba))


def _load_template_with_size(path: Path) -> Tuple[np.ndarray, Tuple[int, int]]:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to read template: {path}")
    _bgr, alpha = _ensure_bgr_alpha(img)
    mask = (alpha > 0).astype(np.uint8)
    h, w = alpha.shape[:2]
    return mask, (w, h)


def normalize_token_display_name(text: str) -> str:
    """Normalize token display names from OCR text."""
    cleaned = text.strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"\s+(token|marker)$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = cleaned.replace("\n", " ")
    return cleaned


def slugify(value: str) -> str:
    """Create a stable slug for filenames and metadata keys."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        return "token"
    if len(normalized) > 80:
        normalized = normalized[:80].rstrip("-")
    return normalized or "token"


def is_probable_token_label(text: str) -> bool:
    """Heuristic filter to keep token name labels and drop rule text blocks."""
    if not text or not text.strip():
        return False
    if re.search(r"\b(token|marker)\b", text, flags=re.IGNORECASE) is None:
        return False
    cleaned = normalize_token_display_name(text)
    return bool(cleaned) and len(cleaned) <= 60


def load_team_config() -> Dict[str, Any]:
    config_path = Path("config/team-config.yaml")
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def get_token_shape_from_config(team_name: str, token_name: str, config: Dict[str, Any]) -> Optional[str]:
    teams = config.get("teams", {}) if config else {}
    team_data = teams.get(team_name, {}) if teams else {}
    tokens = team_data.get("tokens", []) if team_data else []
    normalized = " ".join((token_name or "").strip().lower().split())
    if not normalized:
        return None
    for token in tokens:
        name = " ".join(str(token.get("name", "")).strip().lower().split())
        if name == normalized:
            shape = token.get("shape")
            if shape in {"round", "octagon", "diamond", "operative"}:
                return shape
    return None


def build_token_name_map(tokens_metadata_path: Path) -> Dict[str, str]:
    """Map token image filenames to display names using extraction metadata."""
    if not tokens_metadata_path.exists():
        return {}

    try:
        data = json.loads(tokens_metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse token metadata %s: %s", tokens_metadata_path, exc)
        return {}

    tokens = data.get("tokens", [])
    text_elements = data.get("text_elements", [])
    tokens_by_card: Dict[str, List[Dict[str, Any]]] = {}
    text_by_card: Dict[str, List[Dict[str, Any]]] = {}

    for token in tokens:
        source_card = token.get("source_card") or "_"
        tokens_by_card.setdefault(source_card, []).append(token)

    for text_element in text_elements:
        source_card = text_element.get("source_card") or "_"
        text_by_card.setdefault(source_card, []).append(text_element)

    name_map: Dict[str, str] = {}
    for source_card, token_list in tokens_by_card.items():
        text_list = text_by_card.get(source_card, [])

        filtered_text_list = [t for t in text_list if is_probable_token_label(t.get("text", ""))]
        if not filtered_text_list:
            continue

        token_items = [t for t in token_list if t.get("bbox")]
        text_items = [t for t in filtered_text_list if t.get("bbox")]
        if not token_items or not text_items:
            continue

        def _center(bbox: Dict[str, Any]) -> Tuple[float, float]:
            x = float(bbox.get("x", 0.0))
            y = float(bbox.get("y", 0.0))
            w = float(bbox.get("width", 0.0))
            h = float(bbox.get("height", 0.0))
            return x + (w / 2.0), y + (h / 2.0)

        def _max_extent(items: List[Dict[str, Any]]) -> Tuple[float, float]:
            max_x = 0.0
            max_y = 0.0
            for item in items:
                bbox = item.get("bbox", {})
                x = float(bbox.get("x", 0.0))
                y = float(bbox.get("y", 0.0))
                w = float(bbox.get("width", 0.0))
                h = float(bbox.get("height", 0.0))
                max_x = max(max_x, x + w)
                max_y = max(max_y, y + h)
            return max_x, max_y

        token_max_x, token_max_y = _max_extent(token_items)
        text_max_x, text_max_y = _max_extent(text_items)
        scale_x = text_max_x / token_max_x if token_max_x > 0 else 1.0
        scale_y = text_max_y / token_max_y if token_max_y > 0 else 1.0
        if not (1.25 <= scale_x <= 3.0):
            scale_x = 1.0
        if not (1.25 <= scale_y <= 3.0):
            scale_y = 1.0

        token_centers = []
        for idx, t in enumerate(token_items):
            bbox = t.get("bbox", {})
            cx, cy = _center(bbox)
            tw = float(bbox.get("width", 0.0)) * scale_x
            th = float(bbox.get("height", 0.0)) * scale_y
            token_centers.append((idx, (cx * scale_x, cy * scale_y), tw, th, t))

        text_centers = [(idx, _center(t.get("bbox", {})), t) for idx, t in enumerate(text_items)]

        # Build candidate pairs with a directional preference: labels should be right or below tokens.
        pairs: List[Tuple[float, int, int]] = []
        valid_label_map: Dict[int, bool] = {}
        for ti, (tx, ty), tw, th, _ in token_centers:
            has_valid = False
            for _li, (lx, ly), _ in text_centers:
                if (lx - tx) >= (-0.2 * max(1.0, tw)) and (ly - ty) >= (-0.2 * max(1.0, th)):
                    has_valid = True
                    break
            valid_label_map[ti] = has_valid

        for ti, (tx, ty), tw, th, _ in token_centers:
            require_direction = valid_label_map.get(ti, False)
            for li, (lx, ly), _ in text_centers:
                dx = lx - tx
                dy = ly - ty
                direction_ok = (dx >= (-0.2 * max(1.0, tw))) and (dy >= (-0.2 * max(1.0, th)))
                if require_direction and not direction_ok:
                    continue
                dist = (dx * dx + dy * dy) ** 0.5
                pairs.append((dist, ti, li))
        pairs.sort(key=lambda p: p[0])

        assigned_tokens = set()
        assigned_labels = set()
        assignment: Dict[int, int] = {}
        for dist, ti, li in pairs:
            if ti in assigned_tokens or li in assigned_labels:
                continue
            assignment[ti] = li
            assigned_tokens.add(ti)
            assigned_labels.add(li)

        for ti, _center_pt, _tw, _th, token_item in token_centers:
            li = assignment.get(ti)
            if li is None:
                continue
            text_item = text_centers[li][2]
            display_name = normalize_token_display_name(text_item.get("text", ""))
            filename = token_item.get("filename")
            if filename and display_name:
                name_map[filename] = display_name

    return name_map


def prepare_clean_tokens(team_name: str, workspace_root: Path) -> Tuple[Optional[Path], Dict[str, str]]:
    """Generate cleaned/transparent tokens in output/{team}/tokens from extracted metadata."""
    extracted_team_dir = workspace_root / "layers" / "warcom" / "extracted" / team_name
    extracted_tokens_dir = extracted_team_dir / "tokens"
    metadata_path = extracted_tokens_dir / f"{team_name}_tokens_metadata.json"
    if not extracted_tokens_dir.exists() or not metadata_path.exists():
        return None, {}

    name_map = build_token_name_map(metadata_path)
    if not name_map:
        return None, {}
    final_tokens_dir = workspace_root / "output" / team_name / "tokens"
    if final_tokens_dir.exists():
        shutil.rmtree(final_tokens_dir, ignore_errors=True)
    final_tokens_dir.mkdir(parents=True, exist_ok=True)

    # Build extraction-metadata.json for template selection
    config = load_team_config()
    tokens_meta = []
    missing_names = []
    for token_path in sorted(extracted_tokens_dir.glob("*.png")):
        display_name = name_map.get(token_path.name, "").strip()
        display_name = normalize_token_display_name(display_name)
        if not display_name:
            missing_names.append(token_path.name)
            continue
        shape = get_token_shape_from_config(team_name, display_name, config)
        tokens_meta.append({
            "filename": token_path.name,
            "name": display_name,
            "shape": shape,
        })

    if missing_names:
        logger.error("Missing token name mappings for %s: %s", team_name, ", ".join(missing_names))
        return None, {}

    extraction_meta_path = extracted_tokens_dir / "extraction-metadata.json"
    extraction_meta_path.write_text(
        json.dumps({"tokens": tokens_meta}, indent=2),
        encoding="utf-8",
    )

    template_dir = workspace_root / "config" / "defaults" / "tts-token"
    template_paths = {
        "operative": template_dir / "input" / "template-operative-cutter.png",
        "round": template_dir / "input" / "template-round-cutter.png",
        "octagon": template_dir / "input" / "template-octagon-cutter.png",
        "diamond": template_dir / "input" / "template-diamond-cutter.png",
    }
    templates: Dict[str, Tuple[np.ndarray, Tuple[int, int]]] = {}
    for key, path in template_paths.items():
        if not path.exists():
            logger.error("Missing token template: %s", path)
            return None, {}
        templates[key] = _load_template_with_size(path)

    # Apply transparency + template-fit directly in step 5
    for token_path in sorted(extracted_tokens_dir.glob("*.png")):
        display_name = name_map.get(token_path.name, "").strip()
        display_name = normalize_token_display_name(display_name)
        if not display_name:
            logger.error("Missing token name for %s (%s)", team_name, token_path.name)
            return None, {}
        shape = get_token_shape_from_config(team_name, display_name, config) or "operative"
        template_mask, target_size = templates.get(shape, templates["operative"])
        dest_path = final_tokens_dir / token_path.name
        if not _apply_template_and_save(token_path, dest_path, template_mask, target_size):
            logger.error("Failed to process token image %s for %s", token_path.name, team_name)
            return None, {}

    output_name_map: Dict[str, str] = {}
    used_slugs: Dict[str, int] = {}
    for token_path in sorted(final_tokens_dir.glob("*.png")):
        display_name = name_map.get(token_path.name, "").strip()
        if not display_name:
            logger.error("Missing token name for %s (%s)", team_name, token_path.name)
            return None, {}
        display_name = normalize_token_display_name(display_name)
        slug = slugify(display_name)
        count = used_slugs.get(slug, 0) + 1
        used_slugs[slug] = count
        if count > 1:
            slug = f"{slug}-{count}"
        dest = final_tokens_dir / f"{slug}.png"
        if dest != token_path:
            if dest.exists():
                dest.unlink()
            token_path.rename(dest)
        output_name_map[dest.name] = display_name

    return final_tokens_dir, output_name_map


def find_tokens_dir(team_name: str, workspace_root: Path) -> Optional[Path]:
    """Locate the tokens directory for a team if it exists."""
    output_tokens = workspace_root / "output" / team_name / "tokens"
    if output_tokens.exists():
        return output_tokens

    extracted_tokens = workspace_root / "layers" / "warcom" / "extracted" / team_name / "tokens"
    if extracted_tokens.exists():
        return extracted_tokens

    return None


def build_raw_url(file_path: Path, workspace_root: Path, branch: str = "main") -> str:
    """Build a GitHub raw URL for a local file path."""
    repo_base = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}"
    rel_path = file_path.relative_to(workspace_root).as_posix()
    return f"{repo_base}/{rel_path}"


# ===================================================================
# TTS COMPONENT CLASSES
# ===================================================================

class TTSComponent(ABC):
    """Abstract base class for all TTS components."""
    
    def __init__(self, registry: ComponentRegistry):
        self.registry = registry
        self.metadata: Optional[ComponentMetadata] = None
        self._content: Optional[Dict] = None
    
    @abstractmethod
    def generate(self) -> Dict[str, Any]:
        """Generate the TTS JSON structure for this component."""
        pass
    
    @abstractmethod
    def get_component_path(self) -> str:
        """Get the dot-notation path for this component."""
        pass
    
    @abstractmethod
    def get_component_type(self) -> str:
        """Get the component type identifier."""
        pass
    
    def build(self, force_update: bool = False) -> Tuple[Dict[str, Any], bool]:
        """Build the component with change detection."""
        content = self.generate()
        self._content = content
        
        guid = content.get('GUID', '')
        url = self._generate_json_url()
        
        was_updated, metadata = self.registry.register(
            self.get_component_path(),
            content,
            self.get_component_type(),
            guid,
            url,
            force_update
        )
        
        self.metadata = metadata
        return content, was_updated
    
    def _generate_json_url(self) -> str:
        """Generate GitHub raw URL to this component's JSON file."""
        workspace_root = Path(__file__).parent.parent.parent.parent
        # Get team name from component path
        path_parts = self.get_component_path().split('.')
        team_name = path_parts[0]
        
        # Calculate relative path from workspace root
        output_base = workspace_root / "output" / team_name / "tts"
        file_path = self.get_file_path(output_base)
        rel_path = file_path.relative_to(workspace_root).as_posix()
        
        repo_url = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"
        return f"{repo_url}/{rel_path}"
    
    def get_file_path(self, output_dir: Path) -> Path:
        """Get the file path for this component based on its component path."""
        path_parts = self.get_component_path().split('.')
        team_name = path_parts[0]
        
        if len(path_parts) == 3 and path_parts[2] == "_self":
            # team.cardbox._self -> output/{team}/tts/{team}-cardbox.json
            return output_dir / f"{team_name}-cardbox.json"
        elif len(path_parts) == 4 and path_parts[2] == "token-bag" and path_parts[3] == "_self":
            # team.cardbox.token-bag._self -> output/{team}/tts/cardbox/token-bag/{team}-token-bag.json
            return output_dir / "cardbox" / "token-bag" / f"{team_name}-token-bag.json"
        elif len(path_parts) == 4 and path_parts[3] == "_self":
            # team.cardbox.TYPE._self -> output/{team}/tts/cardbox/decks/{team}-TYPE.json
            return output_dir / "cardbox" / "decks" / f"{team_name}-{path_parts[2]}.json"
        elif len(path_parts) == 5 and path_parts[2] == "token-bag" and path_parts[4] == "_self":
            # team.cardbox.token-bag.NAME._self -> output/{team}/tts/cardbox/token-bag/NAME/{team}-NAME.json
            return output_dir / "cardbox" / "token-bag" / path_parts[3] / f"{team_name}-{path_parts[3]}.json"
        elif len(path_parts) == 4:
            # team.cardbox.TYPE.NAME -> output/{team}/tts/cardbox/decks/TYPE/{team}-NAME.json
            return output_dir / "cardbox" / "decks" / path_parts[2] / f"{team_name}-{path_parts[3]}.json"
        elif len(path_parts) == 5 and path_parts[2] == "token-bag":
            # team.cardbox.token-bag.NAME.TOKEN -> output/{team}/tts/cardbox/token-bag/NAME/{team}-TOKEN.json
            return output_dir / "cardbox" / "token-bag" / path_parts[3] / f"{team_name}-{path_parts[4]}.json"
        elif len(path_parts) == 3:
            # team.cardbox.NAME (single card) -> output/{team}/tts/cardbox/{team}-NAME.json
            return output_dir / "cardbox" / f"{team_name}-{path_parts[2]}.json"
        else:
            raise ValueError(f"Unexpected component path format: {self.get_component_path()}")


class TTSCard(TTSComponent):
    """TTS Card component"""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        card_name: str,
        front_url: str,
        back_url: str,
        card_type: str = None,
        is_in_deck: bool = True,
        tags: Optional[List[str]] = None
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.card_name = card_name
        self.front_url = front_url
        self.back_url = back_url
        self.card_type = card_type
        self.is_in_deck = is_in_deck
        self.tags = tags or []
    
    def get_component_path(self) -> str:
        if self.is_in_deck and self.card_type:
            return f"{self.team_name}.cardbox.{self.card_type}.{self.card_name}"
        else:
            return f"{self.team_name}.cardbox.{self.card_type or self.card_name}"
    
    def get_component_type(self) -> str:
        return "card"
    
    def generate(self) -> Dict[str, Any]:
        """Generate TTS Card object"""
        # Generate unique CardID based on card path hash
        # TTS uses custom_deck_id (first 3+ digits) + card_number (last 2 digits)
        # We'll use a hash of the card path to ensure uniqueness
        hash_input = f"{self.team_name}_{self.card_type}_{self.card_name}".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        # Use first 4 chars of hash for custom deck ID (1000-FFFF range)
        custom_deck_id = str(int(hash_hex[:4], 16) % 9000 + 1000)  # Keep in 1000-9999 range
        card_id = int(custom_deck_id + "00")  # Card 00 in this deck
        
        return {
            "GUID": self._generate_guid(),
            "Name": "Card",
            "Transform": {
                "posX": 0.0,
                "posY": 3.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 180.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": self.card_name,
            "Description": "",
            "GMNotes": "",
            "Tags": self.tags,
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "CardID": card_id,
            "SidewaysCard": False,
            "CustomDeck": {
                custom_deck_id: {
                    "FaceURL": self.front_url,
                    "BackURL": self.back_url,
                    "NumWidth": 1,
                    "NumHeight": 1,
                    "BackIsHidden": True,
                    "UniqueBack": False,
                    "Type": 0
                }
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    
    def _generate_guid(self) -> str:
        """Generate or retrieve persistent GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_{self.card_name}".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSDeck(TTSComponent):
    """TTS Deck component"""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        deck_type: str,
        cards: List[TTSCard]
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.deck_type = deck_type
        self.cards = cards
    
    def get_component_path(self) -> str:
        return f"{self.team_name}.cardbox.{self.deck_type}._self"
    
    def get_component_type(self) -> str:
        return "deck"
    
    def generate(self) -> Dict[str, Any]:
        """Generate TTS Deck object"""
        card_objects = []
        for card in self.cards:
            card_content, _ = card.build()
            card_objects.append(card_content)
        
        return {
            "GUID": self._generate_guid(),
            "Name": "Deck",
            "Transform": {
                "posX": 0.0,
                "posY": 3.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 180.0,
                "scaleX": 1.0,
                "scaleY": 1.0,
                "scaleZ": 1.0
            },
            "Nickname": f"{self.deck_type} deck",
            "Description": "",
            "GMNotes": "",
            "Tags": [f"_{self.team_name}"],
            "DeckIDs": [card["CardID"] for card in card_objects],
            "CustomDeck": self._merge_custom_decks(card_objects),
            "ContainedObjects": card_objects,
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": ""
        }
    
    def _merge_custom_decks(self, cards: List[Dict]) -> Dict:
        """Merge CustomDeck definitions from all cards"""
        merged = {}
        for card in cards:
            if "CustomDeck" in card:
                merged.update(card["CustomDeck"])
        return merged
    
    def _generate_guid(self) -> str:
        """Generate or retrieve persistent GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_{self.deck_type}_deck".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSToken(TTSComponent):
    """TTS Token component"""

    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        token_name: str,
        image_url: str,
        tags: Optional[List[str]] = None
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.token_name = token_name
        self.image_url = image_url
        self.tags = tags or ["KTUIStackable", "KTUIToken"]

    def get_component_path(self) -> str:
        token_slug = slugify(self.token_name)
        return f"{self.team_name}.cardbox.token-bag.{token_slug}.{token_slug}-token"

    def get_component_type(self) -> str:
        return "token"

    def generate(self) -> Dict[str, Any]:
        return {
            "GUID": self._generate_guid(),
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
            "Nickname": self.token_name,
            "Description": self.token_name,
            "ColorDiffuse": {
                "r": 1.0,
                "g": 1.0,
                "b": 1.0
            },
            "Tags": self.tags,
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
            "CustomImage": {
                "ImageURL": self.image_url,
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": 11.0,
                    "StandUp": False,
                    "Stackable": False
                }
            }
        }

    def _generate_guid(self) -> str:
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid

        hash_input = f"{self.team_name}_{self.token_name}_token".encode("utf-8")
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSTokenDispenser(TTSComponent):
    """TTS Token Dispenser (infinite bag) component"""

    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        dispenser_name: str,
        token: TTSToken,
        mesh_url: str
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.dispenser_name = dispenser_name
        self.token = token
        self.mesh_url = mesh_url

    def get_component_path(self) -> str:
        dispenser_slug = slugify(self.dispenser_name)
        return f"{self.team_name}.cardbox.token-bag.{dispenser_slug}._self"

    def get_component_type(self) -> str:
        return "token_dispenser"

    def generate(self) -> Dict[str, Any]:
        token_content, _ = self.token.build()
        locked_child = json.loads(json.dumps(token_content))
        locked_child["Locked"] = True
        locked_child["Transform"] = {
            "posX": 0.0,
            "posY": 0.0,
            "posZ": 0.0,
            "rotX": 0.0,
            "rotY": 0.0,
            "rotZ": 0.0,
            "scaleX": token_content["Transform"]["scaleX"],
            "scaleY": token_content["Transform"]["scaleY"],
            "scaleZ": token_content["Transform"]["scaleZ"]
        }

        return {
            "GUID": self._generate_guid(),
            "Name": "Custom_Model_Infinite_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 1.03,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": 1.85,
                "scaleY": 0.1,
                "scaleZ": 1.78
            },
            "Nickname": self.dispenser_name,
            "Description": f"Infinite {self.dispenser_name} tokens",
            "ColorDiffuse": {
                "r": 1.0,
                "g": 1.0,
                "b": 1.0,
                "a": 0.0
            },
            "Tags": [f"_{self.team_name}_tokens"],
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "Hands": False,
            "CustomMesh": {
                "MeshURL": self.mesh_url,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 7,
                "CastShadows": True
            },
            "Bag": {
                "Order": 0
            },
            "ContainedObjects": [token_content],
            "ChildObjects": [locked_child]
        }

    def _generate_guid(self) -> str:
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid

        hash_input = f"{self.team_name}_{self.dispenser_name}_dispenser".encode("utf-8")
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSTokenBag(TTSComponent):
    """TTS Token Bag container component"""

    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        dispensers: List[TTSTokenDispenser],
        mesh_url: str,
        lua_script: str
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.dispensers = dispensers
        self.mesh_url = mesh_url
        self.lua_script = lua_script

    def get_component_path(self) -> str:
        return f"{self.team_name}.cardbox.token-bag._self"

    def get_component_type(self) -> str:
        return "token_bag"

    def generate(self) -> Dict[str, Any]:
        dispenser_objects = []
        for dispenser in self.dispensers:
            dispenser_content, _ = dispenser.build()
            dispenser_objects.append(dispenser_content)

        return {
            "GUID": self._generate_guid(),
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
            "Nickname": f"{self.team_name.replace('-', ' ').title()} tokens",
            "Description": "If errors pop up, just wait for few sec and try again",
            "GMNotes": f"_{self.team_name}_tokens",
            "ColorDiffuse": {
                "r": 1.0,
                "g": 1.0,
                "b": 1.0,
                "a": 0.0
            },
            "Tags": [f"_{self.team_name}"],
            "Locked": False,
            "Grid": True,
            "Snap": True,
            "Autoraise": True,
            "Sticky": True,
            "Tooltip": True,
            "Hands": False,
            "Number": 0,
            "CustomMesh": {
                "MeshURL": self.mesh_url,
                "DiffuseURL": "",
                "NormalURL": "",
                "ColliderURL": "",
                "Convex": True,
                "MaterialIndex": 0,
                "TypeIndex": 6,
                "CastShadows": True
            },
            "Bag": {
                "Order": 0
            },
            "LuaScript": self.lua_script,
            "LuaScriptState": "",
            "ContainedObjects": dispenser_objects
        }

    def _generate_guid(self) -> str:
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid

        hash_input = f"{self.team_name}_token_bag".encode("utf-8")
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


class TTSCardBox(TTSComponent):
    """Complete TTS card box containing all decks for a team."""
    
    def __init__(
        self,
        registry: ComponentRegistry,
        team_name: str,
        team_display_name: str,
        faction: str,
        decks: List[TTSDeck],
        mesh_url: str,
        texture_url: str,
        lua_script: str = "",
        single_cards: Optional[List[TTSCard]] = None,
        token_bag: Optional[Any] = None
    ):
        super().__init__(registry)
        self.team_name = team_name
        self.team_display_name = team_display_name
        self.faction = faction
        self.decks = decks
        self.single_cards = single_cards or []
        self.mesh_url = mesh_url
        self.texture_url = texture_url
        self.lua_script = lua_script
        self.token_bag = token_bag
    
    def get_component_path(self) -> str:
        return f"{self.team_name}.cardbox._self"
    
    def get_component_type(self) -> str:
        return "cardbox"
    
    def generate(self) -> Dict[str, Any]:
        """Generate complete TTS cardbox"""
        deck_objects = []
        for deck in self.decks:
            deck_content, _ = deck.build()
            deck_objects.append(deck_content)
        
        for card in self.single_cards:
            card_content, _ = card.build()
            deck_objects.append(card_content)
        
        if self.token_bag:
            token_bag_content, _ = self.token_bag.build()
            deck_objects.append(token_bag_content)
        
        # Aggregate timestamps from metadata
        card_timestamps = []
        token_timestamps = []
        
        if self.team_name in self.registry.detector.metadata:
            team_meta = self.registry.detector.metadata[self.team_name]
            if "cardbox" in team_meta:
                cardbox_meta = team_meta["cardbox"]
                metadata_fields = {"guid", "url", "component_type", "content_hash", "last_modified"}
                
                for key, value in cardbox_meta.items():
                    if key in metadata_fields:
                        continue
                    if isinstance(value, dict):
                        if "last_modified" in value:
                            card_timestamps.append(value["last_modified"])
                        for card_key, card_data in value.items():
                            if card_key not in metadata_fields and isinstance(card_data, dict) and "last_modified" in card_data:
                                card_timestamps.append(card_data["last_modified"])

                if "token-bag" in cardbox_meta and isinstance(cardbox_meta["token-bag"], dict):
                    token_bag_meta = cardbox_meta["token-bag"]
                    if "last_modified" in token_bag_meta:
                        token_timestamps.append(token_bag_meta["last_modified"])
                    for dispenser_key, dispenser_data in token_bag_meta.items():
                        if dispenser_key in metadata_fields:
                            continue
                        if isinstance(dispenser_data, dict) and "last_modified" in dispenser_data:
                            token_timestamps.append(dispenser_data["last_modified"])
                        for token_key, token_data in dispenser_data.items():
                            if token_key in metadata_fields:
                                continue
                            if isinstance(token_data, dict) and "last_modified" in token_data:
                                token_timestamps.append(token_data["last_modified"])
        
        card_timestamp = max(card_timestamps) if card_timestamps else ""
        token_timestamp = max(token_timestamps) if token_timestamps else ""
        
        lua_script_state = {
            "ml": {},
            "rr": 270,
            "teamSlug": self.team_name,
            "lastCardUpdate": card_timestamp,
            "lastTokenUpdate": token_timestamp,
            "tokenBagPositions": {}
        }
        
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
            "ObjectStates": [
                {
                    "GUID": self._generate_guid(),
                    "Name": "Custom_Model_Bag",
                    "Transform": {
                        "posX": 0.0,
                        "posY": 3.5,
                        "posZ": 0.0,
                        "rotX": 0.0,
                        "rotY": 270.0,
                        "rotZ": 0.0,
                        "scaleX": 1.0,
                        "scaleY": 1.0,
                        "scaleZ": 1.0
                    },
                    "Nickname": self.team_display_name,
                    "Description": "",
                    "GMNotes": f"_{self.team_name}",
                    "Tags": ["_Faction_Decks"],
                    "Locked": False,
                    "CustomMesh": {
                        "MeshURL": self.mesh_url,
                        "DiffuseURL": self.texture_url,
                        "NormalURL": "",
                        "ColliderURL": "",
                        "Convex": True,
                        "MaterialIndex": 0,
                        "TypeIndex": 6,
                        "CastShadows": True
                    },
                    "Bag": {
                        "Order": 0
                    },
                    "LuaScript": self.lua_script,
                    "LuaScriptState": json.dumps(lua_script_state, separators=(',', ': ')),
                    "ContainedObjects": deck_objects,
                    "XmlUI": ""
                }
            ]
        }
    
    def _generate_guid(self) -> str:
        """Generate deterministic GUID"""
        stored_guid = self.registry.detector.get_guid(self.get_component_path())
        if stored_guid:
            return stored_guid
        
        hash_input = f"{self.team_name}_cardbox".encode('utf-8')
        hash_hex = hashlib.md5(hash_input).hexdigest()
        return hash_hex[:6]


# ===================================================================
# PIPELINE FUNCTIONS
# ===================================================================


def find_all_teams(output_dir: Path) -> List[Path]:
    """Find all team directories in output folder."""
    teams = []
    for team_dir in output_dir.iterdir():
        if team_dir.is_dir() and (team_dir / 'cards').exists():
            teams.append(team_dir)
    return sorted(teams)


def get_team_metadata(team_dir: Path) -> Dict[str, str]:
    """
    Extract team metadata from directory structure.
    
    Returns:
        Dict with team_name, faction, army (if available)
    """
    team_name = team_dir.name
    
    # Try to infer faction from known mappings or metadata files
    # For now, return basic info
    return {
        'team_name': team_name,
        'slug': team_name
    }


def find_card_images(cards_dir: Path, card_type: str, card_name: str, branch: str = "main") -> Dict[str, str]:
    """
    Find front and back images for a card.
    
    Args:
        cards_dir: Base cards directory (output/{team}/cards/)
        card_type: Type of card (datacards, equipment, firefight-ploys, etc.)
        card_name: Card name
        branch: Git branch for GitHub raw URLs (default: main)
    
    Returns:
        Dict with 'front' and 'back' GitHub raw URLs (back may be empty)
    """
    # Handle ploys subdirectory structure
    if card_type.endswith('-ploys'):
        # firefight-ploys -> ploys/firefight, strategy-ploys -> ploys/strategy
        ploy_type = card_type.replace('-ploys', '')
        type_dir = cards_dir / 'ploys' / ploy_type
    else:
        type_dir = cards_dir / card_type
    
    if not type_dir.exists():
        return {'front': '', 'back': ''}
    
    # Build GitHub raw URL base
    repo_base = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}"
    team_name = cards_dir.parent.name
    
    # Look for front and back images
    front_patterns = [f"{card_name}-front.jpg", f"{card_name}-front.png"]
    back_patterns = [f"{card_name}-back.jpg", f"{card_name}-back.png"]
    
    front_url = ""
    back_url = ""
    
    # Get workspace root
    workspace_root = Path(__file__).parent.parent.parent.parent
    
    for pattern in front_patterns:
        front_path = type_dir / pattern
        if front_path.exists():
            rel_path = front_path.relative_to(workspace_root)
            front_url = f"{repo_base}/{rel_path.as_posix()}"
            break
    
    for pattern in back_patterns:
        back_path = type_dir / pattern
        if back_path.exists():
            rel_path = back_path.relative_to(workspace_root)
            back_url = f"{repo_base}/{rel_path.as_posix()}"
            break
    
    return {'front': front_url, 'back': back_url}


def organize_cards_by_type(cards_dir: Path) -> Dict[str, List[str]]:
    """
    Organize cards by type based on directory structure.
    
    Returns:
        Dict mapping card_type -> list of card base names
    """
    cards_by_type = {}
    
    for type_dir in cards_dir.iterdir():
        if not type_dir.is_dir():
            continue
        
        # Handle ploys/ subdirectory with firefight/ and strategy/
        if type_dir.name == 'ploys':
            for ploy_subdir in type_dir.iterdir():
                if not ploy_subdir.is_dir():
                    continue
                
                # firefight -> firefight-ploys, strategy -> strategy-ploys
                card_type = f"{ploy_subdir.name}-ploys"
                cards = set()
                
                for img_path in ploy_subdir.glob('*.jpg'):
                    name = img_path.stem
                    if name.endswith('-front'):
                        base_name = name[:-6]
                    elif name.endswith('-back'):
                        base_name = name[:-5]
                    else:
                        base_name = name
                    
                    team_name = cards_dir.parent.name
                    if base_name.startswith(f"{team_name}-"):
                        base_name = base_name[len(team_name)+1:]
                    
                    cards.add(base_name)
                
                if cards:
                    cards_by_type[card_type] = sorted(cards)
            continue
        
        card_type = type_dir.name
        cards = set()
        
        # Find all card base names (strip -front/-back suffix)
        for img_path in type_dir.glob('*.jpg'):
            name = img_path.stem
            # Remove -front/-back suffix
            if name.endswith('-front'):
                base_name = name[:-6]
            elif name.endswith('-back'):
                base_name = name[:-5]
            else:
                base_name = name
            
            # Remove team prefix if present
            team_name = cards_dir.parent.name
            if base_name.startswith(f"{team_name}-"):
                base_name = base_name[len(team_name)+1:]
            
            cards.add(base_name)
        
        if cards:
            cards_by_type[card_type] = sorted(cards)
    
    return cards_by_type


def register_lua_script_component(
    team_name: str,
    registry: ComponentRegistry,
    script_text: str,
    component_path: str,
    script_output_path: Path,
    workspace_root: Path,
    branch: str = "main"
) -> bool:
    """Register a Lua script as a metadata component and write it to disk."""
    content = {"lua_script": script_text}
    script_url = build_raw_url(script_output_path, workspace_root, branch)

    was_updated, _ = registry.register(
        component_path,
        content,
        "lua_script",
        guid="",
        url=script_url,
        force_update=False
    )

    if was_updated or not script_output_path.exists():
        script_output_path.parent.mkdir(parents=True, exist_ok=True)
        script_output_path.write_text(script_text, encoding="utf-8")

    return was_updated


def generate_team_tts(team_dir: Path, output_dir: Path, registry: ComponentRegistry, branch: str = "main") -> bool:
    """
    Generate TTS objects for a single team.
    
    Args:
        team_dir: Path to team directory (output/{team}/)
        output_dir: Base TTS output directory (tts_objects/)
        registry: Component registry for change detection
        branch: Git branch for GitHub raw URLs (default: main)
    
    Returns:
        True if any components were updated
    """
    workspace_root = Path(__file__).parent.parent.parent.parent
    team_meta = get_team_metadata(team_dir)
    team_name = team_meta['team_name']
    cards_dir = team_dir / 'cards'

    logger.info("Processing %s...", team_name)
    
    # Organize cards by type
    cards_by_type = organize_cards_by_type(cards_dir)
    
    if not cards_by_type:
        logger.warning("No cards found for %s", team_name)
        return False
    
    # Map card types to deck types
    type_mapping = {
        'datacards': 'datacards',
        'equipment': 'equipment',
        'faction-rules': 'faction-rules',
        'ploys': 'firefight-ploys',  # Assume firefight ploys for now
        'operative-selection': 'operative-selection'
    }
    
    all_decks = []
    single_cards = []
    
    # Create decks/cards for each type
    for card_type, card_names in cards_by_type.items():
        deck_type = type_mapping.get(card_type, card_type)
        
        # If only one card of this type, make it a single card
        if len(card_names) == 1:
            card_name = card_names[0]
            images = find_card_images(cards_dir, card_type, f"{team_name}-{card_name}", branch)
            
            if images['front']:
                card = TTSCard(
                    registry=registry,
                    team_name=team_name,
                    card_name=card_name,
                    front_url=images['front'],
                    back_url=images['back'] or images['front'],
                    card_type=deck_type,
                    is_in_deck=False,
                    tags=TTSTagGenerator.get_card_tags(team_name, deck_type, bool(images['back']))
                )
                single_cards.append(card)
                logger.info("Created single card: %s (%s)", card_name, deck_type)
            continue
        
        # Create deck for this type (multiple cards)
        cards_in_deck = []
        for card_name in card_names:
            images = find_card_images(cards_dir, card_type, f"{team_name}-{card_name}", branch)
            
            if not images['front']:
                logger.warning("Missing front image for %s", card_name)
                continue
            
            card = TTSCard(
                registry=registry,
                team_name=team_name,
                card_name=card_name,
                front_url=images['front'],
                back_url=images['back'] or images['front'],
                card_type=deck_type,
                is_in_deck=True,
                tags=TTSTagGenerator.get_card_tags(team_name, deck_type, bool(images['back']))
            )
            cards_in_deck.append(card)
        
        if cards_in_deck:
            deck = TTSDeck(
                registry=registry,
                team_name=team_name,
                deck_type=deck_type,
                cards=cards_in_deck
            )
            all_decks.append(deck)
            logger.info("Created %s deck with %d cards", deck_type, len(cards_in_deck))
    
    token_bag = None
    tokens_dir, token_name_map = prepare_clean_tokens(team_name, workspace_root)
    if tokens_dir:
        token_images = sorted(tokens_dir.glob('*.png'))
        if token_images:
            dispenser_mesh_path = workspace_root / "config" / "defaults" / "tts-token" / "square-bag-mesh.obj"
            dispenser_mesh_url = build_raw_url(dispenser_mesh_path, workspace_root, branch)
            token_bag_script_path = workspace_root / "config" / "defaults" / "tts-script" / "token-bag-script.lua"
            token_bag_script = load_text_file(token_bag_script_path)

            dispensers = []
            seen_slugs = set()

            for token_path in token_images:
                display_name = token_name_map.get(token_path.name, "")
                if not display_name:
                    display_name = token_path.stem.replace("_", " ").replace("-", " ").title()

                token_slug = slugify(display_name)
                if token_slug in seen_slugs:
                    logger.warning("Duplicate token name '%s' in %s", display_name, tokens_dir)
                    continue
                seen_slugs.add(token_slug)

                image_url = build_raw_url(token_path, workspace_root, branch)
                token = TTSToken(
                    registry=registry,
                    team_name=team_name,
                    token_name=display_name,
                    image_url=image_url
                )
                dispenser = TTSTokenDispenser(
                    registry=registry,
                    team_name=team_name,
                    dispenser_name=display_name,
                    token=token,
                    mesh_url=dispenser_mesh_url
                )
                dispensers.append(dispenser)

            if dispensers:
                token_bag_mesh_path = workspace_root / "config" / "defaults" / "tts-token" / "square-bag-mesh.obj"
                token_bag_mesh_url = build_raw_url(token_bag_mesh_path, workspace_root, branch)
                token_bag = TTSTokenBag(
                    registry=registry,
                    team_name=team_name,
                    dispensers=dispensers,
                    mesh_url=token_bag_mesh_url,
                    lua_script=token_bag_script
                )
                logger.info("Created token bag with %d dispensers", len(dispensers))
    else:
        logger.error("Token processing failed for %s; missing name mapping.", team_name)
        # Don't return early - continue to save cards even if tokens fail
        # return False
    
    # Create card box (container for all decks and token bag)
    # TODO: Extract proper faction and display name from metadata
    team_display_name = team_name.replace('-', ' ').title()
    faction = "Unknown"  # Will be extracted from metadata in future
    
    # Check for team-specific box, otherwise use default
    team_box_dir = workspace_root / "config" / "teams" / team_name / "box"
    if team_box_dir.exists():
        mesh_path = team_box_dir / "card-box.obj"
        texture_path = team_box_dir / "card-box-texture.jpg"
    else:
        mesh_path = workspace_root / "config" / "defaults" / "box" / "card-box.obj"
        texture_path = workspace_root / "config" / "defaults" / "box" / "card-box-texture.jpg"
    
    mesh_url = build_raw_url(mesh_path, workspace_root, branch)
    texture_url = build_raw_url(texture_path, workspace_root, branch)

    cardbox_script_path = workspace_root / "config" / "defaults" / "tts-script" / "tts-update-rules-in-box-script.lua"
    cardbox_script = load_text_file(cardbox_script_path)
    
    cardbox = TTSCardBox(
        registry=registry,
        team_name=team_name,
        team_display_name=team_display_name,
        faction=faction,
        decks=all_decks,
        single_cards=single_cards,
        token_bag=token_bag,
        mesh_url=mesh_url,
        texture_url=texture_url,
        lua_script=cardbox_script
    )

    # Register Lua script components for metadata tracking
    register_lua_script_component(
        team_name=team_name,
        registry=registry,
        script_text=cardbox_script,
        component_path=f"{team_name}.cardbox.lua-script",
        script_output_path=output_dir / team_name / "tts" / "cardbox" / f"{team_name}-lua-script.lua",
        workspace_root=workspace_root,
        branch=branch
    )

    if token_bag:
        register_lua_script_component(
            team_name=team_name,
            registry=registry,
            script_text=token_bag.lua_script,
            component_path=f"{team_name}.cardbox.token-bag.lua-script",
            script_output_path=output_dir / team_name / "tts" / "cardbox" / "token-bag" / f"{team_name}-token-bag.lua",
            workspace_root=workspace_root,
            branch=branch
        )

    # Build all components (triggers change detection)
    logger.info("Building components...")
    cardbox_content, was_updated = cardbox.build()
    
    if was_updated:
        logger.info("Cardbox was updated")
    else:
        logger.info("Cardbox unchanged")
    
    # Save all component JSONs
    logger.info("Saving component JSONs...")
    team_output = output_dir / team_name / "tts"
    
    # Clean up old TTS directory to remove stale files
    cardbox_dir = team_output / "cardbox"
    if cardbox_dir.exists():
        shutil.rmtree(cardbox_dir, ignore_errors=True)
    
    # Save cardbox container
    cardbox_file = team_output / f"{team_name}-cardbox.json"
    cardbox_file.parent.mkdir(parents=True, exist_ok=True)
    with open(cardbox_file, 'w', encoding='utf-8') as f:
        json.dump(cardbox_content, f, indent=2, ensure_ascii=False)
    
    # Save individual decks and cards
    for deck in all_decks:
        deck_file = team_output / "cardbox" / "decks" / f"{team_name}-{deck.deck_type}.json"
        deck_file.parent.mkdir(parents=True, exist_ok=True)
        if deck._content:
            with open(deck_file, 'w', encoding='utf-8') as f:
                json.dump(deck._content, f, indent=2, ensure_ascii=False)
        
        # Save individual cards in deck
        for card in deck.cards:
            card_dir = team_output / "cardbox" / "decks" / deck.deck_type
            card_dir.mkdir(parents=True, exist_ok=True)
            card_file = card_dir / f"{team_name}-{card.card_name}.json"
            if card._content:
                with open(card_file, 'w', encoding='utf-8') as f:
                    json.dump(card._content, f, indent=2, ensure_ascii=False)
    
    # Save single cards
    for card in single_cards:
        card_file = team_output / "cardbox" / "single-cards" / f"{team_name}-{card.card_type}.json"
        card_file.parent.mkdir(parents=True, exist_ok=True)
        if card._content:
            with open(card_file, 'w', encoding='utf-8') as f:
                json.dump(card._content, f, indent=2, ensure_ascii=False)

    # Save token bag, dispensers, and tokens
    if token_bag and token_bag._content:
        token_bag_file = team_output / "cardbox" / "token-bag" / "token-bag.json"
        token_bag_file.parent.mkdir(parents=True, exist_ok=True)
        with open(token_bag_file, 'w', encoding='utf-8') as f:
            json.dump(token_bag._content, f, indent=2, ensure_ascii=False)

        for dispenser in token_bag.dispensers:
            dispenser_slug = slugify(dispenser.dispenser_name)
            dispenser_file = team_output / "cardbox" / "token-bag" / dispenser_slug / f"{team_name}-{dispenser_slug}.json"
            dispenser_file.parent.mkdir(parents=True, exist_ok=True)
            if dispenser._content:
                with open(dispenser_file, 'w', encoding='utf-8') as f:
                    json.dump(dispenser._content, f, indent=2, ensure_ascii=False)

            if dispenser.token and dispenser.token._content:
                token_slug = slugify(dispenser.token.token_name)
                token_file = dispenser_file.parent / f"{team_name}-{token_slug}-token.json"
                with open(token_file, 'w', encoding='utf-8') as f:
                    json.dump(dispenser.token._content, f, indent=2, ensure_ascii=False)
    
    logger.info("Saved to %s", team_output)
    
    return was_updated


def main():
    parser = argparse.ArgumentParser(description='Generate TTS objects from extracted cards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--force', action='store_true',
                       help='Force regeneration even if unchanged')
    parser.add_argument('--branch', default='main',
                       help='Git branch for GitHub raw URLs (default: main)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level), format='%(levelname)s: %(message)s')

    # Setup paths
    workspace_dir = Path(__file__).parent.parent.parent.parent
    output_dir = workspace_dir / 'output'
    metadata_file = output_dir / '.tts-metadata.json'
    
    # Initialize change detection
    detector = ChangeDetector(metadata_file)
    registry = ComponentRegistry(detector, force_update=args.force)
    
    logger.info("=" * 60)
    logger.info("TTS Object Generation - Warcom Pipeline")
    logger.info("=" * 60)
    
    # Find teams to process
    if args.teams:
        teams = [output_dir / team for team in args.teams if (output_dir / team).exists()]
    else:
        teams = find_all_teams(output_dir)
    
    if not teams:
        logger.warning("No teams found to process")
        return
    
    logger.info("Found %d team(s) to process", len(teams))
    
    # Process each team
    updated_count = 0
    for team_dir in teams:
        try:
            was_updated = generate_team_tts(team_dir, output_dir, registry, args.branch)
            if was_updated:
                updated_count += 1
        except Exception as e:
            logger.error("Error processing %s: %s", team_dir.name, e)
            import traceback
            traceback.print_exc()
            continue
    
    # Save metadata
    detector.save_metadata()
    logger.info("Full metadata saved to %s", metadata_file)
    
    
    # Summary
    logger.info("=" * 60)
    logger.info("Generation Complete")
    logger.info("=" * 60)
    logger.info("Teams processed: %d", len(teams))
    logger.info("Teams updated: %d", updated_count)
    logger.info("Output: %s", output_dir)
    logger.info("Metadata: %s", metadata_file)


if __name__ == '__main__':
    main()
