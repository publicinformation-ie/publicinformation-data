"""Tests for Serper.dev fallback in get_foi_pages_for_public_bodies.py."""
import io
import unittest
from unittest.mock import MagicMock, patch

from get_foi_pages_for_public_bodies import find_foi_page, search_serper_for_foi_page, _get_final_url


SERPER_RESPONSE_WITH_FOI = {
    "organic": [
        {"link": "https://example.gov.uk/news/2023"},
        {"link": "https://example.gov.uk/foi/disclosure-log"},
        {"link": "https://example.gov.uk/contact"},
    ]
}

SERPER_RESPONSE_WITHOUT_FOI = {
    "organic": [
        {"link": "https://example.gov.uk/news/2023"},
        {"link": "https://example.gov.uk/contact"},
    ]
}

SERPER_RESPONSE_MULTIPLE_FOI = {
    "organic": [
        {"link": "https://example.gov.uk/foi/disclosure-log/2023"},
        {"link": "https://example.gov.uk/foi"},
        {"link": "https://example.gov.uk/freedom-of-information/requests"},
    ]
}


class TestSearchSerperForFoiPage(unittest.TestCase):

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_foi_url_when_found_in_organic_results(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SERPER_RESPONSE_WITH_FOI,
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertEqual(result, "https://example.gov.uk/foi/disclosure-log")

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_shortest_foi_url_when_multiple_matches(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SERPER_RESPONSE_MULTIPLE_FOI,
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertEqual(result, "https://example.gov.uk/foi")

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_none_when_no_foi_urls_in_results(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SERPER_RESPONSE_WITHOUT_FOI,
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertIsNone(result)

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_none_when_api_returns_error(self, mock_post):
        mock_post.return_value = MagicMock(status_code=429)
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertIsNone(result)

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_none_when_no_api_key(self, mock_post):
        result = search_serper_for_foi_page("https://example.gov.uk", api_key=None)
        mock_post.assert_not_called()
        self.assertIsNone(result)

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_queries_using_domain_from_url(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SERPER_RESPONSE_WITHOUT_FOI,
        )
        search_serper_for_foi_page("https://example.gov.uk/some/path", api_key="test-key")
        call_args = mock_post.call_args
        body = call_args.kwargs.get('json') or call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs['json']
        self.assertIn("site:example.gov.uk", body['q'])

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_sends_api_key_in_header(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: SERPER_RESPONSE_WITHOUT_FOI,
        )
        search_serper_for_foi_page("https://example.gov.uk", api_key="my-secret-key")
        headers = mock_post.call_args.kwargs.get('headers', {})
        self.assertEqual(headers.get('X-API-KEY'), "my-secret-key")

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_returns_none_on_network_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.RequestException("timeout")
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertIsNone(result)

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_only_returns_urls_from_queried_domain(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "organic": [
                    {"link": "https://other.gov.uk/foi"},
                    {"link": "https://example.gov.uk/foi"},
                ]
            },
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertEqual(result, "https://example.gov.uk/foi")


class TestFindFoiPageSerperFallback(unittest.TestCase):

    @patch('get_foi_pages_for_public_bodies.search_serper_for_foi_page')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_falls_back_to_serper_when_sitemap_finds_nothing(
        self, _robots, mock_sitemap, mock_serper
    ):
        mock_sitemap.return_value = []
        mock_serper.return_value = "https://example.gov.uk/foi"

        result = find_foi_page("https://example.gov.uk", serper_api_key="test-key")

        mock_serper.assert_called_once()
        self.assertEqual(result, "https://example.gov.uk/foi")

    @patch('get_foi_pages_for_public_bodies.search_serper_for_foi_page')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_does_not_call_serper_when_sitemap_succeeds(
        self, _robots, mock_sitemap, mock_serper
    ):
        mock_sitemap.return_value = ["https://example.gov.uk/foi/disclosure"]
        mock_serper.return_value = "https://example.gov.uk/foi"

        result = find_foi_page("https://example.gov.uk", serper_api_key="test-key")

        mock_serper.assert_not_called()
        self.assertEqual(result, "https://example.gov.uk/foi/disclosure")

    @patch('get_foi_pages_for_public_bodies.search_serper_for_foi_page')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_returns_none_when_both_sitemap_and_serper_find_nothing(
        self, _robots, mock_sitemap, mock_serper
    ):
        mock_sitemap.return_value = []
        mock_serper.return_value = None

        result = find_foi_page("https://example.gov.uk", serper_api_key="test-key")

        self.assertIsNone(result)

    @patch('get_foi_pages_for_public_bodies.search_serper_for_foi_page')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_does_not_call_serper_when_no_api_key_provided(
        self, _robots, mock_sitemap, mock_serper
    ):
        mock_sitemap.return_value = []

        result = find_foi_page("https://example.gov.uk")

        mock_serper.assert_not_called()
        self.assertIsNone(result)


class TestNamePrefixInErrorMessages(unittest.TestCase):

    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=False)
    def test_robots_disallow_message_includes_name(self, _robots):
        stderr = io.StringIO()
        with patch('sys.stderr', stderr):
            find_foi_page("https://example.gov.uk", name="Example Council")
        self.assertIn("Example Council", stderr.getvalue())

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_serper_error_response_message_includes_name(self, mock_post):
        mock_post.return_value = MagicMock(status_code=429)
        stderr = io.StringIO()
        with patch('sys.stderr', stderr):
            search_serper_for_foi_page("https://example.gov.uk", api_key="key", name="Example Council")
        self.assertIn("Example Council", stderr.getvalue())

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_serper_network_error_message_includes_name(self, mock_post):
        import requests as req
        mock_post.side_effect = req.RequestException("timeout")
        stderr = io.StringIO()
        with patch('sys.stderr', stderr):
            search_serper_for_foi_page("https://example.gov.uk", api_key="key", name="Example Council")
        self.assertIn("Example Council", stderr.getvalue())

    @patch('get_foi_pages_for_public_bodies.search_serper_for_foi_page')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_serper_fallback_message_includes_name(self, _robots, mock_sitemap, mock_serper):
        mock_sitemap.return_value = []
        mock_serper.return_value = None
        stderr = io.StringIO()
        with patch('sys.stderr', stderr):
            find_foi_page("https://example.gov.uk", serper_api_key="key", name="Example Council")
        self.assertIn("Example Council", stderr.getvalue())


class TestRedirectHandling(unittest.TestCase):
    """Tests for handling domain redirects (e.g., xyz.ie -> gov.ie/xyz)."""

    def setUp(self):
        import get_foi_pages_for_public_bodies as mod
        mod._redirect_cache.clear()

    @patch('get_foi_pages_for_public_bodies._request')
    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_should_find_foi_on_redirected_domain(
        self, mock_robots, mock_collect, mock_request
    ):
        """When xyz.ie redirects to gov.ie/xyz, should find FOI on gov.ie/xyz."""
        # This test verifies the DESIRED behavior that we will implement
        
        # Mock that xyz.ie redirects to gov.ie/xyz
        mock_response = MagicMock()
        mock_response.url = 'https://www.gov.ie/xyz/'
        mock_response.status_code = 200
        mock_request.return_value = mock_response
        
        # Mock that gov.ie/xyz has FOI in its sitemap
        def collect_side_effect(url):
            if 'gov.ie/xyz' in url:
                return ['https://www.gov.ie/xyz/foi/']
            return []
        
        mock_collect.side_effect = collect_side_effect
        
        # This should find FOI on the final domain
        result = find_foi_page(
            "https://xyz.ie/",
            ignore_robots=True,
            serper_api_key=None
        )
        
        # This will FAIL until we implement redirect handling
        self.assertEqual(result, "https://www.gov.ie/xyz/foi/")

    @patch('get_foi_pages_for_public_bodies._request')
    def test_get_final_url_follows_redirects(self, mock_request):
        """Helper function should follow redirects and return final URL."""
        mock_response = MagicMock()
        mock_response.url = 'https://www.gov.ie/final/'
        mock_response.status_code = 301
        mock_response.ok = False
        mock_request.return_value = mock_response
        
        result = _get_final_url("https://xyz.ie/")
        self.assertEqual(result, "https://www.gov.ie/final/")

    @patch('get_foi_pages_for_public_bodies._request')
    def test_get_final_url_returns_original_if_no_redirect(self, mock_request):
        """Helper function should return original URL if no redirect."""
        mock_response = MagicMock()
        mock_response.url = 'https://xyz.ie/'
        mock_response.status_code = 200
        mock_response.ok = True
        mock_request.return_value = mock_response
        
        result = _get_final_url("https://xyz.ie/")
        self.assertEqual(result, "https://xyz.ie/")

    @patch('get_foi_pages_for_public_bodies._request')
    def test_get_final_url_handles_405_method_not_allowed(self, mock_request):
        """Helper function should try GET when HEAD returns 405."""
        mock_head_response = MagicMock()
        mock_head_response.status_code = 405
        mock_head_response.url = 'https://xyz.ie/'
        
        mock_get_response = MagicMock()
        mock_get_response.url = 'https://www.gov.ie/xyz/'
        mock_get_response.status_code = 200
        mock_get_response.ok = True
        
        mock_request.side_effect = [mock_head_response, mock_get_response]
        
        result = _get_final_url("https://xyz.ie/")
        # Should return the URL from GET response since HEAD returned 405
        self.assertEqual(result, "https://www.gov.ie/xyz/")

    @patch('get_foi_pages_for_public_bodies._request')
    def test_get_final_url_returns_original_on_exception(self, mock_request):
        """Helper function should return original URL on request exception."""
        import requests
        mock_request.side_effect = requests.RequestException("Connection error")
        
        result = _get_final_url("https://xyz.ie/")
        self.assertEqual(result, "https://xyz.ie/")

    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies._get_final_url')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_checks_both_domains_for_foi_when_redirected(
        self, mock_robots, mock_get_final, mock_collect
    ):
        """When URL redirects to different domain, should check both for FOI."""
        # Mock redirect from xyz.ie to gov.ie/xyz
        mock_get_final.return_value = "https://www.gov.ie/xyz/"
        
        # Mock sitemap results - FOI only on final domain
        def collect_side_effect(url):
            if 'xyz.ie' in url:
                return []  # No FOI on original
            elif 'gov.ie/xyz' in url:
                return ['https://www.gov.ie/xyz/foi/']  # FOI on final
            return []
        
        mock_collect.side_effect = collect_side_effect
        
        result = find_foi_page(
            "https://xyz.ie/",
            ignore_robots=True,
            serper_api_key=None
        )
        
        # Should find FOI on the final domain
        self.assertEqual(result, "https://www.gov.ie/xyz/foi/")
        
        # Verify both URLs were checked
        self.assertEqual(mock_collect.call_count, 2)


class TestSharedDomainPathFiltering(unittest.TestCase):
    """When a redirect lands on a path within a large shared domain, results should be
    restricted to that entity's path prefix so we don't return another entity's FOI page."""

    def setUp(self):
        import get_foi_pages_for_public_bodies as mod
        if hasattr(mod, '_redirect_cache'):
            mod._redirect_cache.clear()

    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies._get_final_url')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_excludes_foi_pages_outside_entity_path_on_shared_domain(
        self, _robots, mock_get_final, mock_collect
    ):
        mock_get_final.return_value = "https://www.gov.ie/xyz/"

        def collect_side_effect(url):
            if 'xyz.ie' in url:
                return []
            return [
                'https://www.gov.ie/other-dept/foi/',
                'https://www.gov.ie/foi/',
                'https://www.gov.ie/xyz/foi/',
            ]

        mock_collect.side_effect = collect_side_effect

        result = find_foi_page("https://xyz.ie/", ignore_robots=True, serper_api_key=None)

        self.assertEqual(result, "https://www.gov.ie/xyz/foi/")

    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies._get_final_url')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_shorter_unscoped_path_does_not_beat_entity_scoped_path(
        self, _robots, mock_get_final, mock_collect
    ):
        """gov.ie/foi is shorter than gov.ie/xyz/foi but must not be returned."""
        mock_get_final.return_value = "https://www.gov.ie/xyz/"

        def collect_side_effect(url):
            if 'xyz.ie' in url:
                return []
            return ['https://www.gov.ie/foi/', 'https://www.gov.ie/xyz/foi/']

        mock_collect.side_effect = collect_side_effect

        result = find_foi_page("https://xyz.ie/", ignore_robots=True, serper_api_key=None)

        self.assertEqual(result, "https://www.gov.ie/xyz/foi/")

    @patch('get_foi_pages_for_public_bodies._collect_sitemap_locs')
    @patch('get_foi_pages_for_public_bodies._get_final_url')
    @patch('get_foi_pages_for_public_bodies.is_allowed_by_robots', return_value=True)
    def test_no_path_prefix_filter_when_redirect_is_to_root(
        self, _robots, mock_get_final, mock_collect
    ):
        """When final URL is the domain root (no path), all FOI URLs on that domain are valid."""
        mock_get_final.return_value = "https://www.example.gov.uk/"

        def collect_side_effect(url):
            if 'old.example.gov.uk' in url:
                return []
            return ['https://www.example.gov.uk/foi/']

        mock_collect.side_effect = collect_side_effect

        result = find_foi_page("https://old.example.gov.uk/", ignore_robots=True, serper_api_key=None)

        self.assertEqual(result, "https://www.example.gov.uk/foi/")


