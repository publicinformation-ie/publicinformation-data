# fetch_datacatalogue_orgs

Fetches every organisation listed at <https://datacatalogue.gov.ie/organization/> and writes one record per active organisation to `output.json` under `datacatalogue_orgs`.

## Source (checked 2026-11-20)

- **Fetch path:** CKAN API (design D1), not HTML scraping. The site is CKAN 2.9.16 ("PSB Data Catalogue"); `status_show` confirms the version.
- **Endpoint:** `GET /api/3/action/organization_list?all_fields=true&limit=25&offset=N`.
- **Pagination:** the instance returns at most 25 rows per request whatever `limit` asks for, so the step pages with `offset` until an empty page comes back. A response with `limit=2000` still holds only 25 organisations; an unpaged fetch would silently lose most of the list.
- **Size:** 85 organisations, all `type: organization`, `state: active` at the time of checking. No inactive entries were present, so the inactive-filter test uses synthetic entries.
- **Fields used:** `name` (slug), `display_name`, `package_count`, `description`. Others returned: `title`, `id`, `created`, `state`, `type`, `is_organization`, `approval_status`, `image_url`, `image_display_url`, `num_followers`.

## Output record

| Field | Notes |
|---|---|
| `datacatalogue_slug` | CKAN `name`; keys the match step and `override.json` |
| `datacatalogue_name` | `display_name` (`title` can be empty) |
| `datacatalogue_url` | `https://datacatalogue.gov.ie/organization/<slug>` |
| `datacatalogue_package_count` | Only when the source returns it |
| `datacatalogue_description` | Only when non-empty after trimming |

## Fail-closed

Exits non-zero without writing `output.json` on a request error, HTTP error status, unparseable JSON, `success: false`, a missing result list, a repeated slug while paging, no empty page within 200 pages, or zero active organisations.

Tests use `tests/fixtures/organization_list_page1.json`, a trimmed real response.
