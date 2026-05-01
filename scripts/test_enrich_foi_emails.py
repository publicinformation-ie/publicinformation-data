"""Tests for enrich_foi_emails_from_gov_portal.py."""
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from enrich_foi_emails_from_gov_portal import (
    enrich_rows,
    load_aliases,
    normalize_name,
    scrape_foi_gov_ie,
)


class TestNormalizeName(unittest.TestCase):

    def test_irish_diacritics_stripped(self):
        self.assertEqual(normalize_name("An Garda Síochána"), "an garda siochana")

    def test_punctuation_removed(self):
        self.assertEqual(normalize_name("Dept. of Health"), "dept of health")

    def test_whitespace_collapsed(self):
        self.assertEqual(normalize_name("  An   Bord  Pleanála  "), "an bord pleanala")

    def test_hyphens_preserved(self):
        self.assertEqual(normalize_name("North-West Region"), "north-west region")


class TestScrapeFoiGovIe(unittest.TestCase):

    @patch('enrich_foi_emails_from_gov_portal.find_foi_email')
    @patch('enrich_foi_emails_from_gov_portal._request')
    def test_scrape_deduplicates_urls_and_returns_emails(self, mock_request, mock_find_email):
        all_bodies_html = (
            '<html><body>'
            '<a href="/foi_units/garda">Garda</a>'
            '<a href="/foi_units/garda">Garda</a>'
            '<a href="/foi_units/health">Health</a>'
            '</body></html>'
        )
        garda_html = (
            '<html><body>'
            '<h1>An Garda Siochana</h1>'
            '<a href="mailto:foi@garda.ie">FOI</a>'
            '</body></html>'
        )
        health_html = (
            '<html><body>'
            '<h1>Dept of Health</h1>'
            '<a href="mailto:foi@health.gov.ie">FOI</a>'
            '</body></html>'
        )

        mock_request.side_effect = [
            MagicMock(text=all_bodies_html),
            MagicMock(text=garda_html),
            MagicMock(text=health_html),
        ]
        mock_find_email.side_effect = ['foi@garda.ie', 'foi@health.gov.ie']

        result = scrape_foi_gov_ie(rate_limit=0)

        self.assertEqual(result.get('an garda siochana'), 'foi@garda.ie')
        self.assertEqual(result.get('dept of health'), 'foi@health.gov.ie')
        self.assertEqual(len(result), 2)
        self.assertEqual(mock_request.call_count, 3)


class TestEnrichRowsMatch(unittest.TestCase):

    def test_email_filled_from_scraped_data(self):
        rows = [{'public_body_id': '1', 'public_body_name': 'An Post',
                 'foi_contact_email': '', 'last_checked': '', 'last_modified': ''}]
        scraped = {'an post': 'foi@anpost.ie'}
        aliases = {}

        result = enrich_rows(rows, scraped, aliases)

        self.assertEqual(result[0]['foi_contact_email'], 'foi@anpost.ie')
        self.assertEqual(result[0]['last_checked'], date.today().isoformat())
        self.assertEqual(result[0]['last_modified'], date.today().isoformat())


class TestEnrichRowsAlias(unittest.TestCase):

    def test_alias_used_to_match_scraped_data(self):
        rows = [{'public_body_id': '1042', 'public_body_name': 'An Garda Síochána',
                 'foi_contact_email': '', 'last_checked': '', 'last_modified': ''}]
        scraped = {'an garda siochana': 'foi@garda.ie'}
        aliases = {'1042': 'An Garda Siochana'}

        result = enrich_rows(rows, scraped, aliases)

        self.assertEqual(result[0]['foi_contact_email'], 'foi@garda.ie')

    def test_alias_with_integer_public_body_id(self):
        # Bug: when public_body_id is an integer, alias lookup fails
        # even though the alias exists with a string key
        rows = [{'public_body_id': 1004, 'public_body_name': 'Department of Tourism, Culture, Arts, Gaeltacht, Sport and Media',
                 'foi_contact_email': '', 'last_checked': '', 'last_modified': ''}]
        scraped = {'department of tourism culture arts gaeltacht sport media': 'foi@tourism.ie'}
        aliases = {'1004': 'Department of Tourism, Culture, Arts, Gaeltacht, Sport & Media'}

        result = enrich_rows(rows, scraped, aliases)

        # This should pass but currently fails because pub_id (int) is not in aliases (str keys)
        self.assertEqual(result[0]['foi_contact_email'], 'foi@tourism.ie')

    def test_fallback_to_public_body_name_when_alias_normalized_differs(self):
        # Bug: when alias has '&' but foi.gov.ie has 'and', the normalized names differ
        # The code should fall back to using public_body_name if alias doesn't match
        rows = [{'public_body_id': '1004', 'public_body_name': 'Department of Tourism, Culture, Arts, Gaeltacht, Sport and Media',
                 'foi_contact_email': '', 'last_checked': '', 'last_modified': ''}]
        # Simulate scraped data having the name with 'and' (not '&')
        scraped = {'department of tourism culture arts gaeltacht sport and media': 'foi@tourism.ie'}
        # Alias has '&' which normalizes differently
        aliases = {'1004': 'Department of Tourism, Culture, Arts, Gaeltacht, Sport & Media'}

        result = enrich_rows(rows, scraped, aliases)

        # Should fall back to public_body_name and find the match
        self.assertEqual(result[0]['foi_contact_email'], 'foi@tourism.ie')


class TestEnrichRowsNoMatch(unittest.TestCase):

    def test_no_match_leaves_email_unchanged_and_writes_stderr(self):
        rows = [{'public_body_id': '99', 'public_body_name': 'Mystery Body',
                 'foi_contact_email': '', 'last_checked': '', 'last_modified': ''}]
        scraped = {}
        aliases = {}

        stderr = io.StringIO()
        with patch('sys.stderr', stderr):
            result = enrich_rows(rows, scraped, aliases)

        self.assertEqual(result[0]['foi_contact_email'], '')
        self.assertEqual(result[0]['last_checked'], date.today().isoformat())
        self.assertIn('No match for public_body_id=99', stderr.getvalue())


class TestLoadAliases(unittest.TestCase):

    def test_loads_aliases_from_csv(self):
        content = 'public_body_id,public_body_name,foi_gov_ie_name\n1042,An Garda Síochána,An Garda Siochana\n'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', encoding='utf-8', delete=True) as f:
            f.write(content)
            f.flush()
            result = load_aliases(f.name)
        self.assertEqual(result, {'1042': 'An Garda Siochana'})

    def test_returns_empty_dict_for_missing_file(self):
        result = load_aliases(Path('/nonexistent/aliases.csv'))
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()
