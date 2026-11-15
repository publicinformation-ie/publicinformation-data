# Round: 1594-non-personal-2017-2020

Winner: gate-dd-mon-yy

| fix | kind | scope | files_resolved | files_gate_pass | records_recovered | errors_after | gold_accuracy | cluster_gold | agreement | controls_worse | controls_differ | not_run | seconds_per_file | disqualified |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| current | baseline | routed | 0 | 0 | 0 | 7 | 0.9537 | 1.0 | 0.9922 | 0 | 0 | 0 | 0.0 | no |
| force:pdfplumber | config | routed | 0 | 0 | 0 | 7 | 0.7372 | 1.0 | 0.9929 | 7 | 7 | 0 | 0.411 | no |
| force:pymupdf | config | routed | 0 | 0 | 0 | 7 | 0.6762 | 1.0 | 0.995 | 7 | 9 | 1 | 0.503 | no |
| force:camelot_lattice | config | routed | 0 | 0 | 0 | 7 | 0.7811 | 1.0 | 0.9943 | 4 | 8 | 1 | 3.218 | no |
| force:camelot_stream | config | routed | 0 | 0 | 0 | 19 | 0.4566 | 0.875 | 0.8344 | 6 | 8 | 0 | 0.623 | no |
| force:mistral_cache | config | routed | 0 | 0 | 0 | 6 | 0.652 | 0.9833333333333333 | 0.8654 | 7 | 8 | 7 | 0.002 | no |
| docling | candidate | routed | 0 | 0 | 0 | 7 | 0.9209 | 1.0 | 0.9564 | 2 | 10 | 0 | 0.001 | no |
| gate-dd-mon-yy | gate | global | 4 | 4 | 568 | 7 | 0.9537 | 1.0 | 0.9922 | 0 | 0 | 0 | 0.0 | no |

