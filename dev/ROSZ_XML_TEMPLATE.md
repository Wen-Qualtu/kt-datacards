# .rosz XML Structure Template & Data Mapping

## Overview
A `.rosz` file is a ZIP archive containing a `.ros` file (BattleScribe XML format).

---

## XML Structure

### 1. Root Element: `<roster>`
```xml
<roster 
  id="6t08qu6" 
  name="Salvagers" 
  battleScribeVersion="2.03" 
  generatedBy="https://newrecruit.eu" 
  gameSystemId="c521-ad27-44df-f959" 
  gameSystemName="Warhammer 40,000: Kill Team (2024)" 
  gameSystemRevision="9" 
  xmlns="http://www.battlescribe.net/schema/rosterSchema">
```

**What we need:**
- ✅ `name`: Team name (from our config/metadata)
- ✅ `gameSystemName`: Constant "Warhammer 40,000: Kill Team (2024)"
- 🔧 `id`: Generate unique GUID
- 🔧 `battleScribeVersion`: Constant "2.03"
- 🔧 `generatedBy`: Our tool name
- 🔧 `gameSystemId`, `gameSystemRevision`: Constants

---

### 2. Forces & Team-Level Rules

```xml
<forces>
  <force id="6uermg9" name="Roster" entryId="default-force" 
         catalogueId="58da-24b8-ca3c-2bf4" catalogueRevision="8" 
         catalogueName="Hearthkyn Salvagers">
    
    <!-- Team-wide rules (if any) -->
    <rules>
      <rule id="561b-4528-0dc8-9748" name="Grudge" hidden="false">
        <description>Whenever an enemy operative incapacitates...</description>
      </rule>
    </rules>
    
    <selections>
      <!-- Operatives here -->
    </selections>
  </force>
</forces>
```

**What we need:**
- ✅ `catalogueName`: Team name from metadata
- 🔧 `rule` elements: Team-wide special rules
  - **Where in our data?** Could be in faction-rules, ploys, or abilities
  - **Gap:** Need to identify which rules are team-wide vs operative-specific

---

### 3. Operative (Selection)

```xml
<selection id="p3see4i" name="Theyn" entryId="b737-d90f-310b-04df" 
          number="1" type="model" from="entry">
  
  <!-- Operative stats & abilities -->
  <profiles>
    <!-- Profile 1: Stats -->
    <profile id="50c0-143a-9713-d6fa" name="Theyn" 
             typeId="5156-3fb9-39ce-7bdb" typeName="Operative">
      <characteristics>
        <characteristic name="APL">2</characteristic>
        <characteristic name="Move">5"</characteristic>
        <characteristic name="Save">3+</characteristic>
        <characteristic name="Wounds">9</characteristic>
      </characteristics>
    </profile>
    
    <!-- Profile 2: Abilities -->
    <profile id="7d42-74a6-d450-9ab6" name="Eye of the Ancestors" 
             typeId="f887-5881-0e6d-755c" typeName="Abilities">
      <characteristics>
        <characteristic name="Ability">**STRATEGIC GAMBIT**. Select one enemy operative...</characteristic>
      </characteristics>
    </profile>
    
    <!-- Profile 3: More abilities -->
    <profile id="835e-b513-fa85-eee6" name="Weavefield Crest" 
             typeId="f887-5881-0e6d-755c" typeName="Abilities">
      <characteristics>
        <characteristic name="Ability">Once per battle, when an attack dice...</characteristic>
      </characteristics>
    </profile>
  </profiles>
  
  <!-- Weapon selections (nested) -->
  <selections>
    <!-- See Weapon section below -->
  </selections>
  
  <!-- Keywords/Categories -->
  <categories>
    <category id="fe71-c335-8feb-bb5c" name="Hearthkyn Salvagers" 
              entryId="fe71-c335-8feb-bb5c" primary="false" />
    <category id="a016-36a7-fbed-5668" name="Leagues of Votann" 
              entryId="a016-36a7-fbed-5668" primary="false" />
    <category id="d999-8cad-8145-4efe" name="Leader" 
              entryId="d999-8cad-8145-4efe" primary="true" />
    <category id="7576-7e96-4361-a480" name="Theyn" 
              entryId="7576-7e96-4361-a480" primary="false" />
  </categories>
</selection>
```

