import json
import urllib.request
import os
from collections import defaultdict
from urllib.parse import urlparse

# Read the JSON file
print("Loading dev/examples/3336372255.json...")
with open("dev/examples/3336372255.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

# Create output directory
output_dir = "downloaded_backsides"
os.makedirs(output_dir, exist_ok=True)

# Track unique backsides
backsides_by_team = defaultdict(set)
backside_urls = {}

def extract_backsides_from_object(obj, team_name="Unknown"):
    """Recursively extract backside URLs from object"""
    if isinstance(obj, dict):
        # Check for CustomDeck (deck of cards)
        if "CustomDeck" in obj:
            for deck_id, deck_data in obj["CustomDeck"].items():
                if "BackURL" in deck_data:
                    back_url = deck_data["BackURL"]
                    if back_url and back_url.startswith("http"):
                        backsides_by_team[team_name].add(back_url)
                        backside_urls[back_url] = team_name
        
        # Check for individual card back
        if obj.get("Name") == "Card" or obj.get("Name") == "CardCustom":
            custom_obj = obj.get("CustomDeck", {})
            if custom_obj and isinstance(custom_obj, dict):
                for deck_id, deck_data in custom_obj.items():
                    if "BackURL" in deck_data:
                        back_url = deck_data["BackURL"]
                        if back_url and back_url.startswith("http"):
                            backsides_by_team[team_name].add(back_url)
                            backside_urls[back_url] = team_name
        
        # Check CustomMesh for individual cards
        if "CustomMesh" in obj:
            custom = obj["CustomMesh"]
            if isinstance(custom, dict) and "DiffuseURL" in custom:
                # This might be a card back
                pass
        
        # Recurse into nested objects
        for key, value in obj.items():
            if key == "ContainedObjects":
                nickname = obj.get("Nickname", "Unknown")
                for contained in value:
                    extract_backsides_from_object(contained, nickname)
            elif isinstance(value, (dict, list)):
                extract_backsides_from_object(value, team_name)
    
    elif isinstance(obj, list):
        for item in obj:
            extract_backsides_from_object(item, team_name)

# Find all bags and extract backsides
print("\nExtracting backside URLs from bags...")
for obj in data.get("ObjectStates", []):
    if obj.get("Name") == "Custom_Model_Bag":
        team_name = obj.get("Nickname", "Unknown")
        print(f"\nProcessing bag: {team_name}")
        
        # Check contained objects
        contained = obj.get("ContainedObjects", [])
        for item in contained:
            extract_backsides_from_object(item, team_name)

# Print summary
print("\n" + "="*80)
print(f"Found backsides for {len(backsides_by_team)} teams:")
for team, urls in sorted(backsides_by_team.items()):
    print(f"\n{team}: {len(urls)} unique backside(s)")
    for url in urls:
        print(f"  - {url[:80]}...")

# Download unique backsides
print("\n" + "="*80)
print("Downloading backsides...")
downloaded = []
failed = []

for url, team_name in backside_urls.items():
    safe_team = team_name.replace(" ", "_").replace("/", "-")
    # Create a unique filename based on URL hash
    url_hash = str(hash(url))[-8:]
    filename = f"{safe_team}-backside-{url_hash}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    print(f"\nDownloading: {team_name}")
    print(f"  URL: {url[:80]}...")
    print(f"  Saving to: {filepath}")
    
    try:
        urllib.request.urlretrieve(url, filepath)
        file_size = os.path.getsize(filepath)
        downloaded.append((team_name, filename, file_size))
        print(f"  ✓ Success ({file_size:,} bytes)")
    except Exception as e:
        failed.append((team_name, str(e)))
        print(f"  ✗ Failed: {e}")

# Final summary
print("\n" + "="*80)
print(f"✅ Successfully downloaded {len(downloaded)} backsides")
print(f"❌ Failed to download {len(failed)} backsides")

if downloaded:
    print("\nDownloaded:")
    for team, filename, size in downloaded:
        print(f"  - {team}: {filename} ({size:,} bytes)")

if failed:
    print("\nFailed:")
    for team, error in failed:
        print(f"  - {team}: {error}")

print(f"\nAll backsides saved to: {output_dir}/")
