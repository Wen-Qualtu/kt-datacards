# Token Scripts

Scripts for token bag extraction and processing.

## Scripts

### `extract_token_bags.py`
Extracts token bags from team card boxes into separate JSON files.
- **Input**: `output_v2/{team-name}.json` (card box files)
- **Output**: `processed/extracted-tokens/{team-name}-tokens.json`
- **Purpose**: Separate token management from card boxes

## Usage

Extract all token bags:
```bash
python script/tokens/extract_token_bags.py
```

Extract for specific teams:
```bash
python script/tokens/extract_token_bags.py --teams kasrkin blooded
```