| file | fix | status | gate | failed checks | records | errors | best agreement | agrees with | resolved |
|---|---|---|---|---|---|---|---|---|---|
| Department of Foreign Affairs and Trade (control) | current | ok | yes |  | 20 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | force:pdfplumber | ok | yes |  | 20 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | force:pymupdf | ok | no | width_uniformity, fragment_share, role_contamination, anchored_row_share | 5 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | force:camelot_lattice | ok | yes |  | 20 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | force:camelot_stream | ok | no | width_uniformity, fragment_share, anchored_row_share | 26 | 4 |  |  |  |
| Department of Foreign Affairs and Trade (control) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | docling | ok | yes |  | 20 | 0 |  |  |  |
| Department of Foreign Affairs and Trade (control) | gate-dd-mon-yy | ok | yes |  | 20 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | current | ok | yes |  | 31 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | force:pdfplumber | ok | no | width_uniformity, fragment_share, split_word_rate, role_contamination, anchored_row_share | 28 | 4 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | force:pymupdf | ok | no | width_uniformity, fragment_share, split_word_rate, role_contamination, anchored_row_share | 84 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | force:camelot_lattice | ok | yes |  | 31 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | force:camelot_stream | ok | no | fragment_share, anchored_row_share | 41 | 11 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | docling | ok | yes |  | 31 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (control) | gate-dd-mon-yy | ok | yes |  | 31 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | current | ok | yes |  | 24 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | force:pdfplumber | ok | no | fragment_share | 27 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | force:pymupdf | ok | yes |  | 24 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | force:camelot_lattice | ok | yes |  | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | force:camelot_stream | ok | no | width_uniformity, fragment_share, anchored_row_share | 31 | 2 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | docling | ok | yes |  | 24 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (control) | gate-dd-mon-yy | ok | yes |  | 24 | 0 |  |  |  |
| Central Bank of Ireland (control) | current | ok | yes |  | 44 | 0 |  |  |  |
| Central Bank of Ireland (control) | force:pdfplumber | ok | no | width_uniformity, fragment_share, column_type_purity, split_word_rate | 0 | 0 |  |  |  |
| Central Bank of Ireland (control) | force:pymupdf | ok | no | width_uniformity, fragment_share, column_type_purity, split_word_rate | 0 | 0 |  |  |  |
| Central Bank of Ireland (control) | force:camelot_lattice | no_table | no |  | 0 | 0 |  |  |  |
| Central Bank of Ireland (control) | force:camelot_stream | ok | no | width_uniformity, fragment_share | 49 | 0 |  |  |  |
| Central Bank of Ireland (control) | force:mistral_cache | ok | yes |  | 44 | 0 |  |  |  |
| Central Bank of Ireland (control) | docling | ok | yes |  | 44 | 0 |  |  |  |
| Central Bank of Ireland (control) | gate-dd-mon-yy | ok | yes |  | 44 | 0 |  |  |  |
| Mayo County Council (control) | current | ok | yes |  | 27 | 0 |  |  |  |
| Mayo County Council (control) | force:pdfplumber | ok | no | role_contamination | 27 | 0 |  |  |  |
| Mayo County Council (control) | force:pymupdf | ok | no | width_uniformity, role_contamination | 27 | 13 |  |  |  |
| Mayo County Council (control) | force:camelot_lattice | ok | no | role_contamination | 27 | 0 |  |  |  |
| Mayo County Council (control) | force:camelot_stream | ok | yes |  | 27 | 0 |  |  |  |
| Mayo County Council (control) | force:mistral_cache | ok | no | role_contamination | 27 | 0 |  |  |  |
| Mayo County Council (control) | docling | ok | no | role_contamination | 27 | 0 |  |  |  |
| Mayo County Council (control) | gate-dd-mon-yy | ok | yes |  | 27 | 0 |  |  |  |
| Offaly County Council (control) | current | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | force:pdfplumber | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | force:pymupdf | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | force:camelot_lattice | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | force:camelot_stream | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Offaly County Council (control) | docling | ok | yes |  | 67 | 0 |  |  |  |
| Offaly County Council (control) | gate-dd-mon-yy | ok | yes |  | 67 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | current | ok | yes |  | 82 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | force:pdfplumber | ok | no | width_uniformity | 87 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | force:pymupdf | ok | no | width_uniformity, fragment_share, anchored_row_share | 91 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | force:camelot_lattice | ok | yes |  | 82 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | force:camelot_stream | ok | no | fragment_share | 65 | 8 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | force:mistral_cache | ok | yes |  | 82 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | docling | ok | yes |  | 82 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (control) | gate-dd-mon-yy | ok | yes |  | 82 | 0 |  |  |  |
| National University of Ireland Galway (control) | current | ok | yes |  | 48 | 0 |  |  |  |
| National University of Ireland Galway (control) | force:pdfplumber | ok | no | width_uniformity, role_contamination | 48 | 0 |  |  |  |
| National University of Ireland Galway (control) | force:pymupdf | ok | no | width_uniformity, anchored_row_share | 29 | 1 |  |  |  |
| National University of Ireland Galway (control) | force:camelot_lattice | ok | yes |  | 48 | 0 |  |  |  |
| National University of Ireland Galway (control) | force:camelot_stream | ok | yes |  | 49 | 0 |  |  |  |
| National University of Ireland Galway (control) | force:mistral_cache | ok | yes |  | 48 | 0 |  |  |  |
| National University of Ireland Galway (control) | docling | ok | yes |  | 48 | 0 |  |  |  |
| National University of Ireland Galway (control) | gate-dd-mon-yy | ok | yes |  | 48 | 0 |  |  |  |
| Dublin City Council (control) | current | ok | yes |  | 547 | 0 |  |  |  |
| Dublin City Council (control) | force:pdfplumber | ok | no | width_uniformity, fragment_share, column_type_purity, split_word_rate | 0 | 0 |  |  |  |
| Dublin City Council (control) | force:pymupdf | no_table | no |  | 0 | 0 |  |  |  |
| Dublin City Council (control) | force:camelot_lattice | ok | no | width_uniformity, fragment_share, column_type_purity, split_word_rate | 0 | 0 |  |  |  |
| Dublin City Council (control) | force:camelot_stream | ok | yes |  | 547 | 0 |  |  |  |
| Dublin City Council (control) | force:mistral_cache | ok | yes |  | 539 | 8 |  |  |  |
| Dublin City Council (control) | docling | ok | yes |  | 547 | 4 |  |  |  |
| Dublin City Council (control) | gate-dd-mon-yy | ok | yes |  | 547 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | current | ok | yes |  | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | force:pdfplumber | ok | yes |  | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | force:pymupdf | ok | yes |  | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | force:camelot_lattice | ok | yes |  | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | force:camelot_stream | ok | no | width_uniformity, fragment_share, column_type_purity, role_contamination, anchored_row_share | 109 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | force:mistral_cache | ok | no | width_uniformity | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | docling | ok | yes |  | 55 | 0 |  |  |  |
| National Transport Authority (NTA) (control) | gate-dd-mon-yy | ok | yes |  | 55 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | current | ok | no | role_contamination | 62 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:pdfplumber | ok | no | width_uniformity, role_contamination | 62 | 49 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:pymupdf | ok | no | width_uniformity, role_contamination | 0 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:camelot_lattice | ok | no | role_contamination | 62 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, role_contamination | 111 | 58 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | docling | ok | no | role_contamination | 62 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | gate-dd-mon-yy | ok | no | role_contamination | 62 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | current | ok | yes |  | 75 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:pdfplumber | ok | no | width_uniformity, fragment_share, split_word_rate, role_contamination, anchored_row_share | 89 | 29 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:pymupdf | ok | no | width_uniformity, fragment_share, anchored_row_share | 6 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:camelot_lattice | ok | yes |  | 75 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share | 85 | 17 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | docling | ok | yes |  | 75 | 1 |  |  |  |
| Raidió Teilifís Éireann - RTÉ (gold) | gate-dd-mon-yy | ok | yes |  | 75 | 1 |  |  |  |
| Fingal County Council (gold) | current | ok | no | anchored_row_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | force:pdfplumber | ok | no | anchored_row_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | force:pymupdf | ok | no | anchored_row_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | force:camelot_lattice | ok | yes |  | 119 | 268 |  |  |  |
| Fingal County Council (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, role_contamination, anchored_row_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | force:mistral_cache | ok | no | width_uniformity, fragment_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | docling | ok | yes |  | 119 | 268 |  |  |  |
| Fingal County Council (gold) | gate-dd-mon-yy | ok | no | anchored_row_share | 119 | 268 |  |  |  |
| Fingal County Council (gold) | current | ok | yes |  | 139 | 0 |  |  |  |
| Fingal County Council (gold) | force:pdfplumber | ok | no | width_uniformity | 126 | 139 |  |  |  |
| Fingal County Council (gold) | force:pymupdf | ok | no | role_contamination | 105 | 101 |  |  |  |
| Fingal County Council (gold) | force:camelot_lattice | ok | no | width_uniformity, role_contamination | 16 | 15 |  |  |  |
| Fingal County Council (gold) | force:camelot_stream | ok | no | role_contamination | 141 | 141 |  |  |  |
| Fingal County Council (gold) | force:mistral_cache | ok | yes |  | 139 | 0 |  |  |  |
| Fingal County Council (gold) | docling | ok | no | width_uniformity, role_contamination | 108 | 62 |  |  |  |
| Fingal County Council (gold) | gate-dd-mon-yy | ok | yes |  | 139 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | current | ok | yes |  | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | force:pdfplumber | ok | no | fragment_share | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | force:pymupdf | ok | no | width_uniformity, fragment_share | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | force:camelot_lattice | ok | yes |  | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | force:camelot_stream | ok | no | fragment_share, anchored_row_share | 66 | 28 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | force:mistral_cache | not_extracted | no |  | 0 | 0 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | docling | ok | no | fragment_share | 29 | 2 |  |  |  |
| Department of Rural and Community Development and the Gaeltacht (gold) | gate-dd-mon-yy | ok | yes |  | 0 | 0 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | current | ok | yes |  | 9 | 0 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | force:pdfplumber | ok | no | split_word_rate | 9 | 0 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | force:pymupdf | ok | no | anchored_row_share | 9 | 0 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | force:camelot_lattice | ok | yes |  | 9 | 0 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, split_word_rate, anchored_row_share | 9 | 2 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | force:mistral_cache | ok | no | width_uniformity, fragment_share | 10 | 1 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | docling | ok | no | width_uniformity, fragment_share | 10 | 1 |  |  |  |
| Financial Services and Pensions Ombudsman (FSPO) (gold) | gate-dd-mon-yy | ok | yes |  | 9 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | current | ok | yes |  | 32 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | force:pdfplumber | ok | yes |  | 32 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | force:pymupdf | ok | no | role_contamination, anchored_row_share | 32 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | force:camelot_lattice | ok | yes |  | 0 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, column_type_purity, anchored_row_share | 101 | 6 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | force:mistral_cache | ok | yes |  | 32 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | docling | ok | yes |  | 32 | 0 |  |  |  |
| Health Information and Quality Authority (HIQA) (gold) | gate-dd-mon-yy | ok | yes |  | 32 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | current | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | force:pdfplumber | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | force:pymupdf | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | force:camelot_lattice | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, anchored_row_share | 59 | 1 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | force:mistral_cache | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | docling | ok | yes |  | 74 | 0 |  |  |  |
| Department of Housing, Local Government and Heritage (gold) | gate-dd-mon-yy | ok | yes |  | 74 | 0 |  |  |  |
| Charities Regulator (gold) | current | ok | yes |  | 40 | 2 |  |  |  |
| Charities Regulator (gold) | force:pdfplumber | ok | yes |  | 40 | 2 |  |  |  |
| Charities Regulator (gold) | force:pymupdf | ok | yes |  | 40 | 2 |  |  |  |
| Charities Regulator (gold) | force:camelot_lattice | ok | yes |  | 37 | 1 |  |  |  |
| Charities Regulator (gold) | force:camelot_stream | ok | no | fragment_share | 45 | 6 |  |  |  |
| Charities Regulator (gold) | force:mistral_cache | ok | yes |  | 40 | 2 |  |  |  |
| Charities Regulator (gold) | docling | ok | yes |  | 40 | 2 |  |  |  |
| Charities Regulator (gold) | gate-dd-mon-yy | ok | yes |  | 40 | 2 |  |  |  |
| Irish Fiscal Advisory Council (gold) | current | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | force:pdfplumber | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | force:pymupdf | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | force:camelot_lattice | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | force:camelot_stream | ok | no | width_uniformity, fragment_share, anchored_row_share | 29 | 21 |  |  |  |
| Irish Fiscal Advisory Council (gold) | force:mistral_cache | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | docling | ok | yes |  | 7 | 0 |  |  |  |
| Irish Fiscal Advisory Council (gold) | gate-dd-mon-yy | ok | yes |  | 7 | 0 |  |  |  |
| Office of Public Works (cluster) | current | ok | no | role_contamination | 118 | 0 | 0.9943502824858758 | force:pymupdf | no |
| Office of Public Works (cluster) | force:pdfplumber | ok | no | role_contamination | 118 | 0 | 0.9971751412429378 | force:pymupdf | no |
| Office of Public Works (cluster) | force:pymupdf | ok | no | role_contamination | 118 | 0 | 0.9971751412429378 | force:pdfplumber | no |
| Office of Public Works (cluster) | force:camelot_lattice | ok | no | role_contamination | 118 | 0 | 0.9943502824858758 | force:pymupdf | no |
| Office of Public Works (cluster) | force:camelot_stream | ok | no | role_contamination | 121 | 1 | 0.8277777777777777 | force:pdfplumber | no |
| Office of Public Works (cluster) | force:mistral_cache | ok | no | width_uniformity, role_contamination | 118 | 1 | 0.8008474576271186 | force:pymupdf | no |
| Office of Public Works (cluster) | docling | ok | no | role_contamination | 108 | 0 | 0.8884180790960452 | current | no |
| Office of Public Works (cluster) | gate-dd-mon-yy | ok | yes |  | 118 | 0 | 0.9943502824858758 | force:pymupdf | yes |
| Office of Public Works (cluster) | current | ok | no | role_contamination | 152 | 2 | 0.9978213507625272 | force:camelot_lattice | no |
| Office of Public Works (cluster) | force:pdfplumber | ok | no | role_contamination | 152 | 2 | 0.9978213507625272 | force:camelot_lattice | no |
| Office of Public Works (cluster) | force:pymupdf | ok | no | role_contamination | 152 | 2 | 0.9978213507625272 | force:camelot_lattice | no |
| Office of Public Works (cluster) | force:camelot_lattice | ok | no | role_contamination | 152 | 2 | 0.9978213507625272 | current | no |
| Office of Public Works (cluster) | force:camelot_stream | ok | no | role_contamination | 162 | 4 | 0.8653846153846154 | current | no |
| Office of Public Works (cluster) | force:mistral_cache | ok | no | role_contamination | 152 | 1 | 0.9618736383442266 | force:pymupdf | no |
| Office of Public Works (cluster) | docling | ok | no | role_contamination | 152 | 2 | 0.9847494553376906 | force:camelot_lattice | no |
| Office of Public Works (cluster) | gate-dd-mon-yy | ok | yes |  | 152 | 2 | 0.9978213507625272 | force:camelot_lattice | yes |
| Office of Public Works (cluster) | current | ok | no | role_contamination | 157 | 3 | 0.9861995753715499 | force:pdfplumber | no |
| Office of Public Works (cluster) | force:pdfplumber | ok | no | role_contamination | 156 | 3 | 0.9861995753715499 | current | no |
| Office of Public Works (cluster) | force:pymupdf | ok | no | role_contamination | 157 | 3 | 0.9861995753715499 | force:pdfplumber | no |
| Office of Public Works (cluster) | force:camelot_lattice | ok | no | role_contamination | 157 | 3 | 0.9861995753715499 | current | no |
| Office of Public Works (cluster) | force:camelot_stream | ok | no | role_contamination | 157 | 3 | 0.8715498938428875 | current | no |
| Office of Public Works (cluster) | force:mistral_cache | ok | no | role_contamination | 158 | 2 | 0.7685774946921444 | current | no |
| Office of Public Works (cluster) | docling | ok | no | role_contamination | 157 | 3 | 0.9819532908704883 | current | no |
| Office of Public Works (cluster) | gate-dd-mon-yy | ok | yes |  | 157 | 3 | 0.9861995753715499 | force:pdfplumber | yes |
| Office of Public Works (cluster) | current | ok | no | role_contamination | 141 | 2 | 0.9905437352245863 | force:pymupdf | no |
| Office of Public Works (cluster) | force:pdfplumber | ok | no | role_contamination | 141 | 2 | 0.9905437352245863 | force:pymupdf | no |
| Office of Public Works (cluster) | force:pymupdf | ok | no | role_contamination | 141 | 2 | 0.9988179669030733 | force:camelot_lattice | no |
| Office of Public Works (cluster) | force:camelot_lattice | ok | no | role_contamination | 141 | 2 | 0.9988179669030733 | force:pymupdf | no |
| Office of Public Works (cluster) | force:camelot_stream | ok | no | role_contamination | 141 | 11 | 0.7727272727272727 | force:pymupdf | no |
| Office of Public Works (cluster) | force:mistral_cache | ok | no | role_contamination | 141 | 2 | 0.9302600472813238 | force:pymupdf | no |
| Office of Public Works (cluster) | docling | ok | no | role_contamination | 141 | 2 | 0.9704491725768322 | force:pymupdf | no |
| Office of Public Works (cluster) | gate-dd-mon-yy | ok | yes |  | 141 | 2 | 0.9905437352245863 | force:pymupdf | yes |
