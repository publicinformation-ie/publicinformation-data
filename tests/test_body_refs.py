from scripts.lib.body_refs import build_body_slug_lookup, body_uri, BASE_URI


def test_body_uri_builds_expected_url():
    assert body_uri("revenue-commissioners") == (
        f"{BASE_URI}/body/revenue-commissioners"
    )


def test_base_uri_matches_existing_transform_scripts():
    # Every existing transform script (transform_public_bodies.py,
    # transform_foi_request_files.py, transform_who_does_what.py) hard-codes
    # this exact literal. body_refs.BASE_URI must match it so a future
    # switch-over doesn't change any published @id.
    assert BASE_URI == "https://data.publicinformation.ie"


def test_build_body_slug_lookup_uses_seeded_slug_over_generated_one():
    # Seeded slug wins even though generate_slug(name) would produce a
    # different, plausible-looking slug from the name alone. This is the
    # permanence guarantee resolve_slug() documents: never recompute for a
    # seeded id.
    pipeline_bodies = [
        {"public_body_id": 1608, "name": "Office of the Revenue Commissioners"},
    ]
    slug_seed = {1608: "revenue-commissioners-legacy-slug"}
    lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    assert lookup == {1608: "revenue-commissioners-legacy-slug"}


def test_build_body_slug_lookup_falls_back_for_unseeded_id():
    # public_body_id 999999 has no entry in slug_seed -- resolve_slug()
    # falls back to generate_slug(name) for ids "onboarded after
    # slug_seed.json was frozen".
    pipeline_bodies = [
        {"public_body_id": 999999, "name": "New Body Ltd"},
    ]
    slug_seed = {}
    lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    assert lookup == {999999: "new-body-ltd"}


def test_build_body_slug_lookup_supports_public_body_name_key():
    # public/pipeline-data.json-shaped records use "public_body_name"
    # instead of "name" -- both key shapes must resolve identically.
    pipeline_bodies = [
        {"public_body_id": 1651, "public_body_name": "Public Appointments Service"},
    ]
    slug_seed = {1651: "public-appointments-service"}
    lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    assert lookup == {1651: "public-appointments-service"}


def test_build_body_slug_lookup_handles_multiple_bodies():
    pipeline_bodies = [
        {"public_body_id": 1608, "name": "Office of the Revenue Commissioners"},
        {"public_body_id": 1651, "name": "Public Appointments Service"},
    ]
    slug_seed = {1608: "office-of-the-revenue-commissioners"}
    lookup = build_body_slug_lookup(pipeline_bodies, slug_seed)
    assert lookup == {
        1608: "office-of-the-revenue-commissioners",
        1651: "public-appointments-service",
    }
