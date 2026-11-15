# Diagnosis input: 2018 file (https://assets.gov.ie/static/documents/non-personal-foi-requests-2018.pdf)

## Page images

- page 1: `experiments/2026-11-15-gating-round-01-1594-non-personal/pages/page-1.png`
- last page (15): `experiments/2026-11-15-gating-round-01-1594-non-personal/pages/page-15.png`

## current  (status=ok, error=None)

rows: 155, header width: 6

header row: `["FOI Requests - 2018", null, null, null, null, null]`
first five data rows:
- `["Ref No", "Date\nReceived", "Requester", "Request Details", "Decision\nDate", "Decision"]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act:\ni) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of\ndeer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the\nname of the sniper(s) engaged to carry out each cull.\nii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016.\niii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017.\niv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure\nin order to negate any concerns regarding commercial sensitivity.\nv) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the\nproperty of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been:\n-damaged, or;\n-gone missing for any period of time.\nPlease provide information regarding any cost accrued in the repair or relocation of these items; please provide\ninformation regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and\nplease provide any information regarding any items that are still missing at the time of this request and the value of same.\nIf there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the\nabove, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014,\n2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'Date\nReceived'` -> ['header']
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']

## force:camelot_lattice  (status=ok, error=None)

rows: 155, header width: 6

header row: `["FOI Requests - 2018", null, null, null, null, null]`
first five data rows:
- `["Ref No", "Date \nReceived", "Requester", "Request Details", "Decision \nDate", "Decision"]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act:\ni) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of \ndeer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the \nname of the sniper(s) engaged to carry out each cull.\nii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016.\niii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017.\niv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure \nin order to negate any concerns regarding commercial sensitivity.\nv) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the \nproperty of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been: \n-damaged, or;\n-gone missing for any period of time.\nPlease provide information regarding any cost accrued in the repair or relocation of these items; please provide \ninformation regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and \nplease provide any information regarding any items that are still missing at the time of this request and the value of same. \nIf there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the \nabove, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014, \n2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'Date \nReceived'` -> ['header']
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']

## force:camelot_stream  (status=ok, error=None)

rows: 532, header width: 6

header row: `[null, null, null, "FOI Requests - 2018", null, null]`
first five data rows:
- `["Ref No", "Date", "Requester", "Request Details", "Decision", "Decision"]`
- `[null, "Received", null, null, "Date", null]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act:", "N/A", "Withdrawn"]`
- `[null, null, null, "i) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of", null, null]`
- `[null, null, null, "deer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the", null, null]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'decision_date', 2: 'requester_type'}`

## force:mistral_cache  (status=ok, error=None)

rows: 168, header width: 6

