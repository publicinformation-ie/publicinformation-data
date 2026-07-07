from lib.body_utils import generate_slug, resolve_slug


class TestGenerateSlug:
    def test_lowercases_and_hyphenates(self):
        assert generate_slug("Health Service Executive") == "health-service-executive"

    def test_strips_diacritics(self):
        assert generate_slug("Údarás na Gaeltachta") == "udaras-na-gaeltachta"

    def test_expands_ampersand(self):
        assert generate_slug("Housing & Planning") == "housing-and-planning"

    def test_empty_for_all_symbol_name(self):
        assert generate_slug("—/—") == ""


class TestResolveSlug:
    def test_uses_seed_value_when_present(self):
        seed = {1: "seeded-slug"}
        assert resolve_slug(1, "Some Other Name", seed) == "seeded-slug"

    def test_generates_slug_when_id_absent_from_seed(self):
        assert resolve_slug(999, "New Body Ltd", {}) == "new-body-ltd"

    def test_falls_back_to_id_suffixed_slug_for_empty_generated_slug(self):
        assert resolve_slug(999, "—/—", {}) == "body-999"

    def test_seed_wins_even_when_name_would_generate_differently(self):
        # Permanence guarantee: never recompute for a seeded id, even if the
        # current name would slugify to something else.
        seed = {1: "old-permanent-slug"}
        assert resolve_slug(1, "Renamed Body", seed) == "old-permanent-slug"
