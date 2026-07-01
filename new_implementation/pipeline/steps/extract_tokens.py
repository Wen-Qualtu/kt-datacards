"""Tokens — one-off per team. Needs the content map + the artwork layer.

content map (which card / token-guide to read) + layers/integration/{team}/artwork (token-bag image)
   ->  output/{team}/tokens/{name}.png

PORT-FROM: pipelines/kt-app/utils/token_extractor.py  (TokenExtractor; reusable)
SOURCE-DECISION: USE kt-app's shared TokenExtractor. warcom step 4 is an inline
  DUPLICATE with a different API — drop it in favour of the shared util.
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("extract_tokens.run: use pipelines/kt-app/utils/token_extractor.py (TokenExtractor)")
