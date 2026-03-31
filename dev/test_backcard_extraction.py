"""Test extraction on LONG-SIGHT back card."""
from pathlib import Path
import importlib.util
import sys

# Load the module
spec = importlib.util.spec_from_file_location("extract_statlines", "pipelines/warcom/steps/6_extract_statlines.py")
module = importlib.util.module_from_spec(spec)
sys.modules["extract_statlines"] = module
spec.loader.exec_module(module)

extract_statlines_from_pdf = module.extract_statlines_from_pdf

back_card = Path("layers/warcom/extracted/farstalker-kinband/cards/farstalker-kinband_page02_card4_landscape.pdf")

print("Extracting from back card...")
data = extract_statlines_from_pdf(back_card)

print(f"\nName: {data.get('name')}")
print(f"APL: {data.get('apl')}")
print(f"Wounds: {data.get('wounds')}")
print(f"Weapons: {len(data.get('weapons', []))} found")
print(f"Unique Actions: {len(data.get('unique_actions', []))} found")

if data.get('unique_actions'):
    for ua in data['unique_actions']:
        print(f"\n  Action: {ua['name']}")
        print(f"  Description: {ua['description'][:100]}...")
