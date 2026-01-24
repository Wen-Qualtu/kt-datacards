# Kill Team Datacard Structure Documentation

This document describes the consistent layout and text positioning across all Kill Team datacards. Understanding this structure allows us to reliably extract team names and card types based on position rather than just text content.

## General Notes

- All cards follow a consistent structure per card type
- Team name positioning is standardized across all teams
- The main exceptions are datacards and operative selection cards, which have unique layouts

**Multi-Page Cards (Front/Back):**
- Many cards have content that continues on the back side
- **Front side:** Always has full header (team name + card type + card name)
- **Back side:** NO header - starts directly with continuation text
- Front side indicator: "CONTINUES ON OTHER SIDE" (orange box with arrow at bottom)
- For PDF identification: We only need to examine the **first page** (always a front side)
- Optimization: Can detect backside by checking if previous page had "CONTINUES ON OTHER SIDE"
  - If yes, skip header extraction for current page
  - If no header found and no continuation indicator on previous page, may be malformed

**Current Processing Focus:**
- For team/card type identification: Only first page matters
- Backside handling is not critical for initial PDF organization and naming
- Future optimization: Use continuation indicator to skip header parsing on known backsides

## Card Types

### 1. Strategy Ploy Cards

**Structure:**
- **Header area (dark background):**
  - Line 1 (top): **Team Name** in orange color with small skull icon (e.g., "BATTLECLADE")
  - Line 2: **"STRATEGY PLOY"** in white text (card type header)
- **Ploy name:**
  - Line 3: **Ploy Name** in a box with green background (e.g., "DUTY OF RECLAMATION")
  - This is ALWAYS the first line after "STRATEGY PLOY"
- **Body:** 
  - Ploy description and rules text
  - May reference specific operative types

**Key Extraction Rules:**
- Team name: First text by Y-position (~5-10), orange colored, before "STRATEGY PLOY"
- Ploy name: Third line, in green box, immediately after card type header
- Never extract ploy name as team name

**Example:** Battleclade - "DUTY OF RECLAMATION"
- Team: "BATTLECLADE" (top, orange)
- Type: "STRATEGY PLOY"
- Ploy: "DUTY OF RECLAMATION" (in green box)

**Note:** Identical structure to Firefight Ploy, but ploy name has green background instead of black/other colors.

---

### 2. Firefight Ploy Cards

**Structure:**
- **Header area (dark background):**
  - Line 1 (top): **Team Name** in orange color with small skull icon (e.g., "BATTLECLADE")
  - Line 2: **"FIREFIGHT PLOY"** in white text (card type header)
- **Ploy name:**
  - Line 3: **Ploy Name** in a box (styling varies - can be black box, bordered box, etc.) (e.g., "AUTO-FERRIC SUPPLICATION")
  - This is ALWAYS the first line after "FIREFIGHT PLOY"
- **Body:** 
  - Ploy description and rules text
  - May reference specific operative types

**Key Extraction Rules:**
- Team name: First text by Y-position (~5-10), orange colored, before "FIREFIGHT PLOY"
- Ploy name: Third line, in box (various styles), immediately after card type header
- Never extract ploy name as team name

**Example:** Battleclade - "AUTO-FERRIC SUPPLICATION"
- Team: "BATTLECLADE" (top, orange)
- Type: "FIREFIGHT PLOY"
- Ploy: "AUTO-FERRIC SUPPLICATION" (in black box)

---

### 3. Faction Equipment Cards

**Structure:**
- **Header area (dark background):**
  - Line 1 (top): **Team Name** in orange color with small skull icon (e.g., "BATTLECLADE")
  - Line 2: **"FACTION EQUIPMENT"** in white text (card type header)
- **Equipment name:**
  - Line 3: **Equipment Name** in a bordered box (e.g., "CONCEALED APPARATUS")
  - This is ALWAYS the next text after "FACTION EQUIPMENT"
- **Body:** 
  - Equipment description and rules text
  - May include stats tables
  - Description can continue on reverse side

**Key Extraction Rules:**
- Team name: First text by Y-position (~5-10), orange colored, before "FACTION EQUIPMENT"
- Equipment name: Third line, in box, immediately after card type header
- Never extract equipment name as team name

