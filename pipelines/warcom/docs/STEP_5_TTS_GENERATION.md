# Step 5: TTS Object Generation and Change Detection

## Purpose

Generate Tabletop Simulator (TTS) JSON objects from extracted cards and tokens with incremental update support using hash-based change detection.

---

## Script

`pipelines/warcom/steps/5_generate_tts_objects.py`

---

## Input

- **Cards**: `output/{team}/cards/**/*.jpg`
- **Tokens**: `output/{team}/tokens/*.png`
- **Metadata**: `output/.tts-metadata.json` (previous generation state)
- **Config**: `config/team-config.yaml`

---

## Output

### TTS Objects
- **Cardbox**: `output/{team}/tts/{team}-cardbox.json` (main container)
- **Single Cards**: `output/{team}/tts/cardbox/single-cards/{team}-{type}.json`
- **Decks**: `output/{team}/tts/cardbox/decks/{team}-{type}.json`
- **Individual Cards**: `output/{team}/tts/cardbox/decks/{type}/{team}-{card}.json`
- **Token Bag**: `output/{team}/tts/cardbox/token-bag/token-bag.json`
- **Dispensers**: `output/{team}/tts/cardbox/token-bag/{token}/{team}-{token}.json`
- **Tokens**: `output/{team}/tts/cardbox/token-bag/{token}/{team}-{token}-token.json`

### Metadata
- **File**: `output/.tts-metadata.json`
- **Purpose**: Tracks content hashes and GUIDs for change detection

### Lua Scripts
- **Cardbox script**: `output/{team}/tts/cardbox/{team}-lua-script.lua`
- **Token bag script**: `output/{team}/tts/cardbox/token-bag/{team}-token-bag.lua`

---

## Execution Order

### 1. Load Team Metadata

```python
team_meta = get_team_metadata(team_dir)
```

**Extraction:**
- Team name from directory
- Display name (canonical from config)
- Faction (imperium, chaos, xenos)

### 2. Organize Cards by Type

**Scan** `output/{team}/cards/**/*.jpg`:
- Group by card type folder
- Extract card names from filenames
- Separate fronts from backs

**Result:**
```python
{
  'datacards': ['kommando-boy', 'kommando-grot', ...],
  'equipment': ['kustom-shoota', ...],
  'ploys': ['get-stuck-in', 'opportunist', ...]
}
```

### 3. Create Single Cards vs Decks

**Decision logic:**

```
For each card type:
  If card count == 1:
    → Create single card object
    → Save to cardbox/single-cards/
  Else:
    → Create deck object with all cards
    → Save to cardbox/decks/
    → Save individual card JSONs to cardbox/decks/{type}/
```

**Examples:**
- `token-guide` (1 card) → Single card
- `operative-selection` (1 card) → Single card
- `datacards` (11 cards) → Deck

### 4. Create Card Objects

**For each card:**

1. **Find images**:
   ```python
   front_url = build_raw_url(front_path, workspace_root)
   back_url = build_raw_url(back_path, workspace_root)
   ```

2. **Build TTS card**:
   ```python
   card = TTSCard(
       registry=registry,
       team_name=team_name,
       card_name=card_name,
       front_url=front_url,
       back_url=back_url or front_url,  # Fallback to front
       card_type=deck_type,
       is_in_deck=True,
       tags=get_card_tags(team_name, deck_type, has_back)
   )
   ```

3. **Register with change detection**:
   - Calculate content hash of JSON
   - Compare with previous hash
   - Reuse existing GUID if unchanged

### 5. Create Deck Objects

**For card types with multiple cards:**

```python
deck = TTSDeck(
    registry=registry,
    team_name=team_name,
    deck_type=deck_type,
    cards=cards_in_deck
)
```

**Deck properties:**
- Contains all cards of that type
- Individual cards stored as `ContainedObjects`
- GUID assigned to deck itself

### 6. Create Token Bag (If Tokens Exist)

**Scan** `output/{team}/tokens/*.png`:
- Load token images
- Match to display names from filename
- Create dispenser for each token

**Token bag structure:**
```
Token Bag
└── Dispensers
    └── Each dispenser contains one token
```

**Dispenser:**
- 3D bag mesh (configurable)
- Spawns infinite copies of token
- Each token has unique dispenser

### 7. Create Cardbox Container

**Top-level object containing:**
- All decks
- All single cards
- Token bag (if tokens exist)

**Properties:**
- Custom mesh/texture (team-specific)
- Lua script for TTS behaviors
- Tags for categorization

### 8. Build Component Registry

**Change detection:**

```python
was_updated, content = registry.register(
    component_path="kommandos.cardbox.datacards.kommando-boy",
    content=card_json,
    component_type="card",
    guid=existing_guid or generate_guid(),
    url=card_url
)
```

**Registry tracks:**
- Content hash (SHA-256 of JSON)
- GUID (persistent across regenerations)
- URL (GitHub raw URL)
- Last modified timestamp
- Component type (card, deck, cardbox, token, etc.)

### 9. Save All JSONs

