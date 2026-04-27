"""Generate the TTS display table JSON.

This updates the existing save file at:
  tts_objects/display-table/kt_all_teams_grid.json

by refreshing the KT Display Manager bag contents (all team card boxes), the
hard-coded team list in its Lua script, and the saved grid positions.

The repository historically treated this as a deploy-time artifact; this module
recreates it deterministically from the current tts_objects/* Cards.json files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import time


@dataclass(frozen=True)
class DisplayGridSpec:
    columns: int = 7
    start_x: float = -37.5753365
    start_z: float = 22.3820934
    dx: float = 12.4553365
    dz: float = 7.51
    y: float = 3.460002
    rot_x: float = -1.50793511e-07
    rot_y: float = 270.0
    rot_z: float = -1.09183293e-06


class DisplayTableGenerator:
    def __init__(
        self,
        *,
        tts_objects_dir: Path,
        display_table_path: Path,
        grid: DisplayGridSpec | None = None,
    ) -> None:
        self.tts_objects_dir = tts_objects_dir
        self.display_table_path = display_table_path
        self.grid = grid or DisplayGridSpec()

    def _now_date_string(self) -> str:
        # Match existing save style: "1/14/2026 8:13:24 PM"
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p").lstrip("0")
        return f"{now.month}/{now.day}/{now.year} {time_str}"

    def _iter_team_card_files(self) -> list[Path]:
        # tts_objects root contains "<Team Name> Cards.json" files.
        # Skip display-table and tokens subfolders.
        return sorted(
            (p for p in self.tts_objects_dir.glob("* Cards.json") if p.is_file()),
            key=lambda p: p.name.lower(),
        )

    def _load_team_bag_object(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("ObjectStates"):
            raise ValueError(f"No ObjectStates in team file: {path}")
        obj = data["ObjectStates"][0]
        if not isinstance(obj, dict):
            raise ValueError(f"Invalid team object in: {path}")
        return obj

    def _format_team_names_lua(self, names: list[str]) -> str:
        # Keep the same formatting pattern as the existing file:
        # 5 names per line, indented.
        lines: list[str] = []
        for i in range(0, len(names), 5):
            chunk = names[i : i + 5]
            joined = ", ".join([f'\"{n}\"' for n in chunk])
            if i + 5 < len(names):
                joined += ","
            lines.append(f"        {joined}")
        return "\n".join(lines)

    def _rewrite_team_names_in_script(self, script: str, names: list[str]) -> str:
        marker = "local teamNames = {"
        start = script.find(marker)
        if start == -1:
            return script

        # Find the matching closing brace for the teamNames block by looking for the
        # next line that starts with "    }" after the marker.
        end = script.find("\n    }", start)
        if end == -1:
            return script

        end = end + len("\n    }")

        replacement = (
            f"{marker}\n"
            f"{self._format_team_names_lua(names)}\n"
            f"    }}"
        )

        return script[:start] + replacement + script[end:]

    def regenerate(self) -> int:
        # Load the minimal Manager bag as the source of truth
        manager_only_path = self.tts_objects_dir / "display-table" / "kt_manager_only.json"
        if not manager_only_path.exists():
            raise FileNotFoundError(f"Minimal Manager file not found: {manager_only_path}. Run extract_manager_bag.py first.")
        
        with open(manager_only_path, "r", encoding="utf-8") as f:
            minimal_data = json.load(f)
        
        if not minimal_data.get("ObjectStates") or len(minimal_data["ObjectStates"]) == 0:
            raise ValueError("Minimal Manager file has no ObjectStates")
        
        manager = minimal_data["ObjectStates"][0]
        
        # Load the full display table to get the wrapper structure
        if not self.display_table_path.exists():
            raise FileNotFoundError(f"Display table file not found: {self.display_table_path}")

        with open(self.display_table_path, "r", encoding="utf-8") as f:
            save = json.load(f)

        # Build contained team bags.
        team_files = self._iter_team_card_files()
        team_names: list[str] = []
        contained: list[dict] = []

        for idx, team_file in enumerate(team_files):
            team_name = team_file.name.removesuffix(" Cards.json")
            team_names.append(team_name)

            bag = self._load_team_bag_object(team_file)
            bag = json.loads(json.dumps(bag))  # deep copy (keeps ordering)

            col = idx % self.grid.columns
            row = idx // self.grid.columns

            pos_x = self.grid.start_x + (col * self.grid.dx)
            pos_z = self.grid.start_z - (row * self.grid.dz)

            transform = bag.get("Transform") or {}
            transform.update(
                {
                    "posX": pos_x,
                    "posY": self.grid.y,
                    "posZ": pos_z,
                    "rotX": self.grid.rot_x,
                    "rotY": self.grid.rot_y,
                    "rotZ": self.grid.rot_z,
                }
            )
            bag["Transform"] = transform

            # Display table expects these to be grabbable.
            bag["Hands"] = True

            contained.append(bag)

        # Update manager bag contents.
        manager["ContainedObjects"] = contained

        # Update LuaScript team list.
        if isinstance(manager.get("LuaScript"), str):
            manager["LuaScript"] = self._rewrite_team_names_in_script(manager["LuaScript"], team_names)

        # Update positions map (GUID -> pos/rot), used by the manager "Place" button.
        positions: dict[str, dict] = {}
        for bag in contained:
            guid = bag.get("GUID")
            t = bag.get("Transform") or {}
            if not guid:
                continue
            positions[str(guid)] = {
                "pos": {"x": t.get("posX"), "y": t.get("posY"), "z": t.get("posZ")},
                "rot": {"x": t.get("rotX"), "y": t.get("rotY"), "z": t.get("rotZ")},
            }

        manager["LuaScriptState"] = json.dumps(positions, ensure_ascii=False)

        # Update top-level timestamp fields.
        save["EpochTime"] = int(time.time())
        save["Date"] = self._now_date_string()

        with open(self.display_table_path, "w", encoding="utf-8") as f:
            json.dump(save, f, indent=2, ensure_ascii=False)

        return len(contained)