**Example:** Battleclade - "CONCEALED APPARATUS"
- Team: "BATTLECLADE" (top, orange)
- Type: "FACTION EQUIPMENT"
- Equipment: "CONCEALED APPARATUS" (in box)

---

### 4. Faction Rules Cards

**Structure (Front Side):**
- **Header area (dark background):**
  - Line 1 (top): **Team Name** in orange color with small skull icon (e.g., "BATTLECLADE", "BLOODED")
  - Line 2: **"FACTION RULE"** in white text (card type header)
- **Rule name:**
  - Line 3: **Rule Name** in orange text with underline (e.g., "NOOSPHERIC NETWORK", "BLOODED")
  - This is ALWAYS the first line after "FACTION RULE" (on front side)
- **Body:** 
  - Rule description and mechanics
  - May reference specific operative types and game phases
- **Bottom:**
  - May have "CONTINUES ON OTHER SIDE" indicator (orange box with arrow)

**Structure (Back Side):**
- **NO HEADER** - no team name, no "FACTION RULE" text
- Starts directly with continuation of rule text
- May also have "CONTINUES ON OTHER SIDE" if multi-page rule

**Key Extraction Rules:**
- Team name: First text by Y-position (~5-10), orange colored, before "FACTION RULE"
- Rule name: Third line, orange text with underline, immediately after card type header
- Back side identified by previous page having "CONTINUES ON OTHER SIDE"
- For PDF identification: Only look at first page (never a backside)
- Never extract rule name as team name

**Examples:**
- Battleclade - "NOOSPHERIC NETWORK"
  - Team: "BATTLECLADE" (top, orange)
  - Type: "FACTION RULE"
  - Rule: "NOOSPHERIC NETWORK" (orange, underlined)
  
- Blooded - "BLOODED" 
  - Team: "BLOODED" (top, orange)
  - Type: "FACTION RULE"
  - Rule: "BLOODED" (orange, underlined)
  - Note: Rule name can match team name

**Note:** Back sides have no header - only front side has team name and card type.

---

### 5. Operatives Cards (Selection)

**Structure:**
(Exception - different layout from other card types, completely black background)

- **Team name area (top):**
  - Line 1-2: **Team Name followed by "KILL TEAM"** in white text (e.g., "BLOODED KILL TEAM")
  - Formatting varies based on team name length (can be 1 line or 2 lines)
  - Always pattern: `[TEAM NAME]` then `KILL TEAM`

- **Archetype bar (orange background):**
  - Format: **"ARCHETYPE: X, Y"** (always lists exactly 2 of 4 possible archetypes)
  - Possible archetypes: SECURITY, SEEK & DESTROY, RECON, INFILTRATION
  - Example: "ARCHETYPE: SECURITY, SEEK & DESTROY"
  - **Note:** Should be captured in metadata YAML for each team

- **Operatives header:**
  - **"OPERATIVES"** with orange underline

- **Operative selection lists:**
  - Multiple selection groups with format: `[Number] [TEAM_NAME] [operative type] with options:`
  - Each group lists equipment/weapon options as bullet points
  - Can have multiple selection groups (e.g., "1 CHIEFTAIN", "9 operatives from list", "4 operatives from other list")
  - Lists continue on back side if needed

- **Rules text:**
  - Bottom section explains selection constraints
  - Rules like "max 1 of each", "cannot combine certain options", etc.

- **Bottom:**
  - "CONTINUES ON OTHER SIDE" indicator (orange box with arrow)