**For each component:**
1. Check if content changed
2. If changed or `--force` flag:
   - Write JSON to file
   - Update metadata
3. If unchanged:
   - Skip write (file already up-to-date)

### 10. Update Metadata File

**Write** `output/.tts-metadata.json`:

```json
{
  "kommandos": {
    "cardbox": {
      "guid": "abc123",
      "url": "https://raw.githubusercontent.com/.../kommandos-cardbox.json",
      "component_type": "cardbox",
      "content_hash": "sha256...",
      "last_modified": "2026-02-16T12:00:00Z",
      "datacards": {
        "guid": "def456",
        "url": "https://raw.githubusercontent.com/.../kommandos-datacards.json",
        "component_type": "deck",
        "content_hash": "sha256...",
        "last_modified": "2026-02-16T12:00:00Z",
        "kommando-boy": {
          "guid": "ghi789",
          "url": "https://raw.githubusercontent.com/.../kommando-boy.json",
          "component_type": "card",
          "content_hash": "sha256...",
          "last_modified": "2026-02-16T12:00:00Z"
        }
      }
    }
  }
}
```

---

## Change Detection System

### Content Hashing

**Algorithm:** SHA-256

**Input:** Normalized JSON (sorted keys, consistent formatting)

**Purpose:** Detect when card data changes (stats, text, images)

### GUID Persistence

**Generation:**
```python
guid = hashlib.md5(f"{team}_{component_name}".encode()).hexdigest()[:6]
```

**Reuse:**
- On first generation: Create new GUID
- On subsequent generations: Check metadata for existing GUID
- If found: Reuse existing GUID
- If not found or hash changed: Keep existing GUID but update content

**Why persistent GUIDs?**
- TTS recognizes objects by GUID
- Prevents duplicate spawning
- Allows in-place updates

### Update Detection

**For each component:**

1. Calculate content hash
2. Look up previous hash in metadata
3. Compare:
   - **Same hash** → No update needed
   - **Different hash** → Regenerate component
   - **No previous hash** → New component

**With `--force` flag:**
- Skip hash comparison
- Regenerate all components

---

## URL Generation

**GitHub Raw URLs:**

```python
def build_raw_url(file_path: Path, workspace_root: Path, branch: str = "main") -> str:
    rel_path = file_path.relative_to(workspace_root)
    return f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/{rel_path}"
```

**Branch Parameter:**
- Default: `main` (production branch)
- Used for all card images, mesh/texture files, and Lua scripts
- Allows testing changes on feature branches before merging
- Pass via CLI: `--branch feature-branch-name`

**Examples:**
- Card image: `https://raw.githubusercontent.com/.../main/output/kommandos/cards/datacards/kommandos-kommando-boy-front.jpg`
- Deck JSON: `https://raw.githubusercontent.com/.../main/output/kommandos/tts/cardbox/decks/kommandos-datacards.json`
- Feature branch: `https://raw.githubusercontent.com/.../add-warcom-pdf-processor/output/...`

**Why GitHub Raw?**
- Direct file access (no HTML wrapper)
- Stable URLs (branch-based)
- Free hosting for public repos
- CDN-backed delivery

---

## TTS Object Structure

### Card JSON

```json
{
  "Name": "Card",
  "Transform": {
    "posX": 0, "posY": 0, "posZ": 0,
    "rotX": 0, "rotY": 180, "rotZ": 0,
    "scaleX": 1, "scaleY": 1, "scaleZ": 1
  },
  "Nickname": "Kommando Boy",
  "Description": "",
  "CardID": 100,
  "SidewaysCard": false,
  "CustomDeck": {
    "1": {
      "FaceURL": "https://raw.githubusercontent.com/.../kommando-boy-front.jpg",
      "BackURL": "https://raw.githubusercontent.com/.../kommando-boy-back.jpg",
      "NumWidth": 1,
      "NumHeight": 1,
      "BackIsHidden": false
    }
  },
  "Tags": ["KTKommandos", "KTCardsDatacards", "KTCardsSided"]
}
```

### Deck JSON

```json
{
  "Name": "Deck",
  "Transform": { /* ... */ },
  "Nickname": "Datacards",
  "Description": "Kommandos Datacards",
  "DeckIDs": [100, 101, 102, ...],
  "CustomDeck": { /* ... */ },
  "ContainedObjects": [
    { /* Card 1 JSON */ },
    { /* Card 2 JSON */ },
    ...
  ],
  "Tags": ["KTKommandos", "KTCardsDatacards"]
}
```

### Cardbox JSON

```json
{
  "Name": "Custom_Model_Bag",
  "Transform": { /* ... */ },
  "Nickname": "Kommandos Cardbox",
  "Description": "Kill Team: Kommandos",
  "CustomMesh": {
    "MeshURL": "https://raw.githubusercontent.com/.../cardbox-mesh.obj",
    "DiffuseURL": "https://raw.githubusercontent.com/.../cardbox-texture.png",
    "ColliderURL": "",
    "Convex": true,
    "MaterialIndex": 1,
    "TypeIndex": 6,
    "CastShadows": true
  },
  "ContainedObjects": [
    { /* Deck 1 */ },
    { /* Deck 2 */ },
    { /* Token Bag */ }
  ],
  "LuaScript": "-- Cardbox script content",
  "Tags": ["KTKommandos", "KTCardBox"]
}
```

