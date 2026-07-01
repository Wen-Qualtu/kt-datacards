"""Stats / team data — from the content map.

layers/integration/{team}/content/{team}-content.json  ->  output/{team}/data/{team}-team-data.json

PORT-FROM: pipelines/kt-app/steps/3_extract_team_data.py (the serialization half).
SOURCE-DECISION: kt-app. May fold into content_analysis if the split proves redundant.
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("extract_stats.run: serialize content map -> output/{team}/data")
