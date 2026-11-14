# Mistral cache replay (generated)

User answer: the last run was not meant to use Mistral, so the error PDFs were not a configuration regression.

- distinct error file_urls: 354 (non-pdf skipped: 26, no transform record: 1)
- error PDFs: 327
- with Mistral cache hit: 208
- cached, clean via Mistral: 74
- cached, clean via current: 78
- cached, clean via both: 52
- cached, clean via neither: 108
- Mistral only: 22; current only: 26

## Top 10 bodies by error count (cached PDFs only in the clean columns)

| body | id | errors | error PDFs | cached | mistral | current | both | neither |
|---|---|---|---|---|---|---|---|---|
| Raidió Teilifís Éireann - RTÉ | 1655 | 565 | 33 | 0 | 0 | 0 | 0 | 0 |
| Fingal County Council | 1295 | 552 | 5 | 5 | 0 | 0 | 0 | 5 |
| Tipperary County Council | 1817 | 150 | 22 | 21 | 12 | 5 | 4 | 8 |
| Waterford City and County Council | 1864 | 114 | 1 | 0 | 0 | 0 | 0 | 0 |
| An Coimisiún Pleanála | 1010 | 112 | 8 | 3 | 0 | 0 | 0 | 3 |
| City of Dublin Education and Training Board | 1122 | 103 | 7 | 0 | 0 | 0 | 0 | 0 |
| Department of Rural and Community Development and the Gaeltacht | 1210 | 96 | 11 | 0 | 0 | 0 | 0 | 0 |
| Comptroller and Auditor General | 1157 | 96 | 1 | 0 | 0 | 0 | 0 | 0 |
| Leitrim County Council | 1475 | 81 | 7 | 7 | 1 | 0 | 0 | 6 |
| Department of Defence | 1200 | 63 | 6 | 6 | 1 | 1 | 1 | 5 |

## Failed checks among cached PDFs

- current column_type_purity: 3
- current fragment_share: 79
- current repeated_header_share: 6
- current split_word_rate: 73
- current width_uniformity: 98
- mistral fragment_share: 37
- mistral repeated_header_share: 56
- mistral split_word_rate: 52
- mistral width_uniformity: 75

Current extractor among error PDFs: {'pdfplumber': 282, 'camelot_stream': 45}
