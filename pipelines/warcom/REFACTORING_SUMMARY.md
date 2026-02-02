# Code Refactoring Summary - Warcom Pipeline Steps 2 & 3

## Changes Made

### File: `pipelines/warcom/steps/2_card_extractor.py`

**Line ~69**: Added reliability note to `extract_team_name_from_pdf()`
- Added TODO comment flagging this function as fragile and needing improvement
- Works for now but may extract incorrect text
- Suggests checking multiple pages or using more specific patterns

---

### File: `pipelines/warcom/steps/3_card_classification.py`

#### 1. Simplified Orientation Detection (Lines ~227-241)
**Before**: Checked both `is_landscape` and `is_portrait` from PDF analysis  
**After**: Only checks `is_landscape` from filename (extracted in previous step)
- Orientation is already encoded in filename from step 2
- Simpler logic: if filename contains 'landscape' → landscape, else → portrait
- Removed redundant `is_portrait` variable

#### 2. Unified Name Extraction (Lines ~280-370)
**Before**: Three separate functions:
- `_extract_name_from_header()` - for portrait cards
- `_extract_faction_rule_name()` - for faction rules
- `_extract_operative_name()` - for datacards

**After**: Single function `_extract_name_from_card(lines, is_landscape=False)`
- Handles all card types in one place
- Takes `is_landscape` parameter to determine extraction logic
- Keeps card names as they appear on the card (no prefix removal)
- **Removed team prefix removal logic** - names now match exactly what's on the card

#### 3. Simplified Naming Logic (Lines ~795-810)
**Before**: Complex logic with checks for back suffixes, prev_card tracking, fallback cases

**After**: Simple deterministic naming:
```python
# Determine card side (front by default, back determined later)
card_side = 'front'

# Build final card name: {team}-{name}-{side}
final_name = f"{team_name}-{card_name}-{card_side}"
```
- Removed `prev_card_type` and `prev_card_name` tracking variables
- No more back suffix checking during naming
- Side is determined at the beginning of loop, not in naming logic

#### 4. Extracted Special Case Functions (Lines ~444-680)

**New Helper Functions:**

**`_has_backside_continue(card_text: str) -> bool`**
- Generic function to check if card continues on other side
- Checks for both "CONTINUE" and "CONTINUES" variations
- Works for all orientations (was previously only checking 'CONTINU')

**`_is_angels_of_death_special_case(card_text: str) -> bool`**
- Identifies AoD Chapter Tactics cards
- Checks for specific marker text

**`_process_angels_of_death_cards(...) -> Tuple[int, int]`**
- Handles complete AoD special ordering
- Processes 4 cards in misordered sequence
- Returns (classified_count, skip_count)
- All AoD logic isolated from main loop

**`_process_card_backside(...) -> bool`**
- Processes a card that explicitly continues on other side
- Generic for both landscape and portrait
- Returns success/failure

**`_create_default_backside(...) -> bool`**
- Creates default backside when no continue statement
- Applies team-specific or default backside image
- Returns success/failure

#### 5. Cleaned Main Processing Loop (Lines ~830-870)
**Before**: 150+ lines of nested if/else with special cases inline

**After**: Clean, readable flow:
```python
# Extract card text
card_text = classifier.extract_text_from_card_pdf(card_path)

# Special case: Angels of Death
if _is_angels_of_death_special_case(card_text):
    aod_classified, aod_skip = _process_angels_of_death_cards(...)
    classified_count += aod_classified
    skip_next_card = aod_skip
    continue

# Check for explicit backside continuation
if _has_backside_continue(card_text) and idx + 1 < len(card_files):
    next_card_path = card_files[idx + 1]
    _process_card_backside(...)
    skip_next_card = 1
else:
    # Create default backside
    _create_default_backside(...)
```

---

## Benefits of Changes

### Code Quality
- **Reduced complexity**: Main loop reduced from ~200 lines to ~40 lines
- **Single Responsibility**: Each function does one thing well
- **DRY Principle**: Backside processing logic not repeated
- **Testability**: Helper functions can be unit tested independently

### Maintainability  
- **Clear separation of concerns**: Special cases isolated
- **Easier debugging**: Can add breakpoints in specific helper functions
- **Extensible**: Easy to add new special cases without touching main loop

### Correctness
- **Fixed continue detection**: Now checks for both "CONTINUE" and "CONTINUES"
- **Generic backside logic**: Works for both landscape and portrait
- **Consistent naming**: One simple pattern for all cards
- **Removed team prefix logic**: Names match cards exactly as printed

### Performance
- **No change**: Same number of operations, just reorganized

---

## Design Decisions Reflected in Code

All changes align with the documented design in `DESIGN.md`:

1. **Step Independence**: Orientation comes from filename (step 2 output)
2. **Type Classification Order**: Notes → Landscape → Operative Selection → Line 2
3. **Name Extraction**: Line 1 for datacards, Line 3 for portrait cards
4. **Backside Handling**: Check continue phrase → process backside OR create default

---

## Testing Recommendations

Before merging, test:
1. Run step 3 on a team with datacards (landscape)
2. Run step 3 on a team with portrait cards that have backsides
3. Run step 3 on Angels of Death team (special case)
4. Verify output naming: `{team}-{card-name}-front.png` and `{team}-{card-name}-back.png`
5. Check that names match exactly as they appear on cards (no prefix removal)

---

## Breaking Changes

**Naming Convention**: Card names now include full text from card without team prefix removal.

**Example:**
- **Before**: `legionaries-gunner-front.png` (prefix removed)
- **After**: `legionaries-legionaries-gunner-front.png` (full name as on card)

If downstream systems depend on the old naming, they will need to be updated.
