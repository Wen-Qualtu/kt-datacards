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

    # Bag mesh template path
    BAG_MESH_TEMPLATE = Path('config/defaults/tts-token/token-mesh.obj')

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

    # Token size in Tabletop Simulator.
    #
    # The previous values (round=0.228, operative=0.24) spawn noticeably small
    # tokens in TTS; users commonly "Reset Scale" to get expected sizing.
    # Increasing by ~4x makes tokens spawn at the intended tabletop size.
    TOKEN_SCALE_ROUND = 0.228 * 4.0
    TOKEN_SCALE_OPERATIVE = 0.24 * 4.0

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

    def _pad_to_canvas(self, bgra, *, size_px: int):
        h, w = bgra.shape[:2]
        if h > size_px or w > size_px:
            # Scale down to fit the canvas while preserving aspect ratio.
            scale = size_px / float(max(h, w))
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
            bgra = cv2.resize(bgra, (new_w, new_h), interpolation=cv2.INTER_AREA)
            h, w = bgra.shape[:2]

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

    def generate_infinite_bag(
        self,
        team_name: str,
        token_name: str,
        token_obj: Dict,
        token_image_url: str,
        mesh_url: str,
    ) -> Dict:
        """Generate an infinite bag using Custom_Model_Infinite_Bag."""
        # Contained token (visible on the bag)
        contained_token = {
            "GUID": "53bd29",
            "Name": "Custom_Token",
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
            "CustomImage": token_obj['CustomImage'],
        }

        # Child token template (what spawns)
        child_token_template = {
            "GUID": "333a8b",
            "Name": "Custom_Token",
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
            "Description": "",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0},
            "Tags": token_obj.get('Tags', []),
            "Locked": False,
            "Grid": True,
            "Snap": False,
            "Autoraise": True,
            "Sticky": False,
            "Tooltip": False,
            "Hands": False,
            "CustomImage": token_obj['CustomImage'],
        }

        return {
            "GUID": self.generate_guid(f"{team_name}:{token_name}:infinite_bag"),
            "Name": "Custom_Model_Infinite_Bag",
            "Transform": {
                "posX": 0.0,
                "posY": 1.03,
                "posZ": 0.0,
                "rotX": 0.0,
                "rotY": 180.0,
                "rotZ": 0.0,
                "scaleX": 1.17,
                "scaleY": 0.1,
                "scaleZ": 1.13,
            },
            "Nickname": token_name,
            "Description": f"Infinite {token_name} tokens",
            "ColorDiffuse": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
            "Tags": ["KTUIToken"],
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
            "ContainedObjects": [contained_token],
            "ChildObjects": [child_token_template],
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

            if source_image.exists() and (overwrite_assets or not dest_image.exists()):
                # Normalize image canvas size for consistent TTS cutout behavior.
                src = self._load_rgba(source_image)
                if src is None:
                    raise FileNotFoundError(f"Unable to read token image: {source_image}")
                padded = self._pad_to_canvas(src, size_px=self.TOKEN_CANVAS_PX)

                # Infer shape from alpha silhouette (keeps metadata as tie-breaker).
                inferred = self._infer_shape_from_alpha(padded)
                if inferred is not None:
                    shape = inferred

                dest_image.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(dest_image), padded):
                    raise IOError(f"Failed to write token image: {dest_image}")
            else:
                # Even if we are not overwriting the image, we still want consistent
                # shape selection for the generated token/bag JSON.
                existing = self._load_rgba(dest_image) if dest_image.exists() else None
                inferred = self._infer_shape_from_alpha(existing) if existing is not None else None
                if inferred is not None:
                    shape = inferred

            # Copy bag mesh to output with token-specific name
            mesh_dest = output_token_dir / f"{team_name}-{clean_name}.obj"
            if self.BAG_MESH_TEMPLATE.exists() and (overwrite_assets or not mesh_dest.exists()):
                shutil.copy2(self.BAG_MESH_TEMPLATE, mesh_dest)

            # Generate URLs for texture and mesh
            texture_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{dest_image.name}"
            mesh_url = f"{self.GITHUB_BASE}/output_v2/{faction}/{team_name}/tts/token/{mesh_dest.name}"

            # Create token object
            token_obj = self.generate_token_object(
                team_name=team_name,
                token_name=nickname,
                token_texture_url=texture_url,
                shape=shape,
            )

            # Create infinite bag containing the token
            bag = self.generate_infinite_bag(
                team_name=team_name,
                token_name=nickname,
                token_obj=token_obj,
                token_image_url=texture_url,
                mesh_url=mesh_url,
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

            print(f"  ✓ {token_data['token_name']} ({token_data['shape']})")

        print(f"\n✓ Generated {len(tokens_data)} token bags")
        print(f"\nOutput locations:")
        print(f"  TTS assets: {output_token_dir.absolute()}")
        print(f"  JSON files: {team_json_dir.absolute()}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()
