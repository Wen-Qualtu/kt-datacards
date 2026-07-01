"""Backside extraction — one-off per team, consumes the artwork layer.

layers/integration/{team}/artwork/...  ->  output/{team}/card-backside/{landscape,portrait}.jpg

Predecessor for card image processing. NOT stored in the classified folder
(an earlier copy landed in the wrong path; that is being removed).

PORT-FROM: pipelines/kt-app/steps/5d_generate_card_backsides.py
SOURCE-DECISION: kt-app only (warcom has no separate backside pre-generation).
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("extract_backsides.run: port from pipelines/kt-app/steps/5d_generate_card_backsides.py")
