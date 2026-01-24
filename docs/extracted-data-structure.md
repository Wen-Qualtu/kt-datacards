# Extracted Data Structure

This document describes the structure of the extracted data that will be stored per team during the extraction phase.

## Overview

We'll split the data into two separate files to separate concerns:

1. **Card Data** (in output folder): `output/{team}/team_data.json` - Contains the actual extracted card content
2. **ETL Metadata** (in metadata folder): `metadata/{team}/extraction_metadata.json` - Contains extraction tracking and pipeline information

This separation keeps the card data clean and focused on content, while tracking metadata separately for pipeline management.

---

## Card Data Structure

**Location:** `output/{team}/team_data.json`

Contains the actual card content organized by card type:

```json
{
  "team": {
    "name": "exaction-squad",
    "display_name": "Exaction Squad",
    "faction": "Imperium",
    "army": "Adeptus Arbites"
  },
  "card_types": {
    "datacards": {
      "arbites-proctor-exactant": {
        "card_name": "arbites-proctor-exactant",
        "display_name": "Arbites Proctor Exactant",
        "has_back": true,
        "content": {
          "description": "The leader of the squad, wielding an executioner shotgun",
          "full_text": "M 3\" | APL 2 | SV 3+ | W 10\nWEAPONS:\n- Executioner Shotgun (Range 6\", A 4, WS/BS 4+, D 4/5)\n- Shock Maul (Range -, A 4, WS/BS 3+, D 4/5)\nABILITIES:\nLeader: This operative can perform the Order action...",
          "stats": {
            "movement": "3\"",
            "apl": 2,
            "save": "3+",
            "wounds": 10
          }
        }
      },
      "arbites-castigator": {
        "card_name": "arbites-castigator",
        "display_name": "Arbites Castigator",
        "has_back": true,
        "content": {
          "description": "Heavy weapons specialist with grenade launcher",
          "full_text": "M 3\" | APL 2 | SV 4+ | W 8\nWEAPONS:\n- Grenade Launcher...",
          "stats": {
            "movement": "3\"",
            "apl": 2,
            "save": "4+",
            "wounds": 8
          }
        }
      }
    },
    "strategy-ploys": {
      "shock-and-awe": {
        "card_name": "shock-and-awe",
        "display_name": "Shock and Awe",
        "has_back": false,
        "content": {
          "description": "Until the end of the turning point, each time a friendly operative fights in combat or makes a shooting attack, in the Roll Attack Dice step of that combat or shooting attack, you can re-roll any or all of your attack dice.",
          "full_text": "SHOCK AND AWE\n1 CP\nUntil the end of the turning point, each time a friendly operative fights in combat or makes a shooting attack, in the Roll Attack Dice step of that combat or shooting attack, you can re-roll any or all of your attack dice."
        }
      }
    },
    "firefight-ploys": {
      "brutal-backup": {
        "card_name": "brutal-backup",
        "display_name": "Brutal Backup",
        "has_back": false,
        "content": {
          "description": "When combating the most belligerent of foes, Arbites squads call for overwhelming firepower.",
          "full_text": "BRUTAL BACKUP\n2 CP\nWhen combating the most belligerent of foes, Arbites squads call for overwhelming firepower."
        }
      }
    },
    "equipment": {
      "photo-visor": {
        "card_name": "photo-visor",
        "display_name": "Photo-visor",
        "has_back": false,
        "content": {
          "description": "The operative can perform shooting attacks while within Engagement Range of enemy operatives, and subtract 1 from the target number of its shooting attacks (to a minimum of 2+).",
          "full_text": "PHOTO-VISOR\n2 EP\nThe operative can perform shooting attacks while within Engagement Range of enemy operatives, and subtract 1 from the target number of its shooting attacks (to a minimum of 2+)."
        }
      }
    },
    "faction-rules": {
      "judgement": {
        "card_name": "judgement",
        "display_name": "Judgement",
        "has_back": true,
        "content": {
          "description": "Arbites operatives gain judgement tokens that can be spent to enhance their attacks.",
          "full_text": "JUDGEMENT\nAt the start of each turning point, each friendly operative gains 1 judgement token..."
        }
      }
    }
  },
  "processing_summary": {
    "total_cards": 42,
    "by_type": {
      "datacards": 10,
      "strategy-ploys": 12,
      "firefight-ploys": 8,
      "equipment": 10,
      "faction-rules": 2
    }
  }
}
```

