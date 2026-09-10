## Purpose

Extracts text from image-only council meeting minutes PDFs (scanned documents with no embedded text layer) so that motions can be extracted downstream.

## Requirements

### Requirement: Image-only minutes are OCR'd
The system SHALL run optical character recognition on a minutes record whose extracted text is empty, rendering each page to an image and recognizing text from it.

#### Scenario: Scanned minutes produce OCR text
- **WHEN** a minutes PDF has no text layer and OCR recognizes text on its pages
- **THEN** the record is emitted with `text` set to the recognized text and `extractor` set to the OCR engine identifier

#### Scenario: Empty page contributes nothing
- **WHEN** a page of an image-only PDF is blank or yields no recognized text
- **THEN** that page contributes no text, and other pages' text is still joined into the record

### Requirement: Non-empty records pass through unchanged
The system SHALL leave records that already have non-empty extracted text untouched, preserving their existing `text` and `extractor` values.

#### Scenario: Text-layer PDF is not re-OCR'd
- **WHEN** a minutes record already has non-empty `text`
- **THEN** the record is emitted as-is, with its original `text` and `extractor`, and no OCR is performed

### Requirement: Fail-closed on unresolved extraction
The system SHALL NOT drop, null, or guess a record whose text cannot be reconstructed. If OCR also yields no text, or OCR raises an error, the system SHALL emit the record with empty `text` and record an explicit error identifying the file.

#### Scenario: OCR yields no text
- **WHEN** OCR runs on an image-only record but produces no text
- **THEN** the record is emitted with empty `text` and an error is logged for that file

#### Scenario: OCR raises an error
- **WHEN** OCR fails with an exception for a record
- **THEN** the record is emitted with empty `text` and an error is logged for that file

### Requirement: Single merged output
The system SHALL emit a single output list containing every input record exactly once, whether passed through or OCR'd, so the downstream step consumes one unified source.

#### Scenario: One record per file in merged output
- **WHEN** the step processes an input list containing text-layer and image-only records
- **THEN** the output contains exactly one record per input file, with no file dropped or duplicated
