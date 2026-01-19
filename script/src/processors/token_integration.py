"""Token integration pipeline.

This repository has two workflows:
- Cards: extracted from PDFs and regenerated frequently.
- Tokens: extracted once per team, then treated as immutable once approved.

A team can be "released" by setting `tokens_ready: true` in config/team-config.yaml.

Behavior:
- tokens_ready == false (default): tokens are packaged into output_v2/.../tts/token so
    they can be inspected/hosted, but are NOT embedded into the TTS box/state.
- tokens_ready == true: tokens are packaged into output_v2/.../tts/token and embedded
    into the team TTS box file under tts_objects/. Existing token assets are treated as
    immutable (no overwrites) once a team is ready.

This module focuses on *packaging + embedding* for ready teams. The extraction/tuning
cycle still happens via the token tooling modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import json
import yaml

from src.token_tools.add_tokens_to_box import add_tokens_to_box
from src.token_tools.generate_team_token_bag import TeamTokenBagGenerator
from src.token_tools.generate_tts_tokens import TTSTokenGenerator


@dataclass
class TeamTokenStatus:
    team: str
    canonical_name: str
    faction: str
    tokens_ready: bool


class TokenIntegrator:
    def __init__(
        self,
        *,
        project_root: Path,
        config_path: Path,
        extracted_tokens_dir: Path,
        output_v2_dir: Path,
        tts_objects_dir: Path,
        tts_token_json_dir: Path,
    ) -> None:
        self.project_root = project_root
        self.config_path = config_path
        self.extracted_tokens_dir = extracted_tokens_dir
        self.output_v2_dir = output_v2_dir
        self.tts_objects_dir = tts_objects_dir
        self.tts_token_json_dir = tts_token_json_dir

    def _load_team_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("teams", {}) or {}

    def iter_team_statuses(self, team_filter: Optional[Iterable[str]] = None) -> list[TeamTokenStatus]:
        cfg = self._load_team_config()
        allow = set(team_filter) if team_filter else None

        out: list[TeamTokenStatus] = []
        for team, data in cfg.items():
            if allow is not None and team not in allow:
                continue
            out.append(
                TeamTokenStatus(
                    team=team,
                    canonical_name=str(data.get("canonical_name") or team.replace("-", " ").title()),
                    faction=str(data.get("faction") or "unknown"),
                    tokens_ready=bool(data.get("tokens_ready", False)),
                )
            )
        return out

    def _team_box_file(self, canonical_name: str) -> Path:
        # Matches existing naming in tts_objects.
        return self.tts_objects_dir / f"{canonical_name} Cards.json"

    def embed_ready_tokens(
        self,
        team_filter: Optional[Iterable[str]] = None,
        *,
        force_overwrite_ready: bool = False,
    ) -> dict[str, int]:
        """Package tokens into output_v2 and embed for tokens_ready teams.

        Returns counts: {ready, packaged, embedded, skipped_missing}
        """
        statuses = self.iter_team_statuses(team_filter=team_filter)
        ready = [s for s in statuses if s.tokens_ready]

        embedded = 0
        packaged = 0
        skipped_missing = 0

        token_generator = TTSTokenGenerator(team_config_path=self.config_path)
        bag_generator = TeamTokenBagGenerator(team_config_path=self.config_path)

        for s in statuses:
            meta = self.extracted_tokens_dir / s.team / "extraction-metadata.json"
            if not meta.exists():
                skipped_missing += 1
                continue

            # Generate assets + per-token JSONs.
            # - Unready teams: overwrite to reflect ongoing tuning.
            # - Ready teams: do not overwrite assets (treat as immutable), unless we're
            #   doing a one-time migration (e.g. new canvas normalization).
            tokens_data = token_generator.generate_individual_tokens(
                team_name=s.team,
                metadata_file=meta,
                token_images_dir=self.extracted_tokens_dir,
                output_dir=self.output_v2_dir,
                overwrite_assets=(not s.tokens_ready) or (force_overwrite_ready and s.tokens_ready),
            )
            packaged += 1

            # Write individual token bags to tts_objects/tokens/<team>/ (only if missing)
            team_json_dir = self.tts_token_json_dir / s.team
            team_json_dir.mkdir(parents=True, exist_ok=True)

            for t in tokens_data:
                json_output_file = team_json_dir / t["filename"]
                if s.tokens_ready and json_output_file.exists() and not force_overwrite_ready:
                    continue

                tts_save = {
                    "SaveName": "",
                    "Date": "",
                    "VersionNumber": "",
                    "GameMode": "",
                    "GameType": "",
                    "GameComplexity": "",
                    "Tags": [],
                    "Gravity": 0.5,
                    "PlayArea": 0.5,
                    "Table": "",
                    "Sky": "",
                    "Note": "",
                    "TabStates": {},
                    "LuaScript": "",
                    "LuaScriptState": "",
                    "XmlUI": "",
                    "ObjectStates": [t["bag"]],
                }

                with open(json_output_file, "w", encoding="utf-8") as f:
                    json.dump(tts_save, f, indent=2)

            # Create a single team token bag under output_v2/<faction>/<team>/tts/token/<team>-tokens.json
            # (This is the bag we embed into the team box.)
            token_objs = [t["token"] for t in tokens_data]
            team_bag = bag_generator.generate_team_bag(s.team, token_objs)
            bag_save = {
                "SaveName": "",
                "Date": "",
                "VersionNumber": "",
                "GameMode": "",
                "GameType": "",
                "GameComplexity": "",
                "Tags": [],
                "Gravity": 0.5,
                "PlayArea": 0.5,
                "Table": "",
                "Sky": "",
                "Note": "",
                "TabStates": {},
                "LuaScript": "",
                "LuaScriptState": "",
                "XmlUI": "",
                "ObjectStates": [team_bag],
            }

            token_out_dir = self.output_v2_dir / s.faction / s.team / "tts" / "token"
            token_out_dir.mkdir(parents=True, exist_ok=True)
            token_bag_file = token_out_dir / f"{s.team}-tokens.json"
            # Ready teams: if the bag already exists, keep it.
            # Unready teams: overwrite so token membership stays in sync.
            if (not s.tokens_ready) or force_overwrite_ready or (not token_bag_file.exists()):
                with open(token_bag_file, "w", encoding="utf-8") as f:
                    json.dump(bag_save, f, indent=2)

            # Embed into the team's main box only when the team is ready.
            if s.tokens_ready:
                box_file = self._team_box_file(s.canonical_name)
                if not box_file.exists():
                    skipped_missing += 1
                    continue

                ok = add_tokens_to_box(box_file, token_bag_file)
                if ok:
                    embedded += 1

        return {
            "ready": len(ready),
            "packaged": packaged,
            "embedded": embedded,
            "skipped_missing": skipped_missing,
        }
