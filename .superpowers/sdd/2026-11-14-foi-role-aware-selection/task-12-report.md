# Task 12 report
Status: done. Commits: f1b6301d (cleanups, pdfplumber_lines removal, tests), plus results commit (see git log).
Tests: 1841 passed; pyright 0 errors.
Handoff: docs/handoff-foi-role-aware-selection-results.md (leads with gate blast radius and options).
Step 2 measure: 3,228 of 56,850 records with no reference and no dates (spec: 3,354 of 59,600).
Measurements: pipelines/foi_pipeline/experiments/2026-11-14-pdf-extractor-bakeoff/{final_measures.py,results/task12_final_measures.md}.
Concerns: newly gated files counted 66 (63 gate + 2 override + Fingal 2016 flagged-but-shielded), 29 with 0 errors and records (not ~40); errors do not always drop rows (1,185 records carry known_issues), so the >=20%/>=50% counts differ by definition (both given); option C/D not measured; "probably good" files not eyeballed; docs/ is gitignored here so the handoff was force-added.
