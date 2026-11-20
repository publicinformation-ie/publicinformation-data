# apply_overrides

Applies manual `public_body_id` corrections from `override.json`, then drops organisations that are still unresolved.

- **`override.json`:** `{ "<datacatalogue_slug>": <public_body_id | null> }`. A value always replaces the automated match. A non-null id assigns that body; an explicit `null` suppresses a false match. Slugs absent from the file keep their automated result.
- **Dropped records:** most catalogue organisations are not canonical public bodies, so unresolved records are left out of `output.json` and counted, not fatal.
- **Summary line:** `Matched X/Y (N via override), dropped M unmatched`.
- Candidate overrides can be hinted by the `datagovie_pipeline` overrides where slugs coincide; check each by hand against `match_log.json` and do not copy blindly.
