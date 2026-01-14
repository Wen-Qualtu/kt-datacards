import urllib.request
from pathlib import Path

# Special box mesh used by Wolf Scouts and Battlesuits
SPECIAL_MESH_URL = "https://steamusercontent-a.akamaihd.net/ugc/773992883142220235/B638233F5273FACBDC7483A9A248A0CE01590A71/"

output_dir = Path("config/defaults/box")
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "card-box-4texture.obj"

print(f"Downloading special 4-texture box mesh...")
print(f"URL: {SPECIAL_MESH_URL}")
print(f"Saving to: {output_file}")

try:
    urllib.request.urlretrieve(SPECIAL_MESH_URL, output_file)
    print(f"✅ Successfully downloaded {output_file}")
    print(f"File size: {output_file.stat().st_size:,} bytes")
except Exception as e:
    print(f"❌ Failed to download: {e}")
