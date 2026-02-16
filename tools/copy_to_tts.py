"""
Copy TTS objects to Tabletop Simulator Saved Objects folder.

This script copies generated TTS cardbox files and their supporting folders
to the Tabletop Simulator Saved Objects directory for testing.
"""

import argparse
import shutil
from pathlib import Path


def copy_tts_objects(output_dir: Path, tts_saves_dir: Path, teams: list[str] | None = None, copy_subfolders: bool = False):
    """
    Copy TTS objects to Tabletop Simulator saves folder.
    
    Args:
        output_dir: Path to the output directory containing team folders
        tts_saves_dir: Path to TTS Saved Objects directory
        teams: Optional list of specific teams to copy (default: all)
        copy_subfolders: If True, also copy cardbox subfolders (default: False for speed)
    """
    if not output_dir.exists():
        print(f"Error: Output directory not found: {output_dir}")
        return False
    
    if not tts_saves_dir.exists():
        print(f"Creating TTS saves directory: {tts_saves_dir}")
        tts_saves_dir.mkdir(parents=True, exist_ok=True)
    
    # Find all teams with TTS output
    if teams:
        team_dirs = [output_dir / team for team in teams if (output_dir / team / "tts").exists()]
    else:
        team_dirs = [d for d in output_dir.iterdir() if d.is_dir() and (d / "tts").exists()]
    
    if not team_dirs:
        print("No teams with TTS output found")
        return False
    
    print(f"Found {len(team_dirs)} team(s) to copy")
    copied_count = 0
    
    for team_dir in team_dirs:
        team_name = team_dir.name
        tts_dir = team_dir / "tts"
        
        # Copy main cardbox JSON file
        cardbox_file = tts_dir / f"{team_name}-cardbox.json"
        if cardbox_file.exists():
            dest_file = tts_saves_dir / f"{team_name}-cardbox.json"
            shutil.copy2(cardbox_file, dest_file)
            print(f"✓ Copied {team_name}-cardbox.json")
        else:
            print(f"⚠ Missing cardbox file for {team_name}")
            continue
        
        # Optionally copy cardbox folder (contains decks, single-cards, token-bag, etc.)
        if copy_subfolders:
            cardbox_dir = tts_dir / "cardbox"
            if cardbox_dir.exists():
                dest_dir = tts_saves_dir / team_name
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                shutil.copytree(cardbox_dir, dest_dir)
                print(f"  + Copied {team_name}/cardbox folder")
            else:
                print(f"  ⚠ Missing cardbox folder for {team_name}")
        
        copied_count += 1
    
    print(f"\n✓ Successfully copied {copied_count} team(s) to {tts_saves_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Copy TTS objects to Tabletop Simulator Saved Objects folder'
    )
    parser.add_argument(
        '--teams',
        nargs='+',
        help='Specific teams to copy (default: all)'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Copy cardbox subfolders in addition to main JSON files (slower)'
    )
    parser.add_argument(
        '--tts-dir',
        type=Path,
        default=Path(r"C:\Users\Jesse\OneDrive\Documents\My Games\Tabletop Simulator\Saves\Saved Objects\_KT-cards new"),
        help='Path to TTS Saved Objects directory'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path.cwd() / 'output',
        help='Path to output directory (default: ./output)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Copy TTS Objects to Tabletop Simulator")
    print("=" * 60)
    print(f"Source: {args.output_dir}")
    print(f"Destination: {args.tts_dir}")
    print(f"Mode: {'Full (with subfolders)' if args.full else 'Fast (cardbox JSON only)'}")
    print()
    
    success = copy_tts_objects(args.output_dir, args.tts_dir, args.teams, args.full)
    
    if not success:
        exit(1)


if __name__ == '__main__':
    main()
