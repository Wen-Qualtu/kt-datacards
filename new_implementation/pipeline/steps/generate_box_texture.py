"""Box texture — one-off per team, derived from the artwork layer. TTS-only.

layers/integration/{team}/artwork + config  ->  output/{team}/cardbox/texture.jpg (+ .obj)

PORT-FROM: pipelines/kt-app/steps/5c_generate_box_textures.py
SOURCE-DECISION: kt-app only (warcom has no box-texture step).
  Prioritized icon sources (manual override -> auto-gen -> default); CANVAS 714x585.
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("generate_box_texture.run: port from pipelines/kt-app/steps/5c_generate_box_textures.py")
