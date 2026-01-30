"""
Generate complete token workflow for Kill Team datacards.

This script handles the full token generation pipeline:
1. Extract tokens from PDFs (if --extract flag)
2. Process tokens (background removal, etc.)
3. Generate TTS token assets (.png, .obj)
4. Generate individual token infinite bags (JSON)
5. Generate master token bag with Lua scripts
6. Embed token bag in card box
7. Update metadata and URLs

Usage:
    python script/generate_team_tokens.py --team murderwings
    python script/generate_team_tokens.py --team murderwings --extract
    python script/generate_team_tokens.py --team murderwings celestian-insidiant
"""

import argparse
import sys
import yaml
from pathlib import Path
import subprocess
import shutil
import json

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))


def load_team_config():
    """Load team configuration"""
    config_path = Path('config/team-config.yaml')
    with open(config_path) as f:
        return yaml.safe_load(f)


def validate_team_config(team_slug, config):
    """Validate team has required configuration"""
    teams = config.get('teams', {})
    
    if team_slug not in teams:
        print(f"❌ Error: Team '{team_slug}' not found in config/team-config.yaml")
        return False
    
    team_data = teams[team_slug]
    
    if not team_data.get('tokens_ready'):
        print(f"⚠️  Warning: Team '{team_slug}' has tokens_ready=false")
        print("   Set tokens_ready: true in config/team-config.yaml when tokens are ready")
        return False
    
    if 'tokens' not in team_data or not team_data['tokens']:
        print(f"❌ Error: Team '{team_slug}' has no tokens defined in config")
        return False
    
    return True


def extract_tokens(team_slug):
    """Extract tokens from PDF (Step 1)"""
    print(f"\n{'='*60}")
    print(f"STEP 1: Extracting tokens from PDF")
    print(f"{'='*60}")
    
    input_pdf = Path(f'input/{team_slug}.pdf')
    if not input_pdf.exists():
        print(f"⚠️  No PDF found at {input_pdf}, skipping extraction")
        return True
    
    cmd = ['poetry', 'run', 'python', 'script/tools/extract_tokens.py', '--team', team_slug]
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ Token extraction failed")
        return False
    
    print("✅ Token extraction complete")
    return True


def process_tokens(team_slug):
    """Process extracted tokens - background removal (Step 2)"""
    print(f"\n{'='*60}")
    print(f"STEP 2: Processing tokens (background removal)")
    print(f"{'='*60}")
    
    # Check if tokens exist in dev/extracted-tokens-pdf/{team}/
    extracted_dir = Path(f'dev/extracted-tokens-pdf/{team_slug}')
    if not extracted_dir.exists() or not list(extracted_dir.glob('*.png')):
        print(f"⚠️  No extracted tokens found in {extracted_dir}, skipping processing")
        return True
    
    cmd = ['poetry', 'run', 'python', 'script/tools/add_token_transparency_bg_sample.py', '--team', team_slug]
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ Token processing failed")
        return False
    
    # Move to processed folder
    processed_dir = Path(f'processed/{team_slug}/token')
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy processed tokens
    for token_file in Path(f'dev/extracted-tokens-pdf/{team_slug}').glob('*.png'):
        dest = processed_dir / token_file.name
        shutil.copy2(token_file, dest)
        print(f"  ✓ Moved {token_file.name} to processed/")
    
    print("✅ Token processing complete")
    return True


