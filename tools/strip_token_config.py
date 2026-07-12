"""Strip pre-baked token data from the sandbox team-config.

Removes, for every team:
  - the ``tokens_ready`` flag key
  - the ``tokens`` list (pre-baked token names/shapes/types)

Everything else (faction, dice colors, faction_rule, aliases, ...) is kept.
This forces the pipeline to regenerate tokens from scratch off the integration
manifest instead of relying on baked config.

Operates ONLY on the sandbox copy: new_implementation/config/team-config.yaml.

Run:  python tools/strip_token_config.py   (from new_implementation/)
"""
from __future__ import annotations

from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config" / "team-config.yaml"

REMOVE_KEYS = ("tokens", "tokens_ready")


def main() -> None:
    data = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    teams = data.get("teams", {})

    removed_flag = removed_tokens = 0
    for _team, cfg in teams.items():
        if not isinstance(cfg, dict):
            continue
        if "tokens_ready" in cfg:
            del cfg["tokens_ready"]
            removed_flag += 1
        if "tokens" in cfg:
            del cfg["tokens"]
            removed_tokens += 1

    CONFIG.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    print(f"teams processed         : {len(teams)}")
    print(f"tokens_ready removed     : {removed_flag}")
    print(f"tokens list removed      : {removed_tokens}")
    # Verify nothing slipped through.
    check = CONFIG.read_text(encoding="utf-8")
    print(f"remaining 'tokens_ready' : {check.count('tokens_ready')}")
    print(f"remaining 'tokens:'      : {check.count('tokens:')}")


if __name__ == "__main__":
    main()