**Key Extraction Rules:**
- Team name: Extract from first 1-2 lines, remove "KILL TEAM" suffix
- Card type: Identified by "OPERATIVES" with underline after archetype bar
- Archetype: Extract from orange bar for metadata (2 comma-separated values)
- No card name for operatives selection cards (they're just "operatives")

**Example:** Blooded
- Team: "BLOODED" (extracted from "BLOODED KILL TEAM")
- Type: "OPERATIVES"
- Archetype: "SECURITY, SEEK & DESTROY"
- Lists: 1 CHIEFTAIN, 9 from main list, 4 from special list

**Note:** This is the only card type with completely black background and archetype bar.

---

### 6. Datacards (Operative Stats)

**Structure (Front Side):**
(Exception - different layout from other card types)

- **Header area (dark background):**
  - Line 1 (left): **Operative Name** in white text with orange underline (e.g., "HEARTHKYN KOGNITÂAR")
  - Center: Operative artwork/picture (not relevant for extraction)
  - Right side: **4 stat blocks** in white boxes with values:
    - **APL** (Action Point Limit) - numeric value
    - **MOVE** - value with quote mark (e.g., "5"")
    - **SAVE** - value with plus (e.g., "3+")
    - **WOUNDS** - numeric value

- **Weapons table:**
  - Header row: **NAME | ATK | HIT | DMG | WR**
  - Multiple weapon rows with:
    - Icon before name (bullets = ranged, sword = close combat)
    - Weapon name and stats
  - Table has orange header line

- **Abilities section:**
  - Can be empty (no abilities)
  - Can have 1 or multiple abilities
  - Format: **"Role: ABILITY NAME"** followed by description text
    - Example: "Tactician: STRATEGIC GAMBIT"
  - Abilities may continue on back side

- **Bottom metadata bar (dark background):**
  - **Format: "TEAM_NAME, FACTION, ROLE_KEYWORDS"** (comma-separated)
  - Example: "HEARTHKYN SALVAGERS, LEAGUES OF VOTANN, KOGNITÂAR"
  - First element: Team name (orange text)
  - Remaining elements: Faction and operative-specific keywords
  - Right side: Circle with number (base size in mm)

- **Continuation:**
  - If abilities continue: "RULES CONTINUE ON OTHER SIDE" (orange bar)

**Structure (Back Side):**
- Header: Operative name (same as front)
- Stats boxes (same as front)
- Continuation of abilities
- Same bottom metadata bar

**Key Extraction Rules:**
- Team name: Extract from bottom metadata bar (first element before first comma)
- Operative name: Top left of header
- Card type: Identified by presence of APL/MOVE/SAVE/WOUNDS stat blocks
- Metadata format: Comma-separated, always includes team name, faction, and keywords
- No individual "card name" - the operative name is the identifier

**Example:** Hearthkyn Salvagers - "HEARTHKYN KOGNITÂAR"
- Operative: "HEARTHKYN KOGNITÂAR" (header)
- Stats: APL 2, MOVE 5", SAVE 3+, WOUNDS 8
- Weapons: Autoch-pattern bolter, Ion blaster, Fists
- Abilities: Tactician: STRATEGIC GAMBIT
- Metadata: "HEARTHKYN SALVAGERS, LEAGUES OF VOTANN, KOGNITÂAR"
- Team extracted: "HEARTHKYN SALVAGERS" (first element)
- Base size: 28mm

**Note:** Bottom metadata bar is the most reliable source for team name on datacards.

---

## Extraction Logic Recommendations

Based on the consistent structure:

1. **Team Name Extraction by Position:**
   - For Strategy Ploys, Firefight Ploys, Equipment, and Rules: Team name is ALWAYS at Y-position ~5-10 (first text on page)
   - For Operatives: Check for team name at top or in bottom metadata
   - For Datacards: Extract from bottom metadata line (comma-separated format)

2. **Card Title vs Team Name:**
   - Team name: First text item by Y-position, before card type header
   - Card title: Third text item, after card type header
   - Never confuse card title with team name

3. **Metadata Extraction:**
   - Bottom metadata format: "TEAM_NAME , FACTION, ROLE_KEYWORDS"
   - Always comma-separated
   - Works for datacards and some operatives cards

---

## Team Name Variations to Document

When documenting each card type, please note:
- Exact Y-position of team name text
- Font size of team name
- Whether team includes suffix like "KILL TEAM"
- Color coding (if relevant for extraction)
- Any team-specific variations

---

## TODO: Add Specific Card Examples

For each card type listed above, we need:
1. Full card screenshot
2. Close-up of team name area
3. Y-position and size measurements
4. Any team-specific edge cases