def generate_token_assets(team_slug, config):
    """Generate TTS token assets - PNG and OBJ (Step 3)"""
    print(f"\n{'='*60}")
    print(f"STEP 3: Generating TTS token assets")
    print(f"{'='*60}")
    
    teams = config.get('teams', {})
    team_data = teams[team_slug]
    faction = team_data.get('faction', 'unknown')
    tokens = team_data.get('tokens', [])
    
    # Ensure output directory structure
    output_dir = Path(f'output_v2/{faction}/{team_slug}/tts/token')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processed_dir = Path(f'processed/{team_slug}/token')
    if not processed_dir.exists():
        print(f"❌ Error: No processed tokens found at {processed_dir}")
        return False
    
    # Copy/generate assets for each token
    template_obj = Path('output_v2/chaos/blooded/tts/token/blooded-scavenged.obj')
    if not template_obj.exists():
        print(f"❌ Error: Template OBJ file not found: {template_obj}")
        return False
    
    for token in tokens:
        token_name = token['name']
        token_slug = token_name.lower().replace(' ', '-')
        
        # Source PNG from processed
        src_png = processed_dir / f'{token_slug}.png'
        if not src_png.exists():
            print(f"⚠️  Warning: Token PNG not found: {src_png}")
            continue
        
        # Copy PNG with team prefix
        dest_png = output_dir / f'{team_slug}-{token_slug}.png'
        shutil.copy2(src_png, dest_png)
        print(f"  ✓ Created {dest_png.name}")
        
        # Copy OBJ with team prefix
        dest_obj = output_dir / f'{team_slug}-{token_slug}.obj'
        shutil.copy2(template_obj, dest_obj)
        print(f"  ✓ Created {dest_obj.name}")
    
    print("✅ Token assets generated")
    return True


def generate_individual_token_bags(team_slug, config):
    """Generate individual token infinite bag JSONs (Step 4)"""
    print(f"\n{'='*60}")
    print(f"STEP 4: Generating individual token infinite bags")
    print(f"{'='*60}")
    
    # Call the script as subprocess
    cmd = ['poetry', 'run', 'python', 'script/src/token_tools/generate_tts_tokens.py', '--team', team_slug]
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ Individual token bag generation failed")
        return False
    
    print("✅ Individual token bags generated")
    return True


def generate_master_token_bag(team_slug, config):
    """Generate master token bag with Lua scripts (Step 5)"""
    print(f"\n{'='*60}")
    print(f"STEP 5: Generating master token bag")
    print(f"{'='*60}")
    
    # Call the script as subprocess
    cmd = ['poetry', 'run', 'python', 'script/src/token_tools/generate_team_token_bag.py', '--team', team_slug]
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ Master token bag generation failed")
        return False
    
    teams = config.get('teams', {})
    team_data = teams[team_slug]
    faction = team_data.get('faction', 'unknown')
    
    # Copy to tts_objects for metadata generation
    output_path = Path(f'output_v2/{faction}/{team_slug}/tts/token/{team_slug}-tokens.json')
    if not output_path.exists():
        print(f"❌ Master token bag not found at {output_path}")
        return False
    
    tokens_dir = Path(f'tts_objects/{team_slug}/tokens')
    tokens_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = tokens_dir / f'{team_slug}-tokenbag.json'
    shutil.copy2(output_path, dest_path)
    print(f"  ✓ Copied tokenbag to {dest_path}")
    
    print("✅ Master token bag generated")
    return True


def embed_token_bag_in_box(team_slug, config):
    """Embed token bag in card box (Step 6)"""
    print(f"\n{'='*60}")
    print(f"STEP 6: Embedding token bag in card box")
    print(f"{'='*60}")
    
    teams = config.get('teams', {})
    team_data = teams[team_slug]
    faction = team_data.get('faction', 'unknown')
    
    # Find card box file
    team_display = team_slug.replace('-', ' ').title()
    box_file = Path(f'tts_objects/{team_slug}/{team_display} Cards.json')
    
    if not box_file.exists():
        print(f"❌ Error: Card box not found at {box_file}")
        return False
    
    # Find token bag file
    token_bag_file = Path(f'output_v2/{faction}/{team_slug}/tts/token/{team_slug}-tokens.json')
    
    if not token_bag_file.exists():
        print(f"❌ Error: Token bag not found at {token_bag_file}")
        return False
    
    # Load and merge
    with open(box_file) as f:
        box_data = json.load(f)
    
    with open(token_bag_file) as f:
        token_bag_data = json.load(f)
    
    # Get objects
    token_bag_obj = token_bag_data['ObjectStates'][0]
    box_obj = box_data['ObjectStates'][0]
    
    # Check if ContainedObjects exists
    if 'ContainedObjects' not in box_obj:
        box_obj['ContainedObjects'] = []
    
    # Remove existing token bag if present
    token_bag_name = token_bag_obj.get('Nickname', '')
    box_obj['ContainedObjects'] = [
        obj for obj in box_obj['ContainedObjects']
        if obj.get('Nickname', '') != token_bag_name
    ]
    
    # Add new token bag
    box_obj['ContainedObjects'].append(token_bag_obj)
    print(f"  ✓ Added token bag to card box")
    
    # Update LuaScriptState
    lua_state = box_obj.get('LuaScriptState', '')
    if lua_state:
        try:
            state_data = json.loads(lua_state)
        except Exception:
            state_data = {"ml": {}, "rr": 270}
    else:
        state_data = {"ml": {}, "rr": 270}
    
    token_bag_guid = token_bag_obj.get('GUID', 'unknown')
    state_data['ml'][token_bag_guid] = {
        "lock": False,
        "pos": {"x": 5.5, "y": -2.46, "z": -8.5},
        "rot": {"x": 0.0169, "y": 269.9995, "z": 0.0799},
    }
    
    box_obj['LuaScriptState'] = json.dumps(state_data)
    print(f"  ✓ Updated LuaScriptState")
    
    # Save
    with open(box_file, 'w') as f:
        json.dump(box_data, f, indent=2)
    
    print(f"✅ Token bag embedded (total objects: {len(box_obj['ContainedObjects'])})")
    return True


