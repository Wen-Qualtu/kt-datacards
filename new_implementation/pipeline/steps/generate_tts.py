"""TTS assets + objects — LAST step. Consumes cards, stats, tokens, dice, box texture.

output/{team}/{cards,data,tokens,dice,cardbox}  ->  output/{team}/tts_objects/{Team}.json

PORT-FROM:
  - assets:  pipelines/kt-app/steps/6_generate_tts_assets.py
  - objects: pipelines/kt-app/steps/7_generate_tts_objects.py
SOURCE-DECISION: USE kt-app step 7 (bare/legacy dual format, embedded stats + Lua,
  stable hashing, persistent GUIDs). warcom step 5 is metadata-only — dropped.
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("generate_tts.run: port from pipelines/kt-app/steps/{6_generate_tts_assets,7_generate_tts_objects}.py")