**What we need from datacards:**
- ✅ `name`: Operative name
- ✅ **Stats**: APL, Move, Save, Wounds
  - **Our data:** From statlines extraction (output/{team}/statlines/roster.json)
  - **Status:** ✅ 100% stats, 48.7% rules
  
- ⚠️ **Abilities**: Multiple `<profile typeName="Abilities">`
  - **Where?** Mixed in datacards "rules" field and unique actions
  - **Gap:** Need to separate abilities from weapons/actions
  
- ⚠️ **Categories/Keywords**: Team, Faction, Role, Operative Type
  - **Where?** Not currently extracted
  - **Gap:** Need keyword extraction from cards (LEADER, PSYKER, etc.)

---

### 4. Weapons (Nested Selection)

```xml
<selection id="p4xqxgo" name="Concussion gauntlet" 
          entryId="8aac-a62c-1769-3143" 
          entryGroupId="ba43-aa6d-9d0c-a804" 
          number="1" type="upgrade" from="group" group="Melee weapon">
  
  <!-- Weapon rules -->
  <rules>
    <rule id="5151-5449-ca81-70ed" name="Brutal" hidden="false">
      <description>Your opponent can only block with critical successes.</description>
    </rule>
    <rule id="c544-8d4c-4109-4eec" name="Shock" hidden="false">
      <description>The first time you strike with a critical success...</description>
    </rule>
  </rules>
  
  <!-- Weapon profile -->
  <profiles>
    <profile id="d8b0-7c44-377b-5aa3" name="⚔ Concussion gauntlet" 
             typeId="f25f-4b13-b724-d5a8" typeName="Weapons">
      <characteristics>
        <characteristic name="ATK">4</characteristic>
        <characteristic name="HIT">4+</characteristic>
        <characteristic name="DMG">5/7</characteristic>
        <characteristic name="WR">Brutal, Shock</characteristic>
      </characteristics>
    </profile>
  </profiles>
</selection>
```

**What we need:**
- ✅ **Weapon name**: From statlines weapons array
- ✅ **Weapon stats**: ATK, HIT, DMG
  - **Our data:** In statlines/roster.json weapons
  - **Status:** ✅ 100% weapons extracted
  
- ✅ **Weapon rules (WR)**: In comma-separated format
  - **Our data:** In weapon's SR field
  - **Status:** ✅ Extracted

- ⚠️ **Weapon type prefix**: ⚔ (melee) or ⌖ (ranged)
  - **Gap:** Need to identify weapon type
  - **Solution:** ✅ USER CONFIRMED: Weapons have ICONS (bullets=ranged, sword=melee)
  - **Implementation:** Need image recognition to detect icon type in weapon region
  - **Fallback:** Manual weapon type config mapping if image detection too complex. Order is always range first then melee. Never mixed. But number vary vastly and some have only Melee.

- ⚠️ **Individual rule descriptions**: Each rule as separate `<rule>` element
  - **Gap:** Currently just comma-separated text
  - **Solution:** Parse WR field and expand rules with full descriptions

- ⚠️ **Weapon grouping**: `entryGroupId` and `group` (e.g., "Melee weapon", "Ranged weapon")
  - **Gap:** Need to group weapons by type

---

## Key Observations from Salvagers Example

### Problem: Duplicate Operatives
New Recruit creates **separate operative entries** for each weapon loadout:
- Theyn #1: Concussion gauntlet + Autoch-pattern bolt pistol
- Theyn #2: Concussion gauntlet + Autoch-pattern bolter
- Theyn #3: Concussion gauntlet + Bolt revolver
- ... (12 total Theyn variants!)

### Our Solution: Consolidated Operatives
**Better approach**: One operative type with ALL possible weapons listed:

```xml
<selection name="Theyn">
  <profiles>
    <!-- Single stat profile -->
  </profiles>
  <selections>
    <!-- ALL melee weapon options -->
    <selection name="Concussion gauntlet" />
    <selection name="Plasma weapon" />
    
    <!-- ALL ranged weapon options -->
    <selection name="Autoch-pattern bolt pistol" />
    <selection name="Autoch-pattern bolter" />
    <selection name="Bolt revolver" />
    <selection name="Etacarn plasma pistol" />
    <selection name="Ion blaster" />
    <selection name="Ion pistol" />
  </selections>
</selection>
```

**Benefits:**
- Cleaner structure
- Easier to generate
- Users can select loadout in TTS Command Node
- Matches how datacards actually work (one card, multiple options)

---

## Data Extraction Gaps

