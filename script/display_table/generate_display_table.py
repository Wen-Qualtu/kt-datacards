"""Regenerate the KT display table save.

IMPORTANT: Run extract_manager_bag.py FIRST to create the minimal Manager bag.

This script builds the full display table FROM the minimal Manager bag:
  tts_objects/display-table/kt_manager_only.json (source of truth)
    ↓
  tts_objects/display-table/kt_all_teams_grid.json (generated with all teams)

Team boxes come from:
  tts_objects/* Cards.json
"""

from pathlib import Path
import sys

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from src.generators.display_table_generator import DisplayTableGenerator


def main() -> None:
    workspace_dir = Path(__file__).parent.parent
    gen = DisplayTableGenerator(
        tts_objects_dir=workspace_dir / "tts_objects",
        display_table_path=workspace_dir / "tts_objects" / "display-table" / "kt_all_teams_grid.json",
    )
    count = gen.regenerate()
    print(f"\n✓ Display table regenerated with {count} teams")


if __name__ == "__main__":
    main()