---

## ETL Metadata Structure

**Location:** `metadata/{team}/extraction_metadata.json`

Contains extraction tracking, output paths, and pipeline information:

```json
{
  "team": {
    "name": "exaction-squad",
    "display_name": "Exaction Squad",
    "extraction_date": "2026-01-11T21:25:00"
  },
  "card_types": {
    "datacards": {
      "arbites-proctor-exactant": {
        "card_name": "arbites-proctor-exactant",
        "page_num": 3,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-datacards.pdf",
          "extracted_at": "2026-01-11T21:25:00",
          "text_extracted": true,
          "name_confidence": "high"
        },
        "output": {
          "front_image": "output/exaction-squad/datacards/arbites-proctor-exactant_front.jpg",
          "back_image": "output/exaction-squad/datacards/arbites-proctor-exactant_back.jpg",
          "image_format": "jpg",
          "image_dpi": 300
        }
      },
      "arbites-castigator": {
        "card_name": "arbites-castigator",
        "page_num": 5,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-datacards.pdf",
          "extracted_at": "2026-01-11T21:25:05",
          "text_extracted": true,
          "name_confidence": "high"
        },
        "output": {
          "front_image": "output/exaction-squad/datacards/arbites-castigator_front.jpg",
          "back_image": "output/exaction-squad/datacards/arbites-castigator_back.jpg",
          "image_format": "jpg",
          "image_dpi": 300
        }
      }
    },
    "strategy-ploys": {
      "shock-and-awe": {
        "card_name": "shock-and-awe",
        "page_num": 15,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-ploys.pdf",
          "extracted_at": "2026-01-11T21:26:00",
          "text_extracted": true,
          "name_confidence": "high"
        },
        "output": {
          "front_image": "output/exaction-squad/strategy-ploys/shock-and-awe_front.jpg",
          "back_image": null,
          "image_format": "jpg",
          "image_dpi": 300
        }
      }
    },
    "firefight-ploys": {
      "brutal-backup": {
        "card_name": "brutal-backup",
        "page_num": 18,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-firefight-ploys.pdf",
          "extracted_at": "2026-01-11T21:26:30",
          "text_extracted": true,
          "name_confidence": "high"
        },
        "output": {
          "front_image": "output/exaction-squad/firefight-ploys/brutal-backup_front.jpg",
          "back_image": null,
          "image_format": "jpg",
          "image_dpi": 300
        }
      }
    },
    "equipment": {
      "photo-visor": {
        "card_name": "photo-visor",
        "page_num": 22,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-equipment.pdf",
          "extracted_at": "2026-01-11T21:27:00",
          "text_extracted": true,
          "name_confidence": "medium"
        },
        "output": {
          "front_image": "output/exaction-squad/equipment/photo-visor_front.jpg",
          "back_image": null,
          "image_format": "jpg",
          "image_dpi": 300
        }
      }
    },
    "faction-rules": {
      "judgement": {
        "card_name": "judgement",
        "page_num": 25,
        "extraction": {
          "source_pdf": "processed/exaction-squad/exaction-squad-faction-rules.pdf",
          "extracted_at": "2026-01-11T21:27:30",
          "text_extracted": true,
          "name_confidence": "high"
        },
        "output": {
          "front_image": "output/exaction-squad/faction-rules/judgement_front.jpg",
          "back_image": "output/exaction-squad/faction-rules/judgement_back.jpg",
          "image_format": "jpg",
          "image_dpi": 300
        }
      }
    }
  },
  "processing_summary": {
    "pdfs_processed": 5,
    "total_pages_processed": 89,
    "cards_extracted": 42,
    "extraction_errors": 0,
    "warnings": [
      "Card 'photo-visor' has medium name confidence - extracted from text position"
    ]
  }
}
```