### What We Have ✅
1. **Operative stats** (APL, Move, Save, Wounds): 100% coverage
2. **Weapon profiles** (ATK, HIT, DMG, WR): 100% coverage
3. **Team names and factions**: From config
4. **Card images**: For reference during extraction

### What We Need 🔧

#### 1. **Keyword Extraction** (CRITICAL) ✅ KEYWORDS IN OCR!
**Where:** Black bar at bottom of datacard (front side)
**Examples:** `HEARTHKYN SALVAGER, LEAGUES OF VOTANN, LEADER, THEYN`
**Format:** Comma-separated, all caps, first one is team name (orange color)
**Current Status:** ✅ Already in OCR text! Just need to parse it
**How to extract:** 
- Search for pattern: `[A-Z ,]+` near bottom of page (y > 80%)
- Split by comma
- First keyword is team name, rest are categories
- Filter out common words (AND, OR, etc)

#### 2. **Ability Separation** (HIGH PRIORITY) ✅ USER CONFIRMED
**Current state:** Mixed in "rules" field
**Need to split into:**
- Passive abilities (always active)
- Unique actions (cost AP)
- Weapon special rules (already in weapons)

**Solution:** ✅ USER CONFIRMED: "if cost then UA else passive abilities"
- Parse for AP cost pattern: `(1AP)`, `(2AP)`, etc.
- If rule contains AP cost → Unique Action
- If no AP cost → Passive Ability
- Example pattern: `r'\((\d+)AP\)'`

#### 3. **Rule Descriptions** (MEDIUM PRIORITY) ✅ USER CONFIRMED
**Current:** Just rule names in WR (e.g., "Brutal, Shock")
**Need:** Full descriptions for each rule

**Solution:** ✅ USER CONFIRMED: Extract from "Kill Team Lite Rules PDF from Warcom"
- Source: Warcom key downloads page
- Location: Last page of PDF
- Format: Rule name + full description
- Store in: `config/weapon_rules.yaml` or `.json`
- Example structure:
```yaml
weapon_rules:
  Brutal: "Your opponent can only block with critical successes."
  Shock: "The first time you strike with a critical success..."
  Piercing 1: "The defender collects 1 less defence dice."
```

#### 4. **Weapon Type Detection** (MEDIUM - Needs Image Recognition) ✅ USER CONFIRMED
**Solution:** ✅ USER CONFIRMED: "Icons only - bullets=ranged, sword=melee"
- NOT text-based (no (M)/(R) prefixes)
- Detection required: Image recognition for weapon icons
- Bullet icon (🔫) → Ranged weapon
- Sword icon (⚔️) → Melee weapon
- Implementation options:
  1. PyMuPDF image extraction at weapon coordinates
  2. OCR symbol/icon recognition
  3. Fallback: Manual `config/weapon_types.yaml` mapping

#### 5. **Team-Wide Rules** (LOW PRIORITY)
**Where:** Faction rules or team abilities
**Solution:** Could come from faction-rules extractions

---

## Recommended Generation Steps

### Step 1: Enhance Statline Extraction
Add to `output/{team}/statlines/roster.json`:

```json
{
  "operatives": [
    {
      "name": "Theyn",
      "stats": {
        "APL": 2,
        "Move": "5\"",
        "Save": "3+",
        "Wounds": 9
      },
      "weapons": [
        {
          "name": "⚔ Concussion gauntlet",
          "type": "melee",
          "stats": {
            "ATK": 4,
            "HIT": "4+",
            "DMG": "5/7",
            "WR": ["Brutal", "Shock"]
          }
        }
      ],
      "abilities": [
        {
          "name": "Eye of the Ancestors",
          "type": "unique_action",
          "cost": "0AP",
          "description": "**STRATEGIC GAMBIT**. Select one enemy operative..."
        }
      ],
      "keywords": ["HEARTHKYN SALVAGERS", "LEAGUES OF VOTANN", "LEADER", "THEYN"]
    }
  ]
}
```

### Step 2: Create Rules Database
File: `config/weapon_rules.yaml`

```yaml
Brutal:
  description: "Your opponent can only block with critical successes."
  
Shock:
  description: "The first time you strike with a critical success in each sequence, also discard one of your opponent's unresolved normal successes (or a critical success if there are none)."

"Piercing 1":
  description: "The defender collects 1 less defence dice."
  
# ... etc
```

### Step 3: Generate .rosz XML
New script: `script/generate_rosz.py`

