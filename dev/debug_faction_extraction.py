"""
Debug script to diagnose faction rule extraction issues.

Reads the OLD TTS JSON file and checks for faction rule markers in card LuaScripts.
"""

import json
from pathlib import Path

# Define paths
PROJECT_ROOT = Path(__file__).parent.parent
TTS_FILE = PROJECT_ROOT / "tts_objects" / "angels-of-death" / "Angels Of Death Cards.json"

# Markers to search for
START_MARKER = "-- ===== FACTION RULE:"
END_MARKER = "-- ===== END FACTION RULE ====="

def main():
    print(f"Debugging faction rule extraction")
    print(f"=" * 80)
    print(f"File: {TTS_FILE}")
    print(f"Exists: {TTS_FILE.exists()}")
    print()
    
    if not TTS_FILE.exists():
        print("ERROR: File does not exist!")
        return
    
    # Load the JSON
    with open(TTS_FILE, 'r', encoding='utf-8') as f:
        tts_data = json.load(f)
    
    print(f"Top-level keys: {list(tts_data.keys())}")
    print()
    
    # Check ObjectStates
    object_states = tts_data.get("ObjectStates", [])
    print(f"Number of ObjectStates: {len(object_states)}")
    print()
    
    # Iterate through ObjectStates
    for i, obj in enumerate(object_states):
        obj_name = obj.get("Name", "Unknown")
        print(f"ObjectState [{i}]:")
        print(f"  Name: {obj_name}")
        print(f"  Keys: {list(obj.keys())}")
        
        # Look for Custom_Model_Bag
        if obj_name == "Custom_Model_Bag":
            print(f"  ✓ Found Custom_Model_Bag")
            contained = obj.get("ContainedObjects", [])
            print(f"  ContainedObjects count: {len(contained)}")
            print()
            
            # Check each card in ContainedObjects
            cards_with_lua = 0
            cards_with_start = 0
            cards_with_end = 0
            cards_with_both = 0
            
            for j, card in enumerate(contained):
                card_nickname = card.get("Nickname", "No Nickname")
                card_name = card.get("Name", "Unknown")
                has_lua = "LuaScript" in card
                lua_script = card.get("LuaScript", "")
                lua_length = len(lua_script)
                
                has_start = START_MARKER in lua_script
                has_end = END_MARKER in lua_script
                
                if has_lua:
                    cards_with_lua += 1
                if has_start:
                    cards_with_start += 1
                if has_end:
                    cards_with_end += 1
                if has_start and has_end:
                    cards_with_both += 1
                
                # Print details for all top-level cards
                print(f"  Card [{j}]: {card_nickname}")
                print(f"    Name: {card_name}")
                print(f"    Has LuaScript: {has_lua}")
                print(f"    LuaScript length: {lua_length}")
                print(f"    Contains START_MARKER: {has_start}")
                print(f"    Contains END_MARKER: {has_end}")
                
                # Check if this is a Deck with nested cards
                if card_name == "Deck" and "ContainedObjects" in card:
                    nested_cards = card.get("ContainedObjects", [])
                    print(f"    ↳ This is a Deck with {len(nested_cards)} nested cards")
                    
                    # Check nested cards for faction rules
                    for k, nested_card in enumerate(nested_cards):
                        nested_nickname = nested_card.get("Nickname", "No Nickname")
                        nested_lua = nested_card.get("LuaScript", "")
                        nested_lua_length = len(nested_lua)
                        nested_has_start = START_MARKER in nested_lua
                        nested_has_end = END_MARKER in nested_lua
                        
                        # Show info for first 3 nested cards or any with markers
                        if k < 3 or nested_has_start or nested_has_end:
                            print(f"      Nested [{k}]: {nested_nickname}")
                            print(f"        LuaScript length: {nested_lua_length}")
                            print(f"        Has START: {nested_has_start}, Has END: {nested_has_end}")
                            
                            if nested_has_start and nested_has_end:
                                # Extract and show the faction rule block
                                start_idx = nested_lua.find(START_MARKER)
                                end_idx = nested_lua.find(END_MARKER) + len(END_MARKER)
                                faction_rule_code = nested_lua[start_idx:end_idx]
                                
                                print(f"        ✓✓ FOUND FACTION RULE BLOCK IN NESTED CARD!")
                                print(f"        Block length: {len(faction_rule_code)}")
                                print(f"        First 200 chars:")
                                print(f"        {'-' * 60}")
                                print(f"        {faction_rule_code[:200]}")
                                print(f"        {'-' * 60}")
                                cards_with_both += 1
                    
                    if len(nested_cards) > 3:
                        print(f"      ... ({len(nested_cards) - 3} more nested cards)")
                
                if has_start and has_end:
                    # Extract and show the faction rule block
                    start_idx = lua_script.find(START_MARKER)
                    end_idx = lua_script.find(END_MARKER) + len(END_MARKER)
                    faction_rule_code = lua_script[start_idx:end_idx]
                    
                    print(f"    ✓✓ FOUND FACTION RULE BLOCK!")
                    print(f"    Block length: {len(faction_rule_code)}")
                    print(f"    First 200 chars:")
                    print(f"    {'-' * 60}")
                    print(f"    {faction_rule_code[:200]}")
                    print(f"    {'-' * 60}")
                print()
            
            # Summary
            print(f"Summary:")
            print(f"  Total top-level cards: {len(contained)}")
            print(f"  Cards with LuaScript: {cards_with_lua}")
            print(f"  Cards with START marker: {cards_with_start}")
            print(f"  Cards with END marker: {cards_with_end}")
            print(f"  Cards with BOTH markers (including nested): {cards_with_both}")
            print()
        else:
            print(f"  (Not a Custom_Model_Bag, skipping)")
        print()

if __name__ == "__main__":
    main()
