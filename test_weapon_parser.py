import re
from typing import Optional, Dict, Any

def _parse_weapon_block(block_text: str) -> Optional[Dict[str, Any]]:
    """Parse a single weapon profile block - TEST VERSION"""
    text = block_text.strip()
    
    print(f"\n{'='*60}")
    print(f"Parsing: {repr(block_text[:100])}")
    print(f"{'='*60}")
    
    # Skip headers
    if any(header in text for header in ['NAME', 'ATK', 'HIT', 'DMG', 'WR']):
        print("SKIP: Header detected")
        return None
    
    # Try multi-line format
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    print(f"Lines ({len(lines)}): {lines[:5]}")
    
    if len(lines) >= 4:
        print("Trying multi-line format...")
        weapon = {}
        weapon["name"] = lines[0]
        print(f"  Name: {weapon['name']}")
        
        if not lines[1].isdigit():
            print(f"  ATK not digit: {repr(lines[1])}")
            return None
        weapon["attacks"] = lines[1]
        print(f"  Attacks: {weapon['attacks']}")
        
        if re.match(r'^\d\+$', lines[2]):
            weapon["hit"] = lines[2]
            print(f"  Hit: {weapon['hit']}")
        
        if re.match(r'^\d+(/\d+)?$', lines[3]):
            weapon["damage"] = lines[3]
            print(f"  Damage: {weapon['damage']}")
        
        if len(lines) > 4:
            special_rules = ' '.join(lines[4:]).strip()
            if special_rules and special_rules != '-':
                weapon["special_rules"] = special_rules
                print(f"  Special: {weapon.get('special_rules', 'None')}")
        
        if "name" in weapon and "attacks" in weapon:
            print(f"✓ SUCCESS: {weapon}")
            return weapon
    
    print("FAILED")
    return None

# Test with actual RATLING BOMBER blocks
test_blocks = [
    """NAME
ATK
HIT DMG
WR""",
    """Explosive arsenal
5
3+
4/5
 Range 3", Blast 1", Heavy (Reposition only), Li""",
    """Sniper rifle (mobile)
4
4+
3/4
-""",
    """Sniper rifle (stationary)
4
3+
3/3
Devastating 3, Heavy"""
]

for block in test_blocks:
    result = _parse_weapon_block(block)
    print(f"\nResult: {result}")
