"""Standalone warcom front-end helpers (scrape + per-card PDF extraction).

This is a clean, self-contained port of the warcom card-extraction logic. It does
NOT import or execute the legacy ``pipelines/warcom/steps`` scripts — the new
pipeline is a standalone implementation.

Scope of this package:
  - ``scraper``        : fetch + download team-rules PDFs from warhammer-community
  - ``card_extractor`` : split a team-rules PDF into per-card PDFs (PDF only)

Token extraction is intentionally NOT here. Tokens are produced once per team by
the shared ``extract_tokens`` step.
"""
