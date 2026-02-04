"""
Test icon extraction on Angels of Death team.
"""
from pathlib import Path
import importlib.util

# Load the module directly from file
spec = importlib.util.spec_from_file_location("step2", "pipelines/warcom/steps/2_card_extractor.py")
step2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step2)

# Test on Angels of Death
pdf_path = Path('layers/archive/angels-of-death/warcom/eng_28-01_kill_team_team_rules_angels_of_death-g1xsdrmgpd-t1j6hagnfi.pdf')
output_dir = Path('dev/test_icons_output')
team_name = 'angels-of-death'

print("=" * 60)
print("Testing Icon Extraction")
print("=" * 60)
print(f"PDF: {pdf_path.name}")
print(f"Team: {team_name}")
print(f"Output: {output_dir}")
print()

if not pdf_path.exists():
    print(f"ERROR: PDF not found: {pdf_path}")
    exit(1)

result = step2.extract_icons_from_pdf(pdf_path, output_dir, team_name)

print("Results:")
print(f"  Portrait icon: {'✓' if result['portrait'] else '✗'}")
print(f"  Landscape icon: {'✓' if result['landscape'] else '✗'}")
print(f"  Token bag icon: {'✓' if result['token'] else '✗'}")
print()

icons_dir = output_dir / 'icons'
if icons_dir.exists():
    icons = list(icons_dir.glob('*.jpg'))
    print(f"Extracted {len(icons)} icons:")
    for icon in icons:
        print(f"  - {icon.name}")

print()
print("=" * 60)