---

## Tagging System

**Tags format:** `KT{Context}{Value}`

**Examples:**
- `KTKommandos` - Team identifier
- `KTCardsDatacards` - Card type
- `KTCardsSided` - Has front/back
- `KTCardsUnsided` - Single-sided
- `KTCardBox` - Cardbox container
- `KTTokenBag` - Token bag

**Purpose:**
- Filtering in TTS
- Scripting identification
- Organization

---

## Error Handling

### Missing Card Images

**Symptom:**
```
WARNING: Missing front image for kommando-boy
```

**Cause:** Card not processed in Step 3.

**Recovery:** Skip card, log warning, continue.

### Token Processing Failure

**Symptom:**
```
ERROR: Token processing failed for kommandos; missing name mapping.
```

**Cause:** Step 4 didn't complete successfully.

**Recovery:**
- Cardbox still created (cards only)
- Token bag omitted
- User notified to rerun Step 4

**Design decision:** Don't fail entire TTS generation if tokens fail. Cards can still be used independently.

### Metadata Corruption

**Symptom:**
```
ERROR: Failed to load metadata: Invalid JSON
```

**Cause:** `.tts-metadata.json` corrupted or manually edited incorrectly.

**Recovery:**
- Regenerate with `--force` flag
- Creates new metadata from scratch
- All components regenerated

---

## Command Line Options

```bash
# Generate for all teams
python pipelines/warcom/steps/5_generate_tts_objects.py

# Specific teams
python ... --teams kommandos pathfinders

# Force regeneration (ignore change detection)
python ... --force

# Use specific Git branch for GitHub raw URLs (default: main)
python ... --branch add-warcom-pdf-processor

# Debug logging
python ... --log-level DEBUG

# Combined example
python ... --teams battleclade --branch dev --force
```

---

## Performance

**Typical runtime (single team):**
- Component building: ~1-2 seconds
- JSON generation: ~0.5 seconds per component
- Total: ~5-10 seconds

**With change detection:**
- Unchanged teams: < 1 second (skip regeneration)
- Changed teams: Full regeneration

**Bottleneck:** JSON serialization and file I/O

---

## Design Decisions

### Why Single Cards vs Decks?

**Problem:** Some card types have only one card (e.g., token-guide, operative-selection).

**Solution:**
- 1 card → Single card object (easier to place)
- 2+ cards → Deck object (keeps related cards together)

**Benefits:**
- Single cards don't need to be drawn from deck
- Decks keep groups organized
- Flexible structure

### Why Persistent GUIDs?

**Alternatives:**
1. Random GUIDs → Duplicates on regeneration
2. No GUIDs → TTS assigns random → Breaks references
3. Content-based GUIDs → Changes when content changes

**Chosen:** Hash of team + component name.

**Benefits:**
- Deterministic (same input = same GUID)
- Persistent across regenerations
- TTS recognizes objects

### Why Hash-Based Change Detection?

**Alternatives:**
1. Timestamp-based → Unreliable (file touches don't mean content changed)
2. Full JSON comparison → Slow for large objects
3. Version numbers → Manual tracking required

**Chosen:** SHA-256 content hashing.

**Benefits:**
- Fast comparison (64-character string)
- Cryptographically secure (no collisions)
- Deterministic (same content = same hash)

### Why Nested Output Structure?

**Structure:**
```
output/{team}/tts/
├── {team}-cardbox.json          # Top level
└── cardbox/
    ├── single-cards/            # Flat
    ├── decks/                   # 2 levels
    │   ├── {team}-{type}.json
    │   └── {type}/
    │       └── {team}-{card}.json
    └── token-bag/               # 3 levels
        ├── token-bag.json
        └── {token}/
            ├── {team}-{token}.json
            └── {team}-{token}-token.json
```

**Benefits:**
- Clear hierarchy
- Individual component JSONs for debugging
- Change detection granularity
- Organized file structure

---

## Maintenance

### Adding New Component Types

1. Create TTS class (e.g., `TTSNewComponent`)
2. Implement `.build()` method
3. Register with change detection
4. Add to cardbox container

### Updating TTS Object Format

**Compatibility:**
- TTS object format is stable
- Breaking changes require migration

**Process:**
1. Update TTS class methods
2. Test in TTS
3. Regenerate all objects with `--force`

### Debugging Change Detection

**Check metadata:**
```bash
cat output/.tts-metadata.json | jq '.kommandos.cardbox.datacards."kommando-boy"'
```

**Force regeneration:**
```bash
python ... --teams kommandos --force --log-level DEBUG
```

**Verify hashes:**
- Calculate hash of JSON file
- Compare with metadata hash
- Should match if content identical

---

**Last Updated**: February 17, 2026