---

## Benefits of Separation

1. **Clean card data**: Output folder contains only content-focused data for users
2. **Pipeline tracking**: Metadata folder has all ETL/pipeline information for developers
3. **Version control**: Can .gitignore metadata/ folder if needed (pipeline-specific)
4. **Re-processing**: Can regenerate metadata without touching card content
5. **Different consumers**: Card data for game players, metadata for pipeline debugging

---

## Implementation Notes

The extraction pipeline would use two manager classes to handle these files:

### TeamDataManager (Card Content)

```python
class TeamDataManager:
    """Manages card content data in output folder"""
    
    def __init__(self, team_name: str):
        self.team_name = team_name
        self.data_file = Path(f"output/{team_name}/team_data.json")
        self.data = self._load_or_create()
    
    def _load_or_create(self) -> dict:
        if self.data_file.exists():
            with open(self.data_file) as f:
                return json.load(f)
        return {has_back: bool, content: dict):
        """Add card content data"""
        if card_type not in self.data["card_types"]:
            self.data["card_types"][card_type] = {}
        
        self.data["card_types"][card_type][card_name] = {
            "card_name": card_name,
            "display_name": card_name.replace('-', ' ').title().data["card_types"]:
            self.data["card_types"][card_type] = {}
        
        self.data["card_types"][card_type][card_name] = {
            "card_name": card_name,
            "display_name": card_name.replace('-', ' ').title(),
            "page_num": page_num,
            "has_back": has_back,
            "content": content
        }
    
    def save(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)
```

### ExtractionMetadataManager (ETL Tracking)

```python
class ExtractionMetadataManager:
    """Manages ETL metadata in metadata folder"""
    
    def __init__(self, team_name: str):
        self.team_name = team_name
        self.metadata_file = Path(f"metadata/{team_name}/extraction_metadata.json")
        self.metadata = self._load_or_create()
    
    def _load_or_create(self) -> dict:
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                return json.load(f)
        return {
            "team": {"name": self.team_name},
            "card_types": {},
            "processing_summary": {}
        }
    
    def add_card_metadata(self, card_type: str, card_name: str,
                          extraction: dict, output: dict):
        """Add card extraction and output metadata""" page_num: int,
                          extraction: dict, output: dict):
        """Add card extraction and output metadata"""
        if card_type not in self.metadata["card_types"]:
            self.metadata["card_types"][card_type] = {}
        
        self.metadata["card_types"][card_type][card_name] = {
            "card_name": card_name,
            "page_num": page_num
        }
    
    def save(self):
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
```

### Usage in ImageExtractor

Both managers would be used in the `ImageExtractor._extract_pages()` method:

```python
# Initialize managers
team_data = TeamDataManager(team.name)
extraction_meta = ExtractionMetadataManager(team.name)

for page_num, card_name in enumerate(extracted_cards):
    # Extract content
    content = self._extract_card_description(...)
    
    # Save card data
    team_data.add_card(
        card_type="datacards",
        card_name=card_name,
        page_num=page_num,
        has_back=True,
        content=content
    )
    
    # Save extraction metadata
    extraction_meta.add_card_metadata(
        card_type="datacards",
        card_name=card_name,
        page_num=page_num
            "source_pdf": pdf_path,
            "extracted_at": datetime.now().isoformat(),
            "text_extracted": True,
            "name_confidence": "high"
        },
        output={
            "front_image": f"output/{team.name}/datacards/{card_name}_front.jpg",
            "back_image": f"output/{team.name}/datacards/{card_name}_back.jpg",
            "image_format": "jpg",
            "image_dpi": 300
        }
    )

# Save both files
team_data.save()
extraction_meta.save()
```

This approach provides clean separation between user-facing content and pipeline tracking data.
