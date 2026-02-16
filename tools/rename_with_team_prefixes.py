#!/usr/bin/env python3
"""
One-off script to rename existing files with team prefixes.
Handles:
- layers/warcom/extracted/{team}/tokens/*.png -> {team}_*.png
- layers/warcom/extracted/{team}/tokens/tokens_metadata.json -> {team}_tokens_metadata.json
- Update JSON content to match new filenames
- output/{team}/tokens/*.png -> {team}-*.png
- output/{team}/tts/cardbox.json -> {team}-cardbox.json
- output/{team}/tts/cardbox/token-bag/token-bag.json -> {team}-token-bag.json
- output/{team}/tts/cardbox/token-bag/token-bag.lua -> {team}-token-bag.lua
- output/{team}/tts/cardbox/lua-script.lua -> {team}-lua-script.lua
"""

import json
import shutil
from pathlib import Path

def rename_step2_tokens(extracted_dir: Path):
    """Rename Step 2 extracted tokens and metadata."""
    print("\n=== Step 2: Renaming extracted tokens ===")
    
    for team_dir in sorted(extracted_dir.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_slug = team_dir.name
        tokens_dir = team_dir / "tokens"
        
        if not tokens_dir.exists():
            continue
        
        print(f"\n{team_slug}:")
        
        # Rename metadata JSON file
        old_metadata = tokens_dir / "tokens_metadata.json"
        if old_metadata.exists():
            new_metadata = tokens_dir / f"{team_slug}_tokens_metadata.json"
            
            # Load, update content, save to new location
            with open(old_metadata, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Update filenames in metadata
            for token in metadata.get('tokens', []):
                old_filename = token['filename']
                if not old_filename.startswith(f"{team_slug}_"):
                    token['filename'] = f"{team_slug}_{old_filename}"
            
            # Save to new file
            with open(new_metadata, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # Remove old file
            old_metadata.unlink()
            print(f"  ✓ Renamed metadata: tokens_metadata.json -> {team_slug}_tokens_metadata.json")
        
        # Rename token PNG files
        token_count = 0
        for token_file in sorted(tokens_dir.glob("*.png")):
            old_name = token_file.name
            if not old_name.startswith(f"{team_slug}_"):
                new_name = f"{team_slug}_{old_name}"
                new_path = tokens_dir / new_name
                token_file.rename(new_path)
                token_count += 1
        
        if token_count > 0:
            print(f"  ✓ Renamed {token_count} token PNG files")


def rename_step4_tokens(output_dir: Path):
    """Rename Step 4 processed tokens."""
    print("\n=== Step 4: Renaming processed tokens ===")
    
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir() or team_dir.name.startswith('.'):
            continue
        
        team_slug = team_dir.name
        tokens_dir = team_dir / "tokens"
        
        if not tokens_dir.exists():
            continue
        
        print(f"\n{team_slug}:")
        
        # Rename token PNG files
        token_count = 0
        for token_file in sorted(tokens_dir.glob("*.png")):
            old_name = token_file.name
            if not old_name.startswith(f"{team_slug}-"):
                new_name = f"{team_slug}-{old_name}"
                new_path = tokens_dir / new_name
                token_file.rename(new_path)
                token_count += 1
        
        if token_count > 0:
            print(f"  ✓ Renamed {token_count} token PNG files")


def rename_step5_tts_files(output_dir: Path):
    """Rename Step 5 TTS output files."""
    print("\n=== Step 5: Renaming TTS files ===")
    
    for team_dir in sorted(output_dir.iterdir()):
        if not team_dir.is_dir() or team_dir.name.startswith('.'):
            continue
        
        team_slug = team_dir.name
        tts_dir = team_dir / "tts"
        
        if not tts_dir.exists():
            continue
        
        print(f"\n{team_slug}:")
        renamed = []
        
        # Rename cardbox.json
        old_cardbox = tts_dir / "cardbox.json"
        if old_cardbox.exists():
            new_cardbox = tts_dir / f"{team_slug}-cardbox.json"
            old_cardbox.rename(new_cardbox)
            renamed.append("cardbox.json")
        
        # Rename lua-script.lua in cardbox/
        old_lua = tts_dir / "cardbox" / "lua-script.lua"
        if old_lua.exists():
            new_lua = tts_dir / "cardbox" / f"{team_slug}-lua-script.lua"
            old_lua.rename(new_lua)
            renamed.append("lua-script.lua")
        
        # Rename token-bag files
        token_bag_dir = tts_dir / "cardbox" / "token-bag"
        if token_bag_dir.exists():
            old_tb_json = token_bag_dir / "token-bag.json"
            if old_tb_json.exists():
                new_tb_json = token_bag_dir / f"{team_slug}-token-bag.json"
                old_tb_json.rename(new_tb_json)
                renamed.append("token-bag.json")
            
            old_tb_lua = token_bag_dir / "token-bag.lua"
            if old_tb_lua.exists():
                new_tb_lua = token_bag_dir / f"{team_slug}-token-bag.lua"
                old_tb_lua.rename(new_tb_lua)
                renamed.append("token-bag.lua")
        
        if renamed:
            print(f"  ✓ Renamed: {', '.join(renamed)}")


def main():
    print("=" * 70)
    print("Renaming files with team prefixes")
    print("=" * 70)
    
    extracted_dir = Path("layers/warcom/extracted")
    output_dir = Path("output")
    
    if extracted_dir.exists():
        rename_step2_tokens(extracted_dir)
    else:
        print(f"\n⚠ Directory not found: {extracted_dir}")
    
    if output_dir.exists():
        rename_step4_tokens(output_dir)
        rename_step5_tts_files(output_dir)
    else:
        print(f"\n⚠ Directory not found: {output_dir}")
    
    print("\n" + "=" * 70)
    print("✓ All files renamed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
