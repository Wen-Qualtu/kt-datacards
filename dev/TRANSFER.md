# Transfer Notes (Feb 9, 2026)

## Context
- Work is on the warcom pipeline and TTS object generation.
- Step 5 (warcom) was updated to generate cardbox, decks, cards, token bag, dispensers, and tokens with metadata + hash-based timestamps.
- Lua scripts are pulled from config/defaults/tts-script and config/defaults/tts-token and tracked as metadata components.
- Output targets are output/{team}/tts and output/.tts-*.json.

## Changes made
- pipelines/warcom/steps/5_generate_tts_objects.py
  - Added token generation (TTSToken, TTSTokenDispenser, TTSTokenBag).
  - Added Lua script tracking + output to output/{team}/tts/cardbox/.../lua-script.lua.
  - Added safe metadata timestamp aggregation for tokens.
  - Added logging + --log-level; registry honors --force.
- pipelines/warcom/steps/4_token_extraction.py
  - Fixed tools path (root/tools).
  - Added logging and early exit if tokens already exist.
- pipelines/warcom/steps/2_card_extractor.py
  - Added safe file removal helpers; replaced prints with logging.
  - Safe unlink before overwriting PDFs/PNGs/icons.
  - Added readonly-safe rmtree when cleaning team outputs.
- pipelines/warcom/steps/3_card_classification.py
  - Added safe file removal helpers; safe unlink before writing front/back images.
  - Added readonly-safe rmtree for team output cleanup.
- pipelines/warcom/steps/TTS_GENERATION_DESIGN.md
  - Updated output paths to output/{team}/tts and output/.tts-*.json.
  - Updated file structure and URLs.

## Pipeline run status
- Full pipeline run was started multiple times.
- Last run reached Step 4 and completed, but Step 2 and Step 3 saw WinError 5 access denied on a few files.
- Step 4 initially skipped tokens because it searched for token-guide cards in layers/warcom/extracted/{team}/cards; after changes, it now short-circuits if tokens already exist.

## Outstanding issues
1. WinError 5 access denied during Step 2 / Step 3 file writes (likely due to file locks). We added safe unlink + readonly cleanup but need to re-run to validate.
2. Step 4 token extraction currently skips if tokens already exist (intended to avoid rework). If you want a forced refresh, add a flag later.

## Environment actions taken
- Updated pyproject.toml python constraint to ^3.11.
- Ran:
  - poetry add numpy@^2.1.0 (now numpy 2.4.2, opencv-python 4.13.0.92)
  - poetry install
  - poetry run playwright install
- Re-ran: poetry run python pipelines/warcom/pdf_process_pipeline.py --all (user cancelled once; later run continued but still hit WinError 5).

## Notes from user
- Use Poetry only (no pip).
- Do not do one-off fixes; update pipeline scripts instead.
- Any helper/test scripts should live in dev/.

## Git note
- User hit: .git/index.lock exists when running git add. Remove lock only if sure no other git process is running.

## Next steps
1. Re-run full pipeline:
   - poetry run python pipelines/warcom/pdf_process_pipeline.py --all
2. Confirm Step 2/3 no longer hit WinError 5.
3. If still failing, add retry/backoff around PDF/JPG writes in steps 2/3.
4. Run Step 5 for TTS objects once pipeline is clean:
   - poetry run python pipelines/warcom/steps/5_generate_tts_objects.py