def update_metadata_and_urls(team_slugs):
    """Update TTS metadata and URLs (Step 7)"""
    print(f"\n{'='*60}")
    print(f"STEP 7: Updating metadata and URLs")
    print(f"{'='*60}")
    
    # Generate metadata
    print("\nGenerating TTS metadata...")
    cmd = ['poetry', 'run', 'python', 'script/generate_tts_metadata.py']
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ Metadata generation failed")
        return False
    
    # Generate URLs
    print("\nGenerating URLs...")
    cmd = ['poetry', 'run', 'python', 'script/generate_urls.py']
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print("❌ URL generation failed")
        return False
    
    print("✅ Metadata and URLs updated")
    return True


def process_team(team_slug, config, extract=False):
    """Process complete token workflow for a team"""
    print(f"\n{'#'*60}")
    print(f"# Processing tokens for: {team_slug}")
    print(f"{'#'*60}")
    
    # Validate configuration
    if not validate_team_config(team_slug, config):
        return False
    
    # Step 1: Extract (optional)
    if extract:
        if not extract_tokens(team_slug):
            return False
        if not process_tokens(team_slug):
            return False
    
    # Step 3: Generate assets
    if not generate_token_assets(team_slug, config):
        return False
    
    # Step 4: Individual token bags
    if not generate_individual_token_bags(team_slug, config):
        return False
    
    # Step 5: Master token bag
    if not generate_master_token_bag(team_slug, config):
        return False
    
    # Step 6: Embed in card box
    if not embed_token_bag_in_box(team_slug, config):
        return False
    
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Generate complete token workflow for Kill Team datacards',
        epilog='Examples:\n'
               '  python script/generate_team_tokens.py --team murderwings\n'
               '  python script/generate_team_tokens.py --team murderwings --extract\n'
               '  python script/generate_team_tokens.py --team murderwings celestian-insidiant',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--team',
        nargs='+',
        required=True,
        help='Team slug(s) to process (e.g., murderwings celestian-insidiant)'
    )
    parser.add_argument(
        '--extract',
        action='store_true',
        help='Extract tokens from PDF before processing'
    )
    
    args = parser.parse_args()
    
    # Load config
    config = load_team_config()
    
    # Process each team
    failed_teams = []
    successful_teams = []
    
    for team_slug in args.team:
        if process_team(team_slug, config, extract=args.extract):
            successful_teams.append(team_slug)
        else:
            failed_teams.append(team_slug)
    
    # Step 7: Update metadata and URLs (once for all teams)
    if successful_teams:
        update_metadata_and_urls(successful_teams)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    if successful_teams:
        print(f"✅ Successfully processed: {', '.join(successful_teams)}")
    
    if failed_teams:
        print(f"❌ Failed: {', '.join(failed_teams)}")
        sys.exit(1)
    
    print("\n✅ Token generation complete!")


if __name__ == '__main__':
    main()
