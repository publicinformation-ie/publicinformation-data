-- Canonical schema for the publicinformation libSQL database.
-- Owned by publicinformation-data (this repo creates and stores the data).
-- Used by:
--   publicinformation-data db_upload step (populates pipeline tables)
--   publicinformation-web corrections.ts / foi-outreach.ts (inline copies for self-init)

CREATE TABLE IF NOT EXISTS corrections (
  correction_id        TEXT    PRIMARY KEY,
  body_id              INTEGER NOT NULL,
  body_name            TEXT    NOT NULL,
  field                TEXT    NOT NULL CHECK (field IN ('website_url','foi_page','disclosures_page','foi_email')),
  current_value        TEXT,
  suggested_value      TEXT    NOT NULL,
  submitter_did        TEXT    NOT NULL,
  submitter_ip         TEXT    NOT NULL,
  submitted_at         TEXT    NOT NULL,
  status               TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
  accepted_at          TEXT,
  rejected_at          TEXT,
  reject_reason        TEXT,
  pending_karma_record TEXT,
  karma_pending        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public_bodies (
  public_body_id            INTEGER PRIMARY KEY,
  public_body_name          TEXT    NOT NULL,
  public_body_url           TEXT    NOT NULL,
  public_body_category      TEXT    NOT NULL,
  website_url               TEXT,
  website_url_status        TEXT,
  website_url_verified      INTEGER DEFAULT 0,
  foi_page_url              TEXT,
  foi_page_status           TEXT,
  foi_page_verified         INTEGER DEFAULT 0,
  foi_email                 TEXT,
  foi_email_status          TEXT,
  foi_email_verified        INTEGER DEFAULT 0,
  disclosures_page_url      TEXT,
  disclosures_page_status   TEXT,
  disclosures_page_verified INTEGER DEFAULT 0,
  disclosure_files_total    INTEGER DEFAULT 0,
  disclosure_files_valid    INTEGER DEFAULT 0,
  disclosure_files_failed   INTEGER DEFAULT 0,
  disclosure_files_status   TEXT,
  foi_requests_valid        INTEGER DEFAULT 0,
  foi_requests_errors       INTEGER DEFAULT 0,
  foi_requests_status       TEXT,
  pipeline_step             TEXT,
  pipeline_completed_at     TEXT
);

CREATE TABLE IF NOT EXISTS disclosure_files (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  public_body_id   INTEGER NOT NULL REFERENCES public_bodies(public_body_id),
  document_url     TEXT    NOT NULL,
  source_page_url  TEXT    NOT NULL,
  file_type        TEXT    NOT NULL,
  date_added       TEXT
);

CREATE TABLE IF NOT EXISTS foi_disclosures (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  public_body_id      INTEGER NOT NULL REFERENCES public_bodies(public_body_id),
  name                TEXT    NOT NULL,
  file_url            TEXT    NOT NULL,
  file_type           TEXT    NOT NULL,
  foi_reference_id    TEXT,
  decision_date       TEXT,
  requester_type      TEXT,
  decision_status     TEXT,
  review_status       TEXT,
  related_request     TEXT,
  request_description TEXT
);

CREATE TABLE IF NOT EXISTS topics (
  slug        TEXT    PRIMARY KEY,
  label       TEXT    NOT NULL,
  match_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topic_keywords (
  topic_slug TEXT NOT NULL REFERENCES topics(slug),
  keyword    TEXT NOT NULL,
  PRIMARY KEY (topic_slug, keyword)
);

CREATE TABLE IF NOT EXISTS topic_disclosures (
  topic_slug        TEXT    NOT NULL REFERENCES topics(slug),
  foi_disclosure_id INTEGER NOT NULL REFERENCES foi_disclosures(id),
  PRIMARY KEY (topic_slug, foi_disclosure_id)
);

CREATE TABLE IF NOT EXISTS outreach_requests (
  request_id          TEXT    PRIMARY KEY,
  correlation_token   TEXT    NOT NULL UNIQUE,
  public_body_id      INTEGER NOT NULL REFERENCES public_bodies(public_body_id),
  body_name           TEXT    NOT NULL,
  reply_address       TEXT    NOT NULL,
  status              TEXT    NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','sent','awaiting_reply','reply_received',
                                          'satisfactory','unsatisfactory','closed','delivery_failed')),
  resolved_url        TEXT,
  operator_id         TEXT,
  created_at          TEXT    NOT NULL,
  updated_at          TEXT    NOT NULL,
  last_activity_at    TEXT
);

CREATE TABLE IF NOT EXISTS outreach_messages (
  message_id          TEXT    PRIMARY KEY,
  request_id          TEXT    REFERENCES outreach_requests(request_id),
  direction           TEXT    NOT NULL CHECK (direction IN ('outbound','inbound')),
  kind                TEXT    NOT NULL DEFAULT 'genuine'
                        CHECK (kind IN ('genuine','bounce','auto_reply')),
  from_addr           TEXT    NOT NULL,
  to_addr             TEXT    NOT NULL,
  subject             TEXT,
  body_text           TEXT,
  body_html           TEXT,
  raw_headers         TEXT,
  provider_message_id TEXT,
  in_reply_to         TEXT,
  has_attachments     INTEGER NOT NULL DEFAULT 0,
  created_at          TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS message_classifications (
  classification_id   TEXT    PRIMARY KEY,
  message_id          TEXT    NOT NULL REFERENCES outreach_messages(message_id),
  category            TEXT    NOT NULL
                        CHECK (category IN ('acknowledgement','provides_url','provides_files',
                                            'no_log_exists','refusal','needs_clarification','other')),
  confidence          REAL,
  extracted_urls      TEXT,
  model               TEXT    NOT NULL,
  classified_at       TEXT    NOT NULL
);
