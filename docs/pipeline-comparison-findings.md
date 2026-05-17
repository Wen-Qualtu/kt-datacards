# Pipeline Output Comparison - Final Report

Date: May 15, 2026
Comparing: Old Pipeline (output_v2/tts_objects) vs Refactored Pipeline (output_v3)

## Executive Summary

The refactored pipeline (`output_v3`) produces **intentional naming and structural changes** compared to the old pipeline. These are design decisions, not bugs:

1. **TTS Card Naming**: Team-specific logic determines which cards keep team prefix
2. **File Naming**: Consistent hyphenation instead of mixed underscore/hyphen
3. **File Format**: PNG instead of JPG for better quality/transparency
4. **Data Structure**: Complete restructuring of team_data.json with more detail
5. **Roster Location**: Needs investigation (missing in refactored output)

---

## Detailed Findings

### 1. TTS Object Card Nicknames

#### Pattern: Team-Specific Naming Logic

**Angels of Death** - Operative cards drop team prefix:
```
OLD: angels-of-death-assault-intercessor-grenadier
NEW: assault-intercessor-grenadier

OLD: angels-of-death-space-marine-captain  
NEW: space-marine-captain
```

But equipment/ploys/faction rules keep prefix:
```
BOTH: angels-of-death-adaptive-tactics
BOTH: angels-of-death-auspex
BOTH: angels-of-death-astartes
```

Multi-card faction rules use new numbering:
```
OLD: angels-of-death-chapter-tactics_2
NEW: angels-of-death-chapter-tactics-card2
```

**Battleclade** - ALL cards keep team prefix:
```
BOTH: battleclade-auto-proxy-servitor
BOTH: battleclade-breacher-servitor
BOTH: battleclade-gun-servitor
...all 22 cards identical
```

#### Impact

- **Breaking change for Angels of Death** (and likely other Imperium teams)
- **No change for Battleclade** (and possibly other teams)
- Code that searches for cards by nickname needs to handle both patterns
- Cleaner TTS experience for teams with unique operative names

---

### 2. Card Image File Naming

#### Old Pipeline
```
Team prefix + underscore separator + .jpg
examples:
  angels-of-death-assault-intercessor-grenadier_front.jpg
  angels-of-death-assault-intercessor-grenadier_back.jpg
  
  battleclade-auto-proxy-servitor_front.jpg
  battleclade-auto-proxy-servitor_back.jpg
```

#### New Pipeline  
```
Consistent hyphenation + .png
examples:
  assault-intercessor-grenadier-front.png
  assault-intercessor-grenadier-back.png
  
  battleclade-auto-proxy-servitor-front.png
  battleclade-auto-proxy-servitor-back.png
```

#### Key Changes
1. **Format**: JPG → PNG (better quality, transparency support)
2. **Separator**: Underscore before front/back → hyphen everywhere
3. **Prefix**: Some teams drop prefix from operative cards (matches TTS nicknames)

#### Impact
- All file path references need updating
- Better image quality with PNG
- More consistent naming scheme
- Still maintains uniqueness within team directory

---

### 3. team_data.json Structure

#### Old Structure (Minimal)
```json
{
  "team": "...",
  "card_types": [...],
  "processing_summary": {...}
}
```

#### New Structure (Comprehensive)
```json
{
  "team": "...",
  "generated_at": "2026-05-15T...",
  "datacards": [...],
  "equipment": [...],
  "faction_rules": [...],
  "firefight_ploys": [...],
  "strategy_ploys": [...],
  "operatives_selection": [...]
}
```

#### Impact
- **Complete breaking change**
- Old structure was extraction metadata
- New structure is comprehensive card index
- Better organization for downstream tools
- Includes timestamp for cache busting
- All parsers need rewriting

---

### 4. Roster Data (statlines)

#### Status
- **Old**: `output_v2/{faction}/{team}/statlines/roster.json` ✅ EXISTS
- **New**: `output_v3/{team}/data/roster.json` ❌ MISSING

#### Investigation Needed
1. Check if roster extraction step runs in refactored pipeline
2. Verify if data is embedded in team_data.json instead
3. Confirm statline extraction is complete

---

### 5. Token Files

**Battleclade** (tokens_ready: true):
- **Old**: No token directory (not generated in old pipeline)
- **New**: 14 token files in `output_v3/battleclade/tokens/`
  ```
  battleclade-breach.obj
  battleclade-breach.png
  battleclade-gaze-of-the-omnissiah.obj
  battleclade-gaze-of-the-omnissiah.png
  ...
  ```

**Angels of Death** (tokens not enabled):
- **Both**: No token directory (as expected)

#### Impact
- New pipeline properly generates tokens for teams with `tokens_ready: true`
- Token generation is working in refactored pipeline

---

### 6. Directory Structure Changes

#### Old Pipeline
```
output_v2/
  {faction}/        # Organized by faction first
    {team}/
      datacards/    # Card images
      statlines/    # Roster data
      tts/          # TTS box obj/texture
      team_data.json
```

#### New Pipeline
```
output_v3/
  {team}/           # Organized by team directly
    cards/          # All card types
      datacards/
      equipment/
      faction_rules/
      ...
    tokens/         # Token images/models
    data/           # JSON data files
    tts_objects/    # TTS save files
```

#### Impact
- Flatter hierarchy (no faction grouping)
- Better separation of asset types
- More intuitive structure
- Path references need complete updating

---

## Summary: What Changed and Why

### Design Decisions (Intentional)

1. **Cleaner TTS Card Names**: Drop redundant team prefix from operative datacards where names are already unique
2. **Consistent File Naming**: All hyphens, no mixed separators
3. **Better Image Format**: PNG for quality and transparency
4. **Structured Data**: Comprehensive team_data.json instead of extraction metadata
5. **Better Organization**: Team-first directory structure

### Issues to Resolve

1. **Roster Data Missing**: Need to verify roster.json generation in refactored pipeline
2. **Multi-card Numbering**: Verify `_2` → `-card2` change is applied consistently

---

## Migration Checklist

### For Validation

- [x] Document TTS nickname differences  
- [x] Document file naming changes
- [x] Document structure changes
- [ ] Verify roster.json generation
- [ ] Test on 5+ different teams
- [ ] Verify multi-card faction rules across all teams

### For Code Updates

- [ ] Update TTS nickname matching logic (handle both patterns)
- [ ] Update file path references (JPG→PNG, faction removed, hyphens)
- [ ] Rewrite team_data.json parsers  
- [ ] Update documentation
- [ ] Create backward compatibility layer if needed

### Teams to Test

- [x] Angels of Death (operative prefix dropped)
- [x] Battleclade (all prefixes kept)
- [ ] Corsair Voidscarred (check pattern)
- [ ] Kasrkin (check pattern)
- [ ] Legionaries (check pattern)
- [ ] Pathfinders (check pattern)

---

## Conclusion

The refactored pipeline produces **better organized, more consistent output** with some **breaking changes**:

**Pros**:
- Cleaner card names in TTS
- Better file organization
- Higher quality images (PNG)
- More comprehensive data structures
- Proper token generation

**Cons/Risks**:
- Breaking changes require code updates
- Roster data may be missing
- Mixed naming patterns across teams could be confusing

**Recommendation**: The changes are improvements. Complete the validation, fix the roster.json issue, and document the migration path for downstream consumers.
