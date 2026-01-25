# Processing Scripts

Scripts for processing raw PDFs and extracting card images.

## Scripts

### `process_pdfs.py`
Processes raw PDF files and identifies team names.
- **Input**: PDFs in `input/` directory (recursive)
- **Output**: Processed PDFs in `processed/` with team identification
- **Used by**: Pipeline step 1 (`--step process`)

### `extract_images.py`
Extracts individual card images from processed PDFs.
- **Input**: Processed PDFs in `processed/`
- **Output**: Card images in `processed/{team-name}/`
- **Used by**: Pipeline step 2 (`--step extract`)

## Usage

These scripts are part of the main pipeline but can be run individually:

```bash
# Process raw PDFs
python script/processing/process_pdfs.py

# Extract images from processed PDFs
python script/processing/extract_images.py

# Or use the pipeline
python script/run_pipeline.py --step process
python script/run_pipeline.py --step extract
```

## Workflow

1. Place raw PDFs in `input/` directory (any subdirectory structure works)
2. Run `process_pdfs.py` to identify and process PDFs
3. Run `extract_images.py` to extract card images
4. Continue with rest of pipeline (backsides, URLs, etc.)
