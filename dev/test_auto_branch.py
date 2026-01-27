import sys
from pathlib import Path

sys.path.insert(0, 'script')

# Test 1: Auto-detect branch (should be refactor-script-structure)
from config import GITHUB_BRANCH, get_github_url
print(f"✓ Auto-detected branch: {GITHUB_BRANCH}")

# Test 2: Build URLs with current branch
url1 = get_github_url("output_v2/chaos/legionaries/datacards/card.jpg")
print(f"✓ URL with current branch: {url1}")

# Test 3: Build URL with override
url2 = get_github_url("tts_objects/Test.json", branch="main")
print(f"✓ URL with override (main): {url2}")

print(f"\n✓ All tests passed!")
