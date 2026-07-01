"""Dice textures — one-off per team, derived from the artwork layer. TTS-only.

layers/integration/{team}/artwork + config  ->  output/{team}/dice/{light,dark,team}.jpg

PORT-FROM: pipelines/kt-app/steps/5b_generate_dice.py
SOURCE-DECISION: USE kt-app 5b (warcom 4a is nearly identical but lacks the
  team-color variant). FACE_COORDS / 2048x2048 grid carry over.
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("generate_dice.run: port from pipelines/kt-app/steps/5b_generate_dice.py")