header row: `["Ref No", "Date Received", "Requester", "Request Details", "Decision Date", "Decision"]`
first five data rows:
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act: i) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of deer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the name of the sniper(s) engaged to carry out each cull. ii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016. iii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017. iv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure in order to negate any concerns regarding commercial sensitivity. v) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the property of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been: -damaged, or; -gone missing for any period of time. Please provide information regarding any cost accrued in the repair or relocation of these items; please provide information regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and please provide any information regarding any items that are still missing at the time of this request and the value of same. If there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the above, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014, 2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`
- `["FOI/1/1/1294", "08-Jan-18", "Journalist", "I wish to request access to the following records: 1.An itemised breakdown of all costs associated with the helipad installed on the roof of Government buildings. 2.All correspondence between the Department of the Taoiseach and the Department of Defence about helicopter access for An Taoiseach and cabinet ministers. 3.The number of times the helipad has been used in each of the past five years. Parts one and two of my request are limited to the past five years only", "N/A", "Withdrawn"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'Date Received'` -> ['header']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']

## force:pdfplumber  (status=ok, error=None)

rows: 155, header width: 6

header row: `["FOI Requests - 2018", null, null, null, null, null]`
first five data rows:
- `["Ref No", "Date\nReceived", "Requester", "Request Details", "Decision\nDate", "Decision"]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act:\ni) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of\ndeer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the\nname of the sniper(s) engaged to carry out each cull.\nii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016.\niii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017.\niv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure\nin order to negate any concerns regarding commercial sensitivity.\nv) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the\nproperty of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been:\n-damaged, or;\n-gone missing for any period of time.\nPlease provide information regarding any cost accrued in the repair or relocation of these items; please provide\ninformation regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and\nplease provide any information regarding any items that are still missing at the time of this request and the value of same.\nIf there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the\nabove, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014,\n2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'Date\nReceived'` -> ['header']
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']

## force:pymupdf  (status=ok, error=None)

rows: 155, header width: 6

header row: `["FOI Requests - 2018", null, null, null, null, null]`
first five data rows:
- `["Ref No", "Date\nReceived", "Requester", "Request Details", "Decision\nDate", "Decision"]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act:\ni) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of\ndeer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the\nname of the sniper(s) engaged to carry out each cull.\nii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016.\niii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017.\niv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure\nin order to negate any concerns regarding commercial sensitivity.\nv) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the\nproperty of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been:\n-damaged, or;\n-gone missing for any period of time.\nPlease provide information regarding any cost accrued in the repair or relocation of these items; please provide\ninformation regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and\nplease provide any information regarding any items that are still missing at the time of this request and the value of same.\nIf there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the\nabove, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014,\n2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'Date\nReceived'` -> ['header']
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']

## docling  (status=ok, error=None)

rows: 155, header width: 6

header row: `["FOI Requests - 2018", "FOI Requests - 2018", "FOI Requests - 2018", "FOI Requests - 2018", "FOI Requests - 2018", "FOI Requests - 2018"]`
first five data rows:
- `["Ref No", "Date Received", "Requester", "Request Details", "Decision Date", "Decision"]`
- `["FOI/1/1/1290", "04-Jan-18", "Journalist", "I wish to request access to the following records under the Freedom of Information Act: i) Records of deer culls in Phoenix Park during 2016 and 2017, to include the date of the cull, the number and type of deer culled, revenue generated through the sale of carcasses from each cull, the purchaser of the carcasses, and the name of the sniper(s) engaged to carry out each cull. ii) Records of the current stock of deer in Phoenix Park, and the stock of deer in Phoenix Park at the beginning of 2016. iii) Records relating to deer that died in road accidents or in other circumstances during 2016 and 2017. iv) The total amount paid to snipers for carrying out deer culls in Phoenix Park during 2016 and 2017 - a cumulative figure in order to negate any concerns regarding commercial sensitivity. v) The total amount paid to snipers for carrying out deer culls in Phoenix Park since 2013.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1291", "04-Jan-18", "Journalist", "Please provide information regarding any articles - including paintings, monuments, sculptures, etc - that are either the property of the OPW or managed/monitored by the OPW on behalf of the state, that have, in 2017, been: -damaged, or; -gone missing for any period of time. Please provide information regarding any cost accrued in the repair or relocation of these items; please provide information regarding how they came to be damaged/lost in the first instance and any delays in notification of same; and please provide any information regarding any items that are still missing at the time of this request and the value of same. If there is any further information regarding any sanctions applied to individuals or departments/bodies etc regarding the above, please also include this as part of this request, as well as any related documentation.", "30-Jan-18", "Part-Granted"]`
- `["FOI/1/1/1292", "05-Jan-18", "Other", "Request for Information on Lower Lee (Cork City) Flood Relief Scheme.", "N/A", "Withdrawn"]`
- `["FOI/1/1/1293", "06-Jan-18", "Journalist", "The number and the amount of revenue generated through the selling of each type of heritage card in the years 2014, 2015, 2016 and 2017 in tabular form", "30-Jan-18", "Granted"]`

`_header_role_map(rows)` = `{0: 'foi_reference_id', 1: 'date_received', 2: 'requester_type', 4: 'decision_date', 5: 'decision_status'}`

column 1 -> date_received; cell_kinds of its first ten data cells (rows 1-10):
- `'Date Received'` -> ['header']
- `'04-Jan-18'` -> ['reference']
- `'04-Jan-18'` -> ['reference']
- `'05-Jan-18'` -> ['reference']
- `'06-Jan-18'` -> ['reference']
- `'08-Jan-18'` -> ['reference']
- `'09-Jan-18'` -> ['reference']
- `'10-Jan-18'` -> ['reference']
- `'15-Jan-18'` -> ['reference']
- `'17-Jan-18'` -> ['reference']
