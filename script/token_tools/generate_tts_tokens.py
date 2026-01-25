"""
Generate TTS token objects from extracted token images.

Creates individual token infinite bags with proper mesh files copied to output.
Each token gets its own .obj mesh file and TTS JSON object.

NOTE: This file was moved from dev/ into the production script package so the
pipeline no longer depends on the dev/ folder.
"""

import argparse
from pathlib import Path
import json
import shutil
import yaml
import hashlib
from typing import Dict, List, Optional

import cv2
import numpy as np
import math


class TTSTokenGenerator:
    """Generate TTS token objects and infinite bags."""

    # Source mesh paths (copied to output_v2 per team for modularity)
    TOKEN_MESH_SOURCE = "config/defaults/tts-token/token-mesh.obj"

    # Important for determinism in Tabletop Simulator: TTS uses pixel-based parameters
    # (e.g. MergeDistancePixels) when generating the cutout mesh. If token images have
    # different resolutions across teams, the effective cutout behavior differs.
    #
    # We therefore package all token PNGs onto a fixed-size transparent canvas.
    # This pads/centers without scaling the artwork.
    TOKEN_CANVAS_PX = 512

    # TTS cutout mesh generation is sensitive to pixel-space parameters.
    # With a 512px canvas, a MergeDistancePixels of ~13 roughly matches the
    # prior behavior seen with ~200px token images at 5px.
    MERGE_DISTANCE_PX = max(5.0, float(int(round(TOKEN_CANVAS_PX / 40))))

    # GitHub repo base URL
    GITHUB_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"

    # Token size in Tabletop Simulator.
    #
    # Scaled to match reference tokens from workshop content:
    # - Round tokens (Writ of Claim): 0.588
    # - Operative tokens (Need Keeps): 0.96
    
    # ====================================================================================
    # IMPORTANT: TTS Auto-Scaling Behavior for Infinite Bags
    # ====================================================================================
    # TTS automatically scales Custom_Model_Infinite_Bag objects proportionally to the
    # token scale inside them. This means:
    #
    # 1. If you change the token scale, the bag will auto-scale by the SAME ratio
    # 2. To keep bags at a fixed size, you must compensate by scaling bags by the INVERSE ratio
    #
    # Formula for compensation when changing token scale:
    #   new_bag_scale = old_bag_scale ├ù (old_token_scale / new_token_scale)
    #
    # Example:
    #   - Original: token=0.651, bag=0.598 (both at correct sizes)
    #   - Change token to: 0.260 (to make tokens 2cm instead of 5cm)
    #   - TTS will auto-scale bag down by: 0.260/0.651 = 0.399x
    #   - To compensate, scale bag up by: 0.651/0.260 = 2.506x
    #   - New bag scale: 0.598 ├ù 2.506 = 1.499 (keeps bag at original 3cm size)
    # ====================================================================================
    
    # Scale values compensating for TTS auto-scaling bags relative to tokens
    # Tokens scaled down to 2cm, bags compensated to stay at 3cm
    # Operative (rectangular) - token at 2cm
    TOKEN_SCALE_OPERATIVE = 0.260  # 0.651 * (2/5)
    BAG_SCALE_OPERATIVE_X = 1.499  # 0.598 * (0.651/0.260) to keep at 3cm
    BAG_SCALE_OPERATIVE_Z = 1.446  # 0.577 * (0.651/0.260)
    # Round (circular) - token at 2cm
    TOKEN_SCALE_ROUND = 0.235  # 0.5301 * (2/4.5)
    BAG_SCALE_ROUND_X = 1.641  # 0.727 * (0.5301/0.235) to keep at 3cm
    BAG_SCALE_ROUND_Z = 1.584  # 0.702 * (0.5301/0.235)

    # Placeholder/infinite-bag mesh visibility:
    # The infinite bag object uses the token image as a diffuse texture on a 3D mesh.
    # If that PNG has transparency, TTS can render the whole placeholder nearly
    # invisible after the texture loads. We therefore generate an *opaque* variant
    # (flattened onto a solid background) for the bag mesh only.
    # NOTE: This background must be bright enough to be visible on dark tables.
    DISPENSER_BG_BGR = (96, 96, 96)
    DISPENSER_BORDER_OUTER_BGR = (245, 245, 245)
    DISPENSER_BORDER_INNER_BGR = (20, 20, 20)
    DISPENSER_BORDER_PX = 10

    # Scale overrides for specific tokens that are physically larger on the battlefield.
    # Format: {team_name: {token_safe_name: scale_multiplier}}
    # Standard tokens are 20mm, scale_multiplier should be actual_mm / 20.0
    TOKEN_SCALE_OVERRIDES = {
        'vespid-stingwings': {
            'skytorch': 28.0 / 20.0,  # 28mm token (1.4x larger than standard 20mm)
        },
    }

    def _copy_token_mesh(self, output_token_dir: Path, team_name: str, faction: str, token_name: str) -> str:
        """Copy token mesh to output_v2/{faction}/{team}/tts/token/ and return URL.
        
        Creates individual mesh file per token for proper dispenser rendering.
        Always overwrites to ensure updates are applied.
        """
        import shutil
        
        source = Path(self.TOKEN_MESH_SOURCE)
        dest = output_token_dir / f"{team_name}-{token_name}.obj"
        
        # Always overwrite to ensure updates are applied
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        
        return f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dest.name}"

    def _flatten_alpha_to_bgr(self, bgra: np.ndarray, *, background_bgr: tuple[int, int, int]) -> np.ndarray:
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            raise ValueError(f"Expected BGRA image, got shape {None if bgra is None else bgra.shape}")
        alpha = (bgra[:, :, 3:4].astype(np.float32) / 255.0)
        src = bgra[:, :, 0:3].astype(np.float32)
        bg = np.array(background_bgr, dtype=np.float32).reshape(1, 1, 3)
        out = (src * alpha) + (bg * (1.0 - alpha))
        return np.clip(out, 0, 255).astype(np.uint8)

    def _add_dispenser_border(self, bgr: np.ndarray) -> np.ndarray:
        if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3:
            raise ValueError(f"Expected BGR image, got shape {None if bgr is None else bgr.shape}")
        h, w = bgr.shape[:2]
        thickness = int(self.DISPENSER_BORDER_PX)
        thickness = max(2, min(thickness, min(h, w) // 10))

        out = bgr.copy()

        # High-contrast frame so the placeholder stays visible even when the
        # token artwork is small or mostly dark.
        cv2.rectangle(out, (0, 0), (w - 1, h - 1), self.DISPENSER_BORDER_OUTER_BGR, thickness=thickness)
        inner_thickness = max(1, thickness // 2)
        cv2.rectangle(
            out,
            (thickness, thickness),
            (w - 1 - thickness, h - 1 - thickness),
            self.DISPENSER_BORDER_INNER_BGR,
            thickness=inner_thickness,
        )
        return out

    def _add_dispenser_border_rgba(self, bgra: np.ndarray) -> np.ndarray:
        """Add dispenser border while preserving alpha channel."""
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            raise ValueError(f"Expected BGRA image, got shape {None if bgra is None else bgra.shape}")
        h, w = bgra.shape[:2]
        thickness = int(self.DISPENSER_BORDER_PX)
        thickness = max(2, min(thickness, min(h, w) // 10))

        out = bgra.copy()

        # High-contrast frame so the placeholder stays visible even when the
        # token artwork is small or mostly dark.
        # Convert BGR colors to BGRA (add full opacity)
        outer_bgra = (*self.DISPENSER_BORDER_OUTER_BGR, 255)
        inner_bgra = (*self.DISPENSER_BORDER_INNER_BGR, 255)
        
        cv2.rectangle(out, (0, 0), (w - 1, h - 1), outer_bgra, thickness=thickness)
        inner_thickness = max(1, thickness // 2)
        cv2.rectangle(
            out,
            (thickness, thickness),
            (w - 1 - thickness, h - 1 - thickness),
            inner_bgra,
            thickness=inner_thickness,
        )
        return out

    def _load_rgba(self, path: Path):
        im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if im is None:
            return None
        if im.ndim == 2:
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
        elif im.shape[2] == 3:
            im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
        elif im.shape[2] == 4:
            # cv2 loads as BGRA already
            pass
        else:
            raise ValueError(f"Unexpected image shape for {path}: {im.shape}")
        return im

    def _crop_transparent_borders(self, bgra):
        """Crop transparent borders from image to ensure consistent token sizes."""
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            return bgra
        
        alpha = bgra[:, :, 3]
        # Find rows and columns with any non-transparent pixels
        rows = np.any(alpha > 0, axis=1)
        cols = np.any(alpha > 0, axis=0)
        
        if not np.any(rows) or not np.any(cols):
            # Completely transparent image
            return bgra
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        # Crop to the bounding box
        cropped = bgra[y_min:y_max+1, x_min:x_max+1]
        return cropped

    def _pad_to_canvas(self, bgra, *, size_px: int):
        # First, resize to fit within target size (with padding margin)
        # Reference tokens fill ~90% of canvas (224/248), so we target ~460px for 512px canvas
        fit_size = int(size_px * 0.9)  # 90% fill matches reference tokens
        h, w = bgra.shape[:2]
        
        # Always resize to fit the target size while preserving aspect ratio
        scale = fit_size / float(max(h, w))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        bgra = cv2.resize(bgra, (new_w, new_h), interpolation=cv2.INTER_AREA)
        h, w = new_h, new_w

        # Now center on the canvas
        canvas = np.zeros((size_px, size_px, 4), dtype=bgra.dtype)

        y0 = (size_px - h) // 2
        x0 = (size_px - w) // 2
        canvas[y0 : y0 + h, x0 : x0 + w] = bgra
        return canvas

    def _infer_shape_from_alpha(self, bgra) -> str | None:
        """Infer token shape from the alpha silhouette.

        This is intentionally conservative: we only return 'round' when the
        silhouette is very clearly circular. Otherwise we return None and keep
        the metadata-provided shape.
        """
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            return None

        alpha = bgra[:, :, 3]
        # Binary mask of non-transparent pixels
        _, mask = cv2.threshold(alpha, 0, 255, cv2.THRESH_BINARY)
        # Smooth small pinholes so circularity isn't destroyed by tiny gaps.
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        c = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(c))
        if area < 200.0:
            return None

        per = float(cv2.arcLength(c, True))
        if per <= 0.0:
            return None

        circularity = (4.0 * math.pi * area) / (per * per)
        x, y, w, h = cv2.boundingRect(c)
        if h <= 0:
            return None
        aspect = float(w) / float(h)

        # Strong classification.
        if circularity >= 0.84 and 0.90 <= aspect <= 1.10:
            return "round"

        return None

    # GitHub repo base URL (from existing project)
    GITHUB_BASE = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main"

    def __init__(self, team_config_path: Path = Path('config/team-config.yaml')):
        self.team_config_path = team_config_path
        self.team_config = self._load_team_config()

    def _load_team_config(self) -> Dict:
        """Load team configuration to get faction information."""
        if not self.team_config_path.exists():
            print(f"Warning: Team config not found: {self.team_config_path}")
            return {}

        with open(self.team_config_path) as f:
            config = yaml.safe_load(f)
            return config.get('teams', {})

    def get_faction(self, team_name: str) -> str:
        """Get faction for a team from config."""
        team_data = self.team_config.get(team_name, {})
        return team_data.get('faction', 'unknown')

    def generate_guid(self, seed: str) -> str:
        """Generate a deterministic 6-character hexadecimal GUID from a seed."""
        return hashlib.md5(seed.encode('utf-8')).hexdigest()[:6]

    def generate_token_object(
        self,
        team_name: str,
        token_name: str,
        token_texture_url: str,
        shape: str = 'operative',
        scale: float | None = None,
    ) -> Dict:
        """Generate a single token object using Custom_Token (2D cutout style)."""
        # Adjust scale based on shape (unless explicitly overridden).
        if scale is None:
            scale = self.TOKEN_SCALE_ROUND if shape == 'round' else self.TOKEN_SCALE_OPERATIVE
        else:
            scale = float(scale)

        # Set tags based on shape
        if shape == 'round':
            tags = ["KTUIMarker", "KTUIToken"]
        else:
            tags = ["KTUIToken", "KTUITokenSimple"]

        return {
            "GUID": self.generate_guid(f"{team_name}:{token_name}:token"),
            "Name": "Custom_Token",
            "Transform": {
                "posX": 0.0,
                "posY": 1.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
                "scaleX": scale,
                "scaleY": 1.0,
                "scaleZ": scale,
            },
            "Nickname": token_name,
            "Description": token_name,
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": tags,
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "IgnoreFoW": False,
            "MeasureMovement": False,
            "DragSelectable": True,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "GridProjection": False,
            "HideWhenFaceDown": False,
            "Hands": False,
            "CustomImage": {
                "ImageURL": token_texture_url,
                "ImageSecondaryURL": "",
                "ImageScalar": 1.0,
                "WidthScale": 0.0,
                "CustomToken": {
                    "Thickness": 0.1,
                    "MergeDistancePixels": self.MERGE_DISTANCE_PX,
                    "StandUp": False,
                    "Stackable": False,
                },
            },
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": "",
        }

    def generate_chip_object(
        self,
        team_name: str,
        token_name: str,
        shape: str = 'operative',
        scale: float | None = None,
    ) -> Dict:
        """Generate a default TTS Chip token when no custom image exists.

        Using a built-in object avoids the white "missing texture" look.
        """
        if scale is None:
            scale = self.TOKEN_SCALE_ROUND if shape == 'round' else self.TOKEN_SCALE_OPERATIVE
        else:
            scale = float(scale)

        if shape == 'round':
            tags = ["KTUIMarker", "KTUIToken"]
        else:
            tags = ["KTUIToken", "KTUITokenSimple"]

        return {
            "GUID": self.generate_guid(f"{team_name}:{token_name}:chip"),
            "Name": "Chip",
            "Transform": {
                "posX": 0.0,
                "posY": 1.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
                "scaleX": scale,
                "scaleY": 1.0,
                "scaleZ": scale,
            },
            "Nickname": token_name,
            "Description": token_name,
            "GMNotes": "",
            "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": tags,
            "LayoutGroupSortIndex": 0,
            "Value": 0,
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "IgnoreFoW": False,
            "MeasureMovement": False,
            "DragSelectable": True,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "GridProjection": False,
            "HideWhenFaceDown": False,
            "Hands": False,
            "LuaScript": "",
            "LuaScriptState": "",
            "XmlUI": "",
        }

    def generate_infinite_bag(
        self,
        team_name: str,
        token_name: str,
        token_obj: Dict,
        token_image_url: str,
        mesh_url: str,
        dispenser_image_url: str = "",
        shape: str = "operative",
    ) -> Dict:
        """Generate an infinite bag using Custom_Model_Infinite_Bag."""
        # Token inside the bag. If the token image is missing, token_obj may be a
        # built-in Chip with no CustomImage.
        contained_token = {
            # IMPORTANT: GUIDs must be unique within a TTS save. When we put multiple
            # infinite bags inside a team bag, reusing a fixed GUID here can cause TTS
            # to drop contents (bags appear empty).
            "GUID": self.generate_guid(f"{team_name}:{token_name}:contained_token"),
            "Name": token_obj.get("Name", "Custom_Token"),
            "Transform": {
                "posX": 0.0,
                "posY": 1.63,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": token_obj['Transform']['scaleX'],
                "scaleY": 1.0,
                "scaleZ": token_obj['Transform']['scaleZ'],
            },
            "Nickname": token_name,
            "Description": token_name,
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": token_obj.get('Tags', []),
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
        }

        if 'CustomImage' in token_obj:
            contained_token["CustomImage"] = token_obj['CustomImage']

        # Create a child object for visual preview on the bag (like in the example)
        child_token = {
            "GUID": self.generate_guid(f"{team_name}:{token_name}:child_preview"),
            "Name": token_obj.get("Name", "Custom_Token"),
            "Transform": {
                "posX": 0.0,
                "posY": 0.0,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 0.0,
                "rotZ": 0.0,
                "scaleX": token_obj['Transform']['scaleX'],
                "scaleY": 1.0,
                "scaleZ": token_obj['Transform']['scaleZ'],
            },
            "Nickname": token_name,
            "Description": token_name,
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": token_obj.get('Tags', []),
            "Locked": True,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
        }

        if 'CustomImage' in token_obj:
            child_token["CustomImage"] = token_obj['CustomImage']

        # Use direct bag scales from manual TTS exports (no multiplication)
        # Bag scales are independent of token scales
        if shape == 'round':
            bag_scale_x = self.BAG_SCALE_ROUND_X
            bag_scale_z = self.BAG_SCALE_ROUND_Z
        else:
            bag_scale_x = self.BAG_SCALE_OPERATIVE_X
            bag_scale_z = self.BAG_SCALE_OPERATIVE_Z

        return {
            "GUID": self.generate_guid(f"{team_name}:{token_name}:infinite_bag"),
            "Name": "Custom_Model_Infinite_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 1.03,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 270.0,
                "rotZ": 0.0,
                "scaleX": bag_scale_x,
                "scaleY": 0.1,
                "scaleZ": bag_scale_z,
            },
            "Nickname": token_name,
            "Description": f"Infinite {token_name} tokens",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": token_obj.get('Tags', []) or ["KTUIToken"],
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
                "CastShadows": True,
            },
            "Bag": {"Order": 0},
            "ContainedObjects": [contained_token],
            "ChildObjects": [child_token],
        }

    def generate_individual_tokens(
        self,
        team_name: str,
        metadata_file: Path,
        token_images_dir: Path,
        output_dir: Path,
        *,
        overwrite_assets: bool = True,
    ) -> List[Dict]:
        """Generate individual token objects with mesh files copied to output."""
        # Load extraction metadata
        with open(metadata_file) as f:
            metadata = json.load(f)

        # Get faction for this team
        faction = self.get_faction(team_name)

        # Create output directories
        output_team_dir = output_dir / faction / team_name
        output_token_dir = output_team_dir / 'tts' / 'token'
        output_token_dir.mkdir(parents=True, exist_ok=True)

        tokens = []

        for token_data in metadata['tokens']:
            filename = token_data['filename']
            token_name = token_data['name']
            shape = token_data['shape']

            # Handle legacy 'complex' shape name
            if shape == 'complex':
                shape = 'operative'

            # Create clean token name for files
            clean_name = filename.replace('.png', '')

            # Create token nickname
            if token_name != 'unknown':
                nickname = token_name
            else:
                nickname = clean_name.replace('-', ' ').title()

            # Copy extracted token image to output as PNG (KEEP TRANSPARENCY!)
            source_image = token_images_dir / team_name / filename
            dest_image = output_token_dir / f"{team_name}-{clean_name}.png"

            is_custom = token_data.get('source') == 'custom'

            padded: np.ndarray | None = None
            if source_image.exists() and (overwrite_assets or not dest_image.exists()):
                src = self._load_rgba(source_image)
                if src is None:
                    raise FileNotFoundError(f"Unable to read token image: {source_image}")
                
                # Custom tokens: keep original size (scale determined by dimensions)
                # Extracted tokens: normalize to 512x512 for consistent TTS cutout
                if is_custom:
                    padded = src  # Keep original dimensions
                else:
                    # Crop transparent borders first for consistent sizing
                    cropped = self._crop_transparent_borders(src)
                    padded = self._pad_to_canvas(cropped, size_px=self.TOKEN_CANVAS_PX)

                # Infer shape from alpha silhouette (keeps metadata as tie-breaker).
                inferred = self._infer_shape_from_alpha(padded)
                if inferred is not None:
                    shape = inferred

            has_image = dest_image.exists()
            if not has_image:
                print(f"Warning: Token image missing for {team_name} / {clean_name}; using default TTS chip")
            else:
                # Even if we are not overwriting the image, we still want consistent
                # shape selection for the generated token/bag JSON.
                existing = self._load_rgba(dest_image) if dest_image.exists() else None
                inferred = self._infer_shape_from_alpha(existing) if existing is not None else None
                if inferred is not None:
                    shape = inferred

            # Write/refresh token image.
            if source_image.exists():
                dest_image.parent.mkdir(parents=True, exist_ok=True)

                if padded is None:
                    # Reuse previously packaged image as the basis for the derived texture.
                    padded = self._load_rgba(dest_image) if dest_image.exists() else None
                    if padded is None:
                        # Last resort: read from source.
                        src = self._load_rgba(source_image)
                        if src is None:
                            raise FileNotFoundError(f"Unable to read token image: {source_image}")
                        # Crop transparent borders first for consistent sizing
                        cropped = self._crop_transparent_borders(src)
                        padded = self._pad_to_canvas(cropped, size_px=self.TOKEN_CANVAS_PX)

                if overwrite_assets or not dest_image.exists():
                    if not cv2.imwrite(str(dest_image), padded):
                        raise IOError(f"Failed to write token image: {dest_image}")

            # Generate URL for texture and mesh (copy mesh to output_v2)
            token_texture_url = (
                f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dest_image.name}"
                if has_image
                else ""
            )
            mesh_url = self._copy_token_mesh(output_token_dir, team_name, faction, clean_name)

            # Create dispenser image (preserve alpha with border for visibility)
            dispenser_image_url = ""
            if has_image:
                dispenser_dest = output_token_dir / f"{team_name}-{clean_name}-dispenser.png"
                if overwrite_assets or not dispenser_dest.exists():
                    # Load the padded token image
                    if padded is None:
                        padded = self._load_rgba(dest_image) if dest_image.exists() else None
                    
                    if padded is not None:
                        # Add visible border frame while preserving alpha channel
                        bgra_with_border = self._add_dispenser_border_rgba(padded)
                        # Save as PNG with alpha
                        if not cv2.imwrite(str(dispenser_dest), bgra_with_border):
                            raise IOError(f"Failed to write dispenser image: {dispenser_dest}")
                
                dispenser_image_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dispenser_dest.name}"

            # Calculate scale for custom tokens based on actual image dimensions
            # Custom tokens are NOT rescaled - their pixel size determines TTS scale
            scale_override = None
            is_custom = token_data.get('source') == 'custom'
            
            if is_custom:
                # For custom tokens, scale is based on actual image size relative to base 512px
                # Larger image = larger in TTS
                token_dimensions = token_data.get('dimensions', {})
                actual_width = token_dimensions.get('width', 512)
                actual_height = token_dimensions.get('height', 512)
                actual_size = (actual_width + actual_height) / 2.0  # Average for non-square images
                
                # Calculate scale multiplier based on size ratio
                size_ratio = actual_size / self.TOKEN_CANVAS_PX
                base_scale = self.TOKEN_SCALE_ROUND if shape == 'round' else self.TOKEN_SCALE_OPERATIVE
                scale_override = base_scale * size_ratio
                print(f"  Γä╣ Custom token scale for {nickname}: {size_ratio:.2f}x (dimensions={actual_width}x{actual_height}, scale={scale_override:.3f})")
            
            # Check for hardcoded scale override (for backwards compatibility)
            elif team_name in self.TOKEN_SCALE_OVERRIDES:
                if clean_name in self.TOKEN_SCALE_OVERRIDES[team_name]:
                    multiplier = self.TOKEN_SCALE_OVERRIDES[team_name][clean_name]
                    base_scale = self.TOKEN_SCALE_ROUND if shape == 'round' else self.TOKEN_SCALE_OPERATIVE
                    scale_override = base_scale * multiplier
                    print(f"  Γä╣ Applying scale override for {nickname}: {multiplier}x (base={base_scale:.3f} ΓåÆ {scale_override:.3f})")

            # Create token object
            if has_image:
                token_obj = self.generate_token_object(
                    team_name=team_name,
                    token_name=nickname,
                    token_texture_url=token_texture_url,
                    shape=shape,
                    scale=scale_override,
                )
            else:
                token_obj = self.generate_chip_object(
                    team_name=team_name,
                    token_name=nickname,
                    shape=shape,
                    scale=scale_override,
                )

            # Create infinite bag containing the token (use same token image, copied mesh)
            bag = self.generate_infinite_bag(
                team_name=team_name,
                token_name=nickname,
                token_obj=token_obj,
                token_image_url=token_texture_url,
                mesh_url=mesh_url,
                dispenser_image_url=dispenser_image_url,
                shape=shape,
            )

            tokens.append(
                {
                    'bag': bag,
                    'token': token_obj,
                    'filename': f"{clean_name}.json",
                    'token_name': nickname,
                    'shape': shape,
                    'image_path': dest_image,
                }
            )

        return tokens


def main():
    parser = argparse.ArgumentParser(description='Generate TTS token objects with mesh files')
    parser.add_argument('--team', type=str, required=True, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument(
        '--metadata',
        type=str,
        default='processed/extracted-tokens/{team}/extraction-metadata.json',
        help='Path to extraction metadata file',
    )
    parser.add_argument(
        '--tokens-dir',
        type=str,
        default='processed/extracted-tokens',
        help='Directory with extracted token images',
    )
    parser.add_argument('--output-dir', type=str, default='output_v2', help='Output directory (default: output_v2)')
    parser.add_argument(
        '--tts-json-dir',
        type=str,
        default='tts_objects/tokens',
        help='Directory for standalone TTS JSON files (temp)',
    )

    args = parser.parse_args()

    tokens_dir = Path(args.tokens_dir)
    output_dir = Path(args.output_dir)
    tts_json_dir = Path(args.tts_json_dir)

    generator = TTSTokenGenerator()

    print(f"\nGenerating TTS tokens for: {args.team}")
    print("=" * 60)

    # Generate token bags
    try:
        metadata_path = Path(args.metadata.replace('{team}', args.team))

        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        # Generate tokens with mesh files copied to output
        tokens_data = generator.generate_individual_tokens(
            team_name=args.team,
            metadata_file=metadata_path,
            token_images_dir=tokens_dir,
            output_dir=output_dir,
            overwrite_assets=True,
        )

        # Get faction for output directory
        faction = generator.get_faction(args.team)
        output_token_dir = output_dir / faction / args.team / 'tts' / 'token'

        # Also save standalone JSON files for testing (temp location)
        team_json_dir = tts_json_dir / args.team
        team_json_dir.mkdir(exist_ok=True, parents=True)

        print(f"\nFaction: {faction}")
        print("Tokens generated:")

        # Save each token bag as standalone JSON
        for token_data in tokens_data:
            # Save to tts_objects for testing
            json_output_file = team_json_dir / token_data['filename']

            # Wrap in TTS save format
            tts_save = {
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
                "ObjectStates": [token_data['bag']],
            }

            with open(json_output_file, 'w') as f:
                json.dump(tts_save, f, indent=2)

            print(f"  Γ£ô {token_data['token_name']} ({token_data['shape']})")

        print(f"\nΓ£ô Generated {len(tokens_data)} token bags")
        print(f"\nOutput locations:")
        print(f"  TTS assets: {output_token_dir.absolute()}")
        print(f"  JSON files: {team_json_dir.absolute()}")

    except Exception as e:
        print(f"\nΓ£ù Error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