class TestSerperTitleMatching(unittest.TestCase):

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_matches_result_by_title_when_url_has_no_foi_keywords(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "organic": [
                    {
                        "link": "https://example.gov.uk/transparency",
                        "title": "Freedom of Information",
                    },
                ]
            },
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertEqual(result, "https://example.gov.uk/transparency")

    @patch('get_foi_pages_for_public_bodies.requests.post')
    def test_does_not_match_result_with_neither_foi_url_nor_foi_title(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "organic": [
                    {
                        "link": "https://example.gov.uk/transparency",
                        "title": "Transparency and openness",
                    },
                ]
            },
        )
        result = search_serper_for_foi_page("https://example.gov.uk", api_key="test-key")
        self.assertIsNone(result)


class TestRedirectCaching(unittest.TestCase):

    def setUp(self):
        import get_foi_pages_for_public_bodies as mod
        if hasattr(mod, '_redirect_cache'):
            mod._redirect_cache.clear()

    @patch('get_foi_pages_for_public_bodies._request')
    def test_does_not_make_repeated_requests_for_same_url(self, mock_request):
        mock_response = MagicMock()
        mock_response.url = 'https://www.gov.ie/xyz/'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result1 = _get_final_url("https://xyz.ie/")
        result2 = _get_final_url("https://xyz.ie/")

        self.assertEqual(result1, result2)
        self.assertEqual(mock_request.call_count, 1)

    @patch('get_foi_pages_for_public_bodies._request')
    def test_different_urls_are_each_fetched_once(self, mock_request):
        def side_effect(method, url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.url = url  # no redirect
            return resp

        mock_request.side_effect = side_effect

        _get_final_url("https://alpha.ie/")
        _get_final_url("https://beta.ie/")
        _get_final_url("https://alpha.ie/")  # cached

        self.assertEqual(mock_request.call_count, 2)


if __name__ == '__main__':
    unittest.main()
