"""Per-team pipeline state + a derived global index.

Shared by every downstream step so they all record their outputs the same way.

- ``StateManager(team)`` owns ``layers/integration/{team}/{team}-pipeline-state.json``.
  It is loaded then rewritten wholly per run for that team, so there are never
  stale cross-team keys.
- ``StateIndex`` rebuilds the global ``layers/integration/pipeline-state.json`` by
  scanning the per-team files, so it stays authoritative automatically.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from . import paths


def _atomic_write_json(path: Path, data) -> None:
    """Write JSON to ``path`` atomically (temp file + os.replace).

    Safe when several threads write different files concurrently and, for the
    global index, when concurrent rebuilds race — os.replace swaps the file in
    one step so readers never see a half-written file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


class StateManager:
    """Per-team pipeline state: step completion + input/output hashes.

    One file per team at ``layers/integration/{team}/{team}-pipeline-state.json``.
    Loaded then rewritten wholly per run for that team, so there are never stale
    cross-team keys.

    Each step records the hash signature of the files it consumed (``inputs``) and
    produced (``outputs``). On the next run a step is skipped (via ``can_skip``)
    when ``--force`` is off, its inputs are byte-for-byte unchanged, and its
    recorded outputs still exist. Because a skipped step leaves its outputs
    untouched, the following step sees unchanged inputs and skips too — so "nothing
    changed upstream" propagates down the chain without any cross-step signalling.
    """

    def __init__(self, team: str):
        self.team = team
        self.state_file = paths.pipeline_state_file(team)
        self.state = self._load()

    def _load(self) -> Dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "team": self.team,
            "pipeline_version": "2.0",
            "last_updated": None,
            "steps": {},
        }

    @staticmethod
    def _compute_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _rel(file_path: Path) -> str:
        """Workspace-relative, forward-slash path (falls back to the raw string)."""
        try:
            return str(Path(file_path).resolve().relative_to(paths.ROOT.resolve())).replace("\\", "/")
        except ValueError:
            return str(file_path).replace("\\", "/")

    def _signature(self, input_paths) -> Dict[str, str]:
        """{rel_path: sha256} for every existing input file (order-independent)."""
        sig: Dict[str, str] = {}
        for p in input_paths:
            p = Path(p)
            if p.is_file():
                sig[self._rel(p)] = self._compute_hash(p)
        return sig

    def record_output(self, step: str, file_key: str, file_path: Path):
        """Record hash + workspace-relative path of a step output."""
        step_entry = self.state["steps"].setdefault(step, {"outputs": {}})
        step_entry.setdefault("outputs", {})[file_key] = {
            "path": self._rel(file_path),
            "hash": self._compute_hash(file_path),
            "modified": datetime.now(timezone.utc).isoformat(),
        }

    # --- incremental change-detection -------------------------------------
    # Each step records the hash signature of the files it consumed (its
    # inputs). On the next run a step is skipped when its inputs are byte-for-byte
    # unchanged AND its recorded outputs are still on disk. Because a skipped step
    # leaves its outputs untouched, the next step sees unchanged inputs and skips
    # too — so "nothing changed upstream" naturally propagates down the chain.
    def record_inputs(self, step: str, input_paths) -> None:
        """Record the hash signature of a step's input files for change detection."""
        step_entry = self.state["steps"].setdefault(step, {"outputs": {}})
        step_entry["inputs"] = self._signature(input_paths)

    def inputs_unchanged(self, step: str, input_paths) -> bool:
        """True only if a prior signature exists and equals the current inputs."""
        prior = self.state["steps"].get(step, {}).get("inputs")
        if not prior:
            return False
        return self._signature(input_paths) == prior

    def outputs_present(self, step: str) -> bool:
        """True if the step recorded outputs and all of them still exist on disk."""
        outs = self.state["steps"].get(step, {}).get("outputs")
        if not outs:
            return False
        return all((paths.ROOT / meta["path"]).exists() for meta in outs.values())

    def can_skip(self, step: str, input_paths, force: bool) -> bool:
        """Skip when not forcing, inputs are unchanged, and outputs still exist."""
        if force:
            return False
        return self.inputs_unchanged(step, input_paths) and self.outputs_present(step)

    # --- consumed-source change-detection ---------------------------------
    # Front-end steps consume their inputs: the source PDF is archived (moved out
    # of the inbox) after splitting, so its path is not stable across runs. These
    # steps gate on the source's *content* hash instead of its path: re-dropping a
    # byte-identical PDF (e.g. after re-populating the inbox) is skipped as long as
    # the outputs it produced are still on disk. A logical ``key`` (card type,
    # "artwork", …) lets one team track several independent sources.
    def record_source(self, step: str, key: str, content_hash: str, output_paths) -> None:
        """Record a consumed source's content hash and the outputs it produced."""
        step_entry = self.state["steps"].setdefault(step, {"outputs": {}})
        srcs = step_entry.setdefault("sources", {})
        srcs[key] = {
            "hash": content_hash,
            "outputs": [self._rel(p) for p in output_paths],
            "modified": datetime.now(timezone.utc).isoformat(),
        }

    def source_can_skip(self, step: str, key: str, content_hash: str, force: bool) -> bool:
        """Skip a consumed source when not forcing, its content is unchanged, and
        every output it produced still exists on disk."""
        if force:
            return False
        rec = self.state["steps"].get(step, {}).get("sources", {}).get(key)
        if not rec or rec.get("hash") != content_hash:
            return False
        return all((paths.ROOT / p).exists() for p in rec.get("outputs", []))

    def mark_complete(self, step: str):
        """Mark a step as completed for this team."""
        step_entry = self.state["steps"].setdefault(step, {"outputs": {}})
        step_entry["completed"] = datetime.now(timezone.utc).isoformat()

    def save(self):
        """Write the per-team state file (atomically)."""
        self.state["last_updated"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_json(self.state_file, self.state)


class StateIndex:
    """Global registry at ``layers/integration/pipeline-state.json``.

    Lists every team with a pointer to its per-team state file and that team's
    ``last_updated``, plus a global ``last_run``. Rebuilt by scanning the per-team
    state files, so it is always authoritative and never holds stale team keys.
    """

    def __init__(self):
        self.index_file = paths.PIPELINE_STATE_INDEX

    def rebuild_and_save(self):
        teams: Dict[str, Dict] = {}
        if paths.INTEGRATION.exists():
            for team_dir in sorted(paths.INTEGRATION.iterdir()):
                if not team_dir.is_dir():
                    continue
                state_path = paths.pipeline_state_file(team_dir.name)
                if not state_path.exists():
                    continue
                last_updated = None
                try:
                    with open(state_path, 'r', encoding='utf-8') as f:
                        last_updated = json.load(f).get("last_updated")
                except Exception:
                    pass
                rel = str(state_path.relative_to(paths.ROOT)).replace("\\", "/")
                teams[team_dir.name] = {"state": rel, "last_updated": last_updated}

        index = {
            "pipeline_version": "2.0",
            "last_run": datetime.now(timezone.utc).isoformat(),
            "teams": teams,
        }
        _atomic_write_json(self.index_file, index)
