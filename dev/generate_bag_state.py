"""Generate LuaScriptState for Farstalker bag with all 8 objects in a 2x5 grid"""
import json
from pathlib import Path

# Map objects to their grid positions (1-10)
# Grid layout:
# 1      2      3      4      5
# 6      7      8      9      10
#
# 1 = faction rule (farstalker-kinband-farstalker)
# 2 = operative selection (farstalker-kinband-operatives)
# 3 = empty
# 4 = empty
# 5 = datacards
# 6 = strategy ploys
# 7 = firefight ploys
# 8 = marker/token guide
# 9 = empty
# 10 = token bag (rotated 90° left)

grid_mapping = {
    "12de03": 1,   # farstalker (faction rule)
    "526598": 2,   # operatives
    "859f19": 5,   # datacards
    "16200c": 6,   # strategy ploys
    "62a680": 7,   # firefight ploys
    "d97f5e": 8,   # markertoken-guide
    "4391e7": 10,  # token bag
    "eca877": 3    # equipment (putting in position 3)
}

# Create 2x5 grid positions with proper spacing
# Row 1: Z = -4, positions X = [-4, -2, 0, 2, 4]
# Row 2: Z = -8, positions X = [-4, -2, 0, 2, 4]
grid_positions = {
    1: {"x": -4.0, "z": -4.0},
    2: {"x": -2.0, "z": -4.0},
    3: {"x": 0.0, "z": -4.0},
    4: {"x": 2.0, "z": -4.0},
    5: {"x": 4.0, "z": -4.0},
    6: {"x": -4.0, "z": -8.0},
    7: {"x": -2.0, "z": -8.0},
    8: {"x": 0.0, "z": -8.0},
    9: {"x": 2.0, "z": -8.0},
    10: {"x": 4.0, "z": -8.0}
}

# Create memory list entries
memory_list = {}
for guid, pos_num in grid_mapping.items():
    pos = grid_positions[pos_num]
    # Token bag gets rotated 90° to the left (Y = 270)
    rotation_y = 269.9995 if guid == "4391e7" else 179.9995
    
    memory_list[guid] = {
        "lock": False,
        "pos": {"x": pos["x"], "y": -2.486, "z": pos["z"]},
        "rot": {"x": 0.0169, "y": rotation_y, "z": 0.0799}
    }

# Create the Lua state structure
lua_state = {
    "ml": memory_list,
    "rr": 270  # relative rotation
}

# Convert to JSON string (this is what goes in LuaScriptState)
lua_state_json = json.dumps(lua_state, separators=(',', ': '))

print("Generated LuaScriptState for 2x5 grid:")
print(f"  8 objects placed in positions: {sorted(grid_mapping.values())}")
print(f"  Token bag at position 10 (rotated 90° left)")

# Now update the Farstalker TTS object
farstalker_path = Path("tts_objects/Farstalker Kinband Cards.json")
with open(farstalker_path, 'r', encoding='utf-8') as f:
    tts_data = json.load(f)

# Update the LuaScriptState
tts_data['ObjectStates'][0]['LuaScriptState'] = lua_state_json

# Write back
with open(farstalker_path, 'w', encoding='utf-8') as f:
    json.dump(tts_data, f, indent=2)

print(f"\n✓ Updated {farstalker_path}")
print(f"  All 8 objects in 2x5 grid with proper spacing")
