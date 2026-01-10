# Team-Specific Custom Backsides

This folder contains custom backside images for specific teams.

## Usage

To add custom backsides for a team:

1. Create a folder with the team name: `script/config/card-backside/team/{team-name}/`
2. Add custom backside images:
   - `backside-portrait.jpg` - Used for equipment, ploys, faction rules, operatives
   - `backside-landscape.jpg` - Used for datacards

## Examples

### Example 1: Kasrkin Custom Backsides
```
script/config/card-backside/team/
└── kasrkin/
    ├── backside-portrait.jpg   # Custom backside for equipment/ploys
    └── backside-landscape.jpg  # Custom backside for datacards
```

### Example 2: Only Custom Datacards Backside
```
script/config/card-backside/team/
└── angels-of-death/
    └── backside-landscape.jpg  # Custom backside only for datacards
                                # Equipment/ploys will use default portrait
```

## Priority Order

When `add_default_backsides.py` runs, it checks in this order:

1. **Team-specific backside** (this folder) - if exists, use it
2. **Default backside** (`script/config/card-backside/default/`) - fallback

## Image Requirements

- **Format**: JPG
- **Naming**: 
  - `backside-portrait.jpg` for portrait cards
  - `backside-landscape.jpg` for landscape cards
- **Resolution**: Match your card extraction DPI (default: 300 DPI)
- **Aspect Ratios**:
  - Portrait: Typically 63mm × 88mm (standard card size)
  - Landscape: Typically 88mm × 63mm (datacards)

## Tips

- Design backsides with team theme, colors, or logos
- Keep text minimal for easy readability in TTS
- Test in TTS to ensure visibility at normal zoom levels
- Consider using the default backside as a template

## When to Use Custom Backsides

**Good use cases:**
- Team has distinct visual theme or faction colors
- Want to differentiate teams quickly in TTS
- Creating tournament-ready sets with professional look

**Default is fine when:**
- Consistent look across all teams is preferred
- Quick prototyping or testing
- Default backside already matches your needs
