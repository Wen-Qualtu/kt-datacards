"""Card image processing — needs the content map + backsides.

layers/shared/integration/{team}-*.pdf (front) + backsides + content map
   ->  output/{team}/cards/{type}/{name}.jpg (+ back)

PDF -> JPEG (300 DPI); compose with the pre-generated backside; fall back to
default backsides where needed.

PORT-FROM: pipelines/kt-app/steps/4_extract_card_images.py
SOURCE-DECISION: kt-app (warcom 3_card_classification.py did OCR-based classification +
  inpainting straight to output; we instead drive off the shared classified + content map).
"""
from __future__ import annotations


def run(teams=None, source=None, force=False):
    raise NotImplementedError("generate_card_images.run: port from pipelines/kt-app/steps/4_extract_card_images.py")
