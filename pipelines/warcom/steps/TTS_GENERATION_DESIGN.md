# TTS Object Generation - Design & Architecture

## Overview
System for generating Tabletop Simulator (TTS) JSON objects with incremental update support using hash-based change detection.

## Architecture Components

### 1. Core Generation System (`pipelines/warcom/steps/5_generate_tts_objects.py`)

All generation logic is self-contained in Step 5 to keep the pipeline independent.

### 2. Pipeline Integration (`pipelines/warcom/steps/`)

Step 5 integrates the core system into the warcom pipeline:
- **Input**: `output/{team}/cards/**/*.jpg` (extracted cards from steps 1-3)
- **Output**: 
  - `output/{team}/tts/cardbox/*.json` (nested TTS objects)
  - `output/.tts-metadata.json` (full hierarchical tracking)
  - `output/.tts-manifest.json` (lightweight for TTS Lua)

## Metadata Structure

### Full Metadata (`.tts-metadata.json`)

Complete hierarchical structure with ALL components for repository tracking:

```json
{
  "kommandos": {
    "cardbox": {
      "guid": "abc123",
      "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox.json",
      "component_type": "cardbox",
      "content_hash": "...",
      "last_modified": "2026-02-03T21:00:00+00:00",
      "datacards": {
        "guid": "def456",
        "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/decks/{team}-datacards.json",
        "component_type": "deck",
        "content_hash": "...",
        "last_modified": "2026-02-03T21:00:00+00:00",
        "kommando-boy": {
          "guid": "ghi789",
          "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/decks/datacards/{team}-kommando-boy.json",
          "component_type": "card",
          "content_hash": "...",
          "last_modified": "2026-02-03T21:00:00+00:00"
        }
      },
      "token-bag": {
        "guid": "jkl012",
        "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/token-bag/token-bag.json",
        "component_type": "token_bag",
        "content_hash": "...",
        "last_modified": "2026-02-03T21:00:00+00:00",
        "breach": {
          "guid": "mno345",
          "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/token-bag/breach/{team}-breach.json",
          "component_type": "token_dispenser",
          "content_hash": "...",
          "last_modified": "2026-02-03T21:00:00+00:00",
          "breach": {
            "guid": "pqr678",
              "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/token-bag/breach/{team}-breach-token.json",
            "component_type": "token",
            "content_hash": "...",
            "last_modified": "2026-02-03T21:00:00+00:00"
          }
        }
      }
    }
  }
}
```

**Key Features:**
- **Metadata fields FIRST**: `guid`, `url`, `component_type`, `content_hash`, `last_modified`
- **Children AFTER**: Nested objects follow metadata fields
- **No `_self` keys**: Container metadata stored directly at parent level
- **No `file_size`**: Removed as unnecessary overhead

### Lightweight Manifest (`.tts-manifest.json`)
Simplified structure for TTS Lua scripts (prevents choking on large JSON):

```json
{
  "kommandos": {
    "cardbox": {
      "guid": "abc123",
      "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox.json",
      "content_hash": "...",
      "last_modified": "2026-02-03T21:00:00+00:00"
    },
    "decks": {
      "datacards": {
        "guid": "def456",
        "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/decks/{team}-datacards.json",
        "content_hash": "...",
        "last_modified": "2026-02-03T21:00:00+00:00"
      },
      "equipment": {
        "guid": "...",
        "url": "...",
        "content_hash": "...",
        "last_modified": "..."
      }
    },
    "token_bag": {
      "guid": "jkl012",
      "url": "https://raw.githubusercontent.com/.../output/{team}/tts/cardbox/token-bag/token-bag.json",
      "content_hash": "...",
      "last_modified": "2026-02-03T21:00:00+00:00"
    }
  }
}
```

**Extracted Fields:**
- Only deck/bag level (no individual cards/tokens)
- Only essential fields: `guid`, `url`, `content_hash`, `last_modified`

## Update Strategy

### Incremental Updates in TTS

TTS Lua script can check for updates at different granularity levels:

#### Level 1: Cardbox Level (Coarse)
```lua
-- Check if entire cardbox changed
if manifest.kommandos.cardbox.content_hash ~= stored_hash then
  -- Respawn entire cardbox
  spawnObjectJSON({
    json = fetch(manifest.kommandos.cardbox.url)
  })
end
```

#### Level 2: Deck Level (Optimal) ⭐
```lua
-- Check each deck individually
for deck_name, deck_meta in pairs(manifest.kommandos.decks) do
  if deck_meta.content_hash ~= stored_decks[deck_name] then
    -- Delete old deck
    old_deck.destruct()
    -- Spawn new deck
    spawnObjectJSON({
      json = fetch(deck_meta.url),
      position = old_position
    })
  end
end
```

#### Level 3: Card Level (Fine-grained)
```lua
-- For surgical updates, use full metadata
-- Check individual card hashes from .tts-metadata.json
if metadata.kommandos.cardbox.datacards["kommando-boy"].content_hash ~= stored_hash then
  -- Delete specific card
  card.destruct()
  -- Spawn replacement
  spawnObjectJSON({
    json = fetch(metadata.kommandos.cardbox.datacards["kommando-boy"].url)
  })
end
```

