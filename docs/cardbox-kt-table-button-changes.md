# Card Box Button Split - KT Table Implementation

## Summary

Split the card box "Place" button functionality into two separate buttons to handle different placement scenarios:
1. **Place** - Original behavior using relative positioning (LuaScriptState positions)
2. **KT table** - New button for placing cards at global coordinates on the workshop table

## Problem

The unified "Place" button was causing issues in some situations because it would automatically detect the workshop table and switch between:
- Global coordinates (when on workshop table with KT_Ploy_Holders tag)
- Relative positioning (when on normal tables)

This automatic detection caused problems when users didn't want the workshop table behavior.

## Solution

### Changes Made

#### 1. New Button: "KT table"
- **Position**: Left side of box at `{-2, -2.5, -2}`, rotated 90° with text facing the box
- **Function**: `click_place_kt_table`
- **Behavior**: 
  - Checks if workshop table is detected (KT_Ploy_Holders tag)
  - Places cards at global coordinates specific to player color (Blue/Red)
  - Shows error if workshop table not detected
  - Shows error if positions not defined for player color

#### 2. Modified Button: "Place"
- **Position**: Right side of box at `{1.75, -2.5, 1}` (unchanged)
- **Function**: `click_place` (simplified)
- **Behavior**:
  - Always uses relative positioning based on LuaScriptState
  - No workshop table detection
  - Works the same on any table surface

### Button Layout on Box

```
   update     setup
KT          BOX
    place       recall
```

Where:
- **update** = Update cards button (left front)
- **setup** = Setup tokens button (left back)  
- **KT** = KT table button (left far back, NEW)
- **place** = Place button (right front)
- **recall** = Recall button (right back)

## Files Modified

### Template File
- `config/defaults/tts-script/tts-update-rules-in-box-script.lua`
  - Added `BUTTON_PLACE_KT_TABLE` definition
  - Added `click_place_kt_table()` function with workshop table logic
  - Simplified `click_place()` to only use relative positioning
  - Updated `changeButtons()` to include new button in 'done_setup' variant

### Card Box Files
All 46 card box JSON files in `tts_objects/` updated with new Lua script:
- Angels Of Death
- Battleclade
- Blades Of Khaine
- Blooded
- Brood Brothers
- Canoptek Circle
- Celestian Insidiants
- Chaos Cult
- Corsair Voidscarred
- Death Korps
- Deathwatch
- Elucidian Starstriders
- Exaction Squad
- Farstalker Kinband
- Fellgor Ravagers
- Gellerpox Infected
- Goremongers
- Hand Of The Archon
- Hearthkyn Salvagers
- Hernkyn Yaegirs
- Hierotek Circle
- Hunter Clade
- Imperial Navy Breachers
- Inquisitorial Agents
- Kasrkin
- Kommandos
- Legionaries
- Mandrakes
- Murderwings
- Nemesis Claw
- Novitiates
- Pathfinders
- Phobos Strike Team
- Plague Marines
- Ratlings
- Raveners
- Sanctifiers
- Scout Squad
- Tempestus Aquilons
- Vespid Stingwings
- Void Dancer Troupe
- Warpcoven
- Wolf Scouts
- Wrecka Krew
- Wyrmblade
- Xv26 Stealth Battlesuits

## Technical Details

### Workshop Table Detection
Both buttons use the same detection method:
```lua
local function isWorkshopTable()
  local workshopObjects = getObjectsWithTag(WORKSHOP_TABLE_TAG)
  return workshopObjects and #workshopObjects > 0
end
```

Where `WORKSHOP_TABLE_TAG = "KT_Ploy_Holders"`

### Global Coordinates
The `WORKSHOP_POSITIONS` table defines exact coordinates for each card type, per player color:
- Blue player positions (negative Z)
- Red player positions (positive Z)
- Card types: strategy_ploys, firefight_ploys, faction_rules, equipment, datacards, token_guide, token_bag, operative_selection

### Relative Positioning
The original `click_place` function now only uses:
```lua
local deltaPos = compare_coords(selfPos, entry.pos, rotationAdjustment)
obj.setPosition(deltaPos)
```

This calculates positions relative to the box's current location and rotation.

## Usage

### For Normal Play (Any Table)
1. Click "Setup" to memorize card positions
2. Move cards around as needed
3. Click "Place" to return cards to saved positions
4. Click "Recall" to return cards to box

### For Workshop Table Play
1. Ensure you're on a table with KT_Ploy_Holders tag
2. Click "Setup" to memorize cards
3. Click "KT table" to place cards at global workshop positions
   - Cards placed face-up at specific coordinates
   - Different positions for Blue vs Red player
4. Click "Recall" to return cards to box

## Script Used for Update

A Python script was created to apply these changes:
- `script/tools/update_cardbox_kt_table_button.py`
- Reads template Lua script
- Updates all card box JSON files
- Preserves all other data in the JSON files

## Testing

Verify the changes on a card box:
```powershell
$json = Get-Content "tts_objects/kasrkin/Kasrkin Cards.json" -Raw | ConvertFrom-Json
$script = $json.ObjectStates[0].LuaScript
$script -like "*KT table*"  # Should be True
$script -like "*click_place_kt_table*"  # Should be True
```

## Benefits

1. **User Control**: Players choose which placement mode to use
2. **No Surprises**: "Place" always works the same way regardless of table
3. **Workshop Table Support**: Still available via dedicated button
4. **Backwards Compatible**: Old behavior preserved in "Place" button
5. **Clear Intent**: Button names indicate what they do

## Future Considerations

- Could add indicator to show which table type is detected
- Could add confirmation dialog before placing on workshop table
- Could add settings to customize workshop positions per team