```python
def generate_rosz(team_name: str) -> bytes:
    """Generate .rosz file for a team."""
    # 1. Load statlines data
    roster_data = load_roster_json(team_name)
    
    # 2. Build XML structure
    roster_xml = create_roster_xml(team_name, roster_data)
    
    # 3. Create .ros file
    ros_content = format_xml(roster_xml)
    
    # 4. Zip into .rosz
    return create_rosz_archive(ros_content, team_name)
```

---

## Example: What Theyn Should Look Like

```xml
<selection id="theyn-001" name="Theyn" type="model">
  
  <!-- Stats -->
  <profiles>
    <profile name="Theyn" typeName="Operative">
      <characteristics>
        <characteristic name="APL">2</characteristic>
        <characteristic name="Move">5"</characteristic>
        <characteristic name="Save">3+</characteristic>
        <characteristic name="Wounds">9</characteristic>
      </characteristics>
    </profile>
    
    <!-- Abilities -->
    <profile name="Eye of the Ancestors" typeName="Abilities">
      <characteristics>
        <characteristic name="Ability">**STRATEGIC GAMBIT**. Select one enemy operative, or up to two enemy operatives if three or more friendly **HEARTHKYN SALVAGER** operatives are incapacitated. Each of those enemy operatives gains one of your Grudge tokens.</characteristic>
      </characteristics>
    </profile>
    
    <profile name="Weavefield Crest" typeName="Abilities">
      <characteristics>
        <characteristic name="Ability">Once per battle, when an attack dice inflicts Normal Dmg on this operative, you can ignore that inflicted damage.</characteristic>
      </characteristics>
    </profile>
  </profiles>
  
  <!-- Weapons (ALL options) -->
  <selections>
    <!-- Melee options -->
    <selection name="Concussion gauntlet" type="upgrade" group="Melee weapon">
      <rules>
        <rule name="Brutal"><description>Your opponent can only block with critical successes.</description></rule>
        <rule name="Shock"><description>The first time you strike with a critical success in each sequence, also discard one of your opponent's unresolved normal successes (or a critical success if there are none).</description></rule>
      </rules>
      <profiles>
        <profile name="⚔ Concussion gauntlet" typeName="Weapons">
          <characteristics>
            <characteristic name="ATK">4</characteristic>
            <characteristic name="HIT">4+</characteristic>
            <characteristic name="DMG">5/7</characteristic>
            <characteristic name="WR">Brutal, Shock</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selection>
    
    <selection name="Plasma weapon" type="upgrade" group="Melee weapon">
      <rules>
        <rule name="Lethal 5+"><description>Your successes equal to or greater than 5+ are critical successes.</description></rule>
      </rules>
      <profiles>
        <profile name="⚔ Plasma weapon" typeName="Weapons">
          <characteristics>
            <characteristic name="ATK">4</characteristic>
            <characteristic name="HIT">3+</characteristic>
            <characteristic name="DMG">4/6</characteristic>
            <characteristic name="WR">Lethal 5+</characteristic>
          </characteristics>
        </profile>
      </profiles>
    </selection>
    
    <!-- Ranged options -->
    <selection name="Autoch-pattern bolt pistol" type="upgrade" group="Ranged weapon">
      <!-- Similar structure -->
    </selection>
    
    <!-- More weapon options... -->
  </selections>
  
  <!-- Keywords -->
  <categories>
    <category name="Hearthkyn Salvagers" primary="false" />
    <category name="Leagues of Votann" primary="false" />
    <category name="Leader" primary="true" />
    <category name="Theyn" primary="false" />
  </categories>
</selection>
```

---

## Summary: Steps to Success

1. ✅ **Stats extraction**: Already working!
2. 🔧 **Add keyword extraction**: Parse for LEADER, PSYKER, etc.
3. 🔧 **Separate abilities from weapons**: Parse rules field better
4. 🔧 **Create weapon rules database**: Standard rules with descriptions
5. 🔧 **Consolidate operative loadouts**: One operative → all weapons
6. 🔧 **Build XML generator**: Create .rosz from enhanced metadata
7. 🔧 **Test with TTS Command Node**: Verify it loads correctly

**Estimated effort:**
- Keyword extraction: 2-3 hours
- Rules database: 1-2 hours (initial)
- XML generator: 4-6 hours
- **Total: ~1 day of dev work**

**Biggest win:** No more New Recruit dependency for users! 🎉