**Recommended Approach:**
- Use **manifest** for deck-level checks (balance between granularity and JSON size)
- Use **metadata** only for debugging or very fine-grained updates
- Token bags: Update entire bag (tokens in dispensers are complex to update individually)

## Change Detection

### Hash-Based System
- **Content Hash**: SHA-256 of TTS object JSON (normalized, sorted keys)
- **Persistent GUIDs**: MD5-based deterministic GUIDs stored in metadata, reused across regenerations
- **Timestamp Tracking**: ISO 8601 timestamps for every component

### GUID Persistence
```python
# On first generation
guid = hashlib.md5(f"{team}_{component_name}".encode()).hexdigest()[:6]

# On subsequent generations
existing_guid = metadata.get_guid(component_path)
if existing_guid:
    guid = existing_guid  # Reuse!
else:
    guid = generate_new_guid()
```

This ensures TTS recognizes objects across updates (no duplicate spawning).

## File Structure

### TTS Objects Output
```
output/
├── .tts-metadata.json          # Full hierarchical metadata
├── .tts-manifest.json          # Lightweight summary for Lua
└── kommandos/
  └── tts/
    ├── cardbox.json        # Container with all decks + token bag
    └── cardbox/
      ├── decks/
      │   ├── kommandos-datacards.json  # Deck object
      │   └── datacards/
      │       └── kommandos-kommando-boy.json
      └── token-bag/
        ├── token-bag.json  # Bag container
        └── breach/
          ├── kommandos-breach.json # Dispenser
          └── kommandos-breach-token.json  # Token
```

### GitHub Raw URLs
All `url` fields point to GitHub raw URLs for the component's JSON file:
```
https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/kommandos/tts/cardbox/decks/datacards/kommandos-kommando-boy.json
```

## Current Status

### ✅ Implemented
- Full metadata structure with proper field ordering
- Persistent GUID system
- Hash-based change detection
- Card and deck generation
- Cardbox container generation
- GitHub raw URL generation
- Manifest generation for TTS Lua

### 🚧 In Progress
- Token extraction (Step 4 in pipeline)
- Token bag generation (Step 5 integration, working on naming and mesh polish)

### 📋 TODO
- Test with multiple teams
- Master "Team Bag" container for multiple teams
- TTS Lua script integration
- Automatic tagging from card content (archetypes, keywords)
- Integration into CI/CD pipeline

## Usage

### Generate TTS Objects

```bash
# Generate for all teams
python pipelines/warcom/steps/5_generate_tts_objects.py

# Generate for specific teams
python pipelines/warcom/steps/5_generate_tts_objects.py --teams kommandos pathfinders

# Force regeneration (ignore change detection)
python pipelines/warcom/steps/5_generate_tts_objects.py --force

```

### TTS Lua Integration (Planned)

```lua
-- In TTS mod, fetch manifest periodically
manifest = JSON.decode(WebRequest.get(
  "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/output/.tts-manifest.json"
))

-- Check for deck updates
for team_name, team_data in pairs(manifest) do
  for deck_name, deck_meta in pairs(team_data.decks) do
    if needs_update(deck_name, deck_meta.content_hash) then
      update_deck(deck_name, deck_meta.url)
    end
  end
end
```

## Design Decisions

### Why Two Metadata Files?

**Full Metadata (`.tts-metadata.json`):**
- Complete history and tracking
- For repository/CI/CD use
- Detailed debugging information
- Can grow large (10k+ lines for many teams)

**Manifest (`.tts-manifest.json`):**
- Only deck/bag level summaries
- For TTS Lua scripts
- Stays lightweight (<1k lines even with many teams)
- Prevents TTS from choking on large JSON

### Why Metadata Fields Before Children?

Original structure had `_self` objects:
```json
"deck": {
  "card1": {...},
  "card2": {...},
  "_self": {"guid": "...", ...}  // Awkward!
}
```

New structure is cleaner:
```json
"deck": {
  "guid": "...",      // Metadata first
  "url": "...",
  "content_hash": "...",
  "card1": {...},     // Children after
  "card2": {...}
}
```

**Benefits:**
- More intuitive to read
- Metadata fields are static/controlled (no naming conflicts)
- Children come after (clear visual hierarchy)
- No special `_self` key needed

### Why No `file_size`?

- Adds no value for change detection (`content_hash` is sufficient)
- Unnecessary overhead in metadata
- Can be calculated from JSON if needed

## Future Enhancements

### 1. Archetype Tagging
Extract from card content when parser supports it:
```python
tags = [
  "KTKommandos",
  "KTCardsInfiltration",  # From archetype
  "KTCardsRecon"          # From keyword
]
```

### 2. Master Team Bag
Container holding multiple team cardboxes for full collection management.

### 3. Diff Report
Generate human-readable diff report:
```
Changes in kommandos:
  - datacards deck: 2 cards updated (kommando-boy, kommando-grot)
  - equipment deck: unchanged
  - token-bag: 1 dispenser added (smoke-grenade)
```

### 4. CI/CD Integration
Automatic generation on card updates, commit to repo, trigger TTS workshop update.

---

**Last Updated**: February 3, 2026  
**Status**: Core system complete, token generation pending  
**Next Steps**: Complete token extraction (Step 4), enable token bag generation
