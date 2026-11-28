# Review of the rendered Kildare and Westmeath meetings

Reviewed on 2026-11-27 against the source PDFs (task 7.6). Nine of the eleven
meetings render; the two that do not are listed under "Not rendered".

## Method

- All nine attendance blocks: the PDF image beside the parsed names (page 1).
- Body: page 5 of Kildare 11 December 2025 against its rendered item 4, plus a
  read of the rendered Markdown of the others for structure.
- Every meeting passes the word check, which proves the render equals the OCR
  words, not the printed page. This review is the check on the OCR itself.

## Findings

OCR misreads found in names, fixed as register aliases (the design's remedy;
the canonical name is the printed one):

| Meeting | Printed | OCR read | Remedy |
|---|---|---|---|
| Kildare 8 May 2025 | Paul Ward | `Pau! Ward` | alias |
| Kildare 21 May 2026 | Noel Connolly | `Noel Connelly` | alias |
| Westmeath 19 Sep 2025 | Cllr. Frankie Keena | `Cilr. Frankie Keena` | alias |
| Kildare (several) | Dónal Hodgins, Carthac De Brí | accents dropped | canonical name keeps the accent; unaccented form is an alias |

Other observations, none of which is a defect in the pipeline:

- **Bullet glyphs are read as letters and symbols** (`e`, `«`, `\>`, `\>»`) in
  Kildare's slide-style bullet lists, so a presentation item is one long
  paragraph. The words are the OCR words; the structure is lost. This is the
  accepted "verbatim to the OCR" limit; the source PDF is authoritative.
- **OCR misreads inside body text** exist (for example `Dénal` for `Dónal`).
  High-confidence misreads pass every gate by design; the published
  `text_source` and the source sha256 say so.
- **Signature scribbles** are read as noise tokens at the end of some meetings
  (`Arce, Q Ale alt`, `Ur rankie Keena`) and a blue tick after
  `(Cathaoirleach)` became a stray `a` in a role. Kept, as source text.
- Westmeath 19 September 2025 prints `Item 3` twice (the second is almost
  certainly `Item 4`); the second heading is anchored `item-3-2`.
- Westmeath 6 March 2026 has a text layer on pages 1 to 3; page 4 was OCR'd and
  recovered real text (136 words, mean confidence 90.0), so no override is
  needed there.

## Not rendered

- **Westmeath 28 November 2025**: its last page is a blank sheet whose speckle
  OCR reads as three junk words (mean confidence 13.7), so the file fails the
  confidence gate. Open question for the user.
- **Westmeath 13 February 2025**: the header prints no year. Open question for
  the user.

## Attendance withheld

- **Kildare 6 February 2025**: `Mr. Joseph Knox` is not registered. The sources
  do not say whether he is a sectoral representative or a guest, so his kind is
  not guessed; the meeting's attendance is withheld and its minutes publish.
