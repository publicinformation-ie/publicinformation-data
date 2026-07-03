# Mistral OCR vs pdfplumber Comparison Experiment

**Date:** 2025-01-03
**Status:** In Progress

## Hypothesis

Mistral OCR API with markdown table format will produce comparable or better table extraction results than pdfplumber for FOI disclosure log PDFs, with fewer null cells and requiring fewer normalization changes.

## Methodology

1. Sample 10 verified PDFs from `verify_disclosure_files/output.json`
2. Extract tables using both Mistral OCR (markdown format) and pdfplumber
3. Convert Mistral markdown tables to pipeline `rows` format
4. Run both outputs through `normalize_disclosure_cells`
5. Compare metrics: row count, column count, null cells, cell match rate

## Results

**Status:** Implementation complete, awaiting execution with MISTRAL_API_KEY

See `comparison.json` for detailed metrics after running the experiment.

## Conclusion

TBD - Will be updated after running the full experiment with Mistral OCR API access.

## Running the Experiment

To run the full experiment:

1. Ensure you have a Mistral OCR API key
2. Set the environment variable: `export MISTRAL_API_KEY=your_key_here`
3. Run the experiment:
   ```bash
   cd pipelines/foi_pipeline/experiments/2025-01-03-mistral-ocr-comparison
   python sample.py  # Already run, sample.json is committed
   MISTRAL_API_KEY=your_key_here python run.py
   ```

4. Results will be saved in the `results/` directory
5. Update this README with the actual results from `comparison.json`

## Reproduction

```bash
cd pipelines/foi_pipeline/experiments/2025-01-03-mistral-ocr-comparison
python sample.py
python run.py
```

## Files

- `sample.json` - The 10 selected PDFs (committed for reproducibility)
- `results/mistral_raw.json` - Raw Mistral OCR output
- `results/pdfplumber_raw.json` - Raw pdfplumber output
- `results/mistral_normalized.json` - After normalization
- `results/pdfplumber_normalized.json` - After normalization
- `results/comparison.json` - Aggregate metrics
