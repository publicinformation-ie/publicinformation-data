import pytest
from lib.requester_type_map import canonicalize_requester_type, CANONICAL_REQUESTER_TYPES


def test_canonical_types_list():
    assert "Journalist" in CANONICAL_REQUESTER_TYPES
    assert "Member of the Public" in CANONICAL_REQUESTER_TYPES
    assert "Business/Interest Group" in CANONICAL_REQUESTER_TYPES
    assert "Elected-Oireachtas" in CANONICAL_REQUESTER_TYPES
    assert "Elected-Councillor" in CANONICAL_REQUESTER_TYPES
    assert "Elected-Unknown" in CANONICAL_REQUESTER_TYPES
    assert "Oireachtas" not in CANONICAL_REQUESTER_TYPES


def test_none_returns_none():
    assert canonicalize_requester_type(None) is None


def test_empty_returns_none():
    assert canonicalize_requester_type("") is None
    assert canonicalize_requester_type("   ") is None


# ── Journalist ──────────────────────────────────────────────
def test_journalist_canonical():
    assert canonicalize_requester_type("Journalist") == "Journalist"

def test_journalists_plural():
    assert canonicalize_requester_type("Journalists") == "Journalist"

def test_journalist_uppercase():
    assert canonicalize_requester_type("JOURNALIST") == "Journalist"

def test_journalist_lowercase():
    assert canonicalize_requester_type("journalist") == "Journalist"

def test_journalist_trailing_space():
    assert canonicalize_requester_type("Journalist ") == "Journalist"


# ── Other ──────────────────────────────────────────────────
def test_other_canonical():
    assert canonicalize_requester_type("Other") == "Other"

def test_others_maps_to_other():
    assert canonicalize_requester_type("Others") == "Other"

def test_other_uppercase():
    assert canonicalize_requester_type("OTHER") == "Other"

def test_other_trailing_space():
    assert canonicalize_requester_type("Other ") == "Other"


# ── Member of the Public ────────────────────────────────────
def test_member_of_the_public_canonical():
    assert canonicalize_requester_type("Member of the Public") == "Member of the Public"

def test_member_of_public_variant():
    assert canonicalize_requester_type("Member of public") == "Member of the Public"

def test_member_of_public_titlecase():
    assert canonicalize_requester_type("Member of Public") == "Member of the Public"

def test_member_of_public_lowercase():
    assert canonicalize_requester_type("member of public") == "Member of the Public"

def test_mop_abbreviation():
    assert canonicalize_requester_type("MOP") == "Member of the Public"

def test_a_member_of_the_public():
    assert canonicalize_requester_type("A Member of the Public") == "Member of the Public"


# ── Non-Personal ────────────────────────────────────────────
def test_non_personal_hyphen():
    assert canonicalize_requester_type("Non-Personal") == "Non-Personal"

def test_non_personal_space():
    assert canonicalize_requester_type("Non Personal") == "Non-Personal"

def test_non_pers_abbreviation():
    assert canonicalize_requester_type("NON PERS") == "Non-Personal"

def test_non_personal_rogue_space():
    # "Non- personal" — rogue space after hyphen (98 rows in analysis)
    assert canonicalize_requester_type("Non- personal") == "Non-Personal"

def test_non_personal_lowercase():
    assert canonicalize_requester_type("Non personal") == "Non-Personal"


# ── Client ──────────────────────────────────────────────────
def test_client_canonical():
    assert canonicalize_requester_type("Client") == "Client"

def test_clients_plural():
    assert canonicalize_requester_type("Clients") == "Client"

def test_client_uppercase():
    assert canonicalize_requester_type("CLIENT") == "Client"

def test_client_lowercase():
    assert canonicalize_requester_type("client") == "Client"


# ── Business/Interest Group ─────────────────────────────────
def test_business_interest_group_canonical():
    assert canonicalize_requester_type("Business/Interest Group") == "Business/Interest Group"

def test_business_interest_group_spaces_around_slash():
    assert canonicalize_requester_type("Business / Interest Group") == "Business/Interest Group"

def test_business_interest_group_space_after_slash():
    assert canonicalize_requester_type("Business/ Interest Group") == "Business/Interest Group"

def test_business_interest_groups_plural():
    assert canonicalize_requester_type("Business/Interest Groups") == "Business/Interest Group"

def test_business_interest_group_no_slash():
    assert canonicalize_requester_type("Business Interest Group") == "Business/Interest Group"

def test_business_interest_group_leading_space():
    assert canonicalize_requester_type(" Business/Interest Groups") == "Business/Interest Group"

def test_business_interest_group_lowercase():
    assert canonicalize_requester_type("business/interest group") == "Business/Interest Group"

def test_business_interest_ocr_wrap():
    # "Business/Inte rest Group" — OCR word-wrap artefact (36 rows in analysis)
    assert canonicalize_requester_type("Business/Inte rest Group") == "Business/Interest Group"


# ── Elected-Oireachtas ──────────────────────────────────────
def test_oireachtas_canonical():
    assert canonicalize_requester_type("Oireachtas") == "Elected-Oireachtas"

def test_oireachtas_uppercase():
    assert canonicalize_requester_type("OIREACHTAS") == "Elected-Oireachtas"

def test_oireachtas_public_representatives():
    assert canonicalize_requester_type("Oireachtas/Public Representatives") == "Elected-Oireachtas"

def test_oireachtas_public_representative_singular():
    assert canonicalize_requester_type("Oireachtas/Public Representative") == "Elected-Oireachtas"

def test_oireachtas_with_spaces_around_slash():
    assert canonicalize_requester_type("Oireachtas / Public Representative") == "Elected-Oireachtas"

def test_oireachtas_member_councillor():
    assert canonicalize_requester_type("Oireachtas Member/Councillor") == "Elected-Oireachtas"

def test_oireachtas_elected_representative():
    assert canonicalize_requester_type("Oireachtas/Elected Representative") == "Elected-Oireachtas"

def test_oireachtas_typo_oireactas():
    assert canonicalize_requester_type("Oireactas / Public Reps") == "Elected-Oireachtas"

def test_member_of_oireachtas():
    assert canonicalize_requester_type("Member of Oireachtas") == "Elected-Oireachtas"

def test_member_of_the_oireachtas():
    assert canonicalize_requester_type("Member of the Oireachtas") == "Elected-Oireachtas"

def test_oireachtas_member():
    assert canonicalize_requester_type("Oireachtas Member") == "Elected-Oireachtas"

def test_oireachtas_public_reps():
    assert canonicalize_requester_type("Oireachtas / Public Reps") == "Elected-Oireachtas"


# ── Elected-Councillor ──────────────────────────────────────
def test_councillor_maps_to_elected_councillor():
    assert canonicalize_requester_type("Councillor") == "Elected-Councillor"

def test_member_of_local_authority_maps_to_elected_councillor():
    assert canonicalize_requester_type("Member of Local Authority") == "Elected-Councillor"


# ── Elected-Unknown ─────────────────────────────────────────
def test_public_representative_maps_to_elected_unknown():
    assert canonicalize_requester_type("Public Representative") == "Elected-Unknown"

def test_politician_maps_to_elected_unknown():
    assert canonicalize_requester_type("Politician") == "Elected-Unknown"

def test_elected_member_maps_to_elected_unknown():
    assert canonicalize_requester_type("Elected Member") == "Elected-Unknown"


# ── Media ───────────────────────────────────────────────────
def test_media_canonical():
    assert canonicalize_requester_type("Media") == "Media"

def test_press_maps_to_media():
    assert canonicalize_requester_type("Press") == "Media"

def test_reporter_maps_to_media():
    assert canonicalize_requester_type("Reporter") == "Media"

def test_media_lowercase():
    assert canonicalize_requester_type("media") == "Media"


# ── Individual ──────────────────────────────────────────────
def test_individual_canonical():
    assert canonicalize_requester_type("Individual") == "Individual"

def test_individual_lowercase():
    assert canonicalize_requester_type("individual") == "Individual"


# ── Personal ────────────────────────────────────────────────
def test_personal_canonical():
    assert canonicalize_requester_type("Personal") == "Personal"

def test_personal_uppercase():
    assert canonicalize_requester_type("PERSONAL") == "Personal"


# ── Staff ───────────────────────────────────────────────────
def test_staff_canonical():
    assert canonicalize_requester_type("Staff") == "Staff"

def test_staff_uppercase():
    assert canonicalize_requester_type("STAFF") == "Staff"


# ── Public ──────────────────────────────────────────────────
def test_public_canonical():
    assert canonicalize_requester_type("Public") == "Public"

def test_public_lowercase():
    assert canonicalize_requester_type("public") == "Public"


# ── Solicitor ───────────────────────────────────────────────
def test_solicitor_canonical():
    assert canonicalize_requester_type("Solicitor") == "Solicitor"

def test_solicitors_plural():
    assert canonicalize_requester_type("Solicitors") == "Solicitor"


# ── Junk / unclassifiable → None ────────────────────────────
def test_category_header_returns_none():
    # "Category" — column header leaking in (14 rows in analysis)
    assert canonicalize_requester_type("Category") is None

def test_type_header_returns_none():
    # "Type" — column header leaking in (9 rows in analysis)
    assert canonicalize_requester_type("Type") is None

def test_su_abbreviation_returns_none():
    # "SU" — unknown abbreviation (15 rows)
    assert canonicalize_requester_type("SU") is None

def test_member_of_truncated_returns_none():
    # "Member of" — truncated value (91 rows), not enough context to classify
    assert canonicalize_requester_type("Member of") is None

def test_erest_group_split_token_returns_none():
    # "erest group" — second half of OCR-split "Business/Interest Group" (13 rows)
    assert canonicalize_requester_type("erest group") is None

def test_the_public_split_token_returns_none():
    # "the Public" — second half of OCR-split "Member of the Public" (28 rows)
    assert canonicalize_requester_type("the Public") is None


# ── Task 2: high-volume synonym additions ───────────────────

@pytest.mark.parametrize("raw,expected", [
    # business — singular bare word (911 errors 'Business', 54 'BUSINESS')
    ("Business", "Business/Interest Group"),
    ("business", "Business/Interest Group"),
    ("BUSINESS", "Business/Interest Group"),
    # association variants (116 errors)
    ("Association", "Business/Interest Group"),
    ("Residents Association", "Business/Interest Group"),
    ("Housing Association", "Business/Interest Group"),
    ("Campaign Organisation", "Business/Interest Group"),
    ("App.Housing Body", "Business/Interest Group"),
    # member of business/interest group (122 errors)
    ("Member of Business/Interest group", "Business/Interest Group"),
    ("Member of Business/Interest Group", "Business/Interest Group"),
    # industry / business-industry compound (43 + 39 errors)
    ("Industry", "Business/Interest Group"),
    ("Business / Industry", "Business/Interest Group"),
    # group variants (98 + 26 + 11 + 8 + 5 errors)
    ("Group", "Business/Interest Group"),
    ("Groups", "Business/Interest Group"),
    ("Interested Group", "Business/Interest Group"),
    ("Interest Group", "Business/Interest Group"),
    ("Business/ Interest Groups", "Business/Interest Group"),
    ("Group Business/Interest", "Business/Interest Group"),
    # company / ngo / charitable (23 + 7 + 6 errors)
    ("Company", "Business/Interest Group"),
    ("NGO", "Business/Interest Group"),
    ("Charitable Organisation", "Business/Interest Group"),
    # OCR word-wrap variant (5 errors)
    ("Business/In terest Group", "Business/Interest Group"),
    # Non-Personal compound variants (196 + 145 + 9 errors)
    ("Individual (Non-Personal)", "Non-Personal"),
    ("Individual (Non- Personal)", "Non-Personal"),
    ("non -personal", "Non-Personal"),
    # Individual (personal) compound (39 errors)
    ("Individual (Personal)", "Personal"),
    # Private individual (29 + 28 errors)
    ("Private individual", "Individual"),
    ("Private Individual", "Individual"),
    # Applicant (76 errors)
    ("Applicant", "Other"),
    # Business/Interest sub-variants already in lookup but tested for confidence
    ("Business/ Interest", "Business/Interest Group"),
])
def test_task2_high_volume_synonyms(raw, expected):
    """High-volume missing synonyms from full error-set analysis."""
    assert canonicalize_requester_type(raw) == expected, f"Expected {raw!r} → {expected!r}"


# ── Task 3: elected-representative synonym variants ─────────

@pytest.mark.parametrize("raw,expected", [
    # Oireachtas plural form (9 errors)
    ("Oireachtas Members", "Elected-Oireachtas"),
    # Standalone Oireactas typo — missing 'h' (not already covered by compound form)
    ("Oireactas", "Elected-Oireachtas"),
    # Oireachtas/Public shorthand (5 errors)
    ("Oireachtas/Public", "Elected-Oireachtas"),
    # TD / Senator — explicit national parliament members (10 errors)
    ("TD / Senator", "Elected-Oireachtas"),
    ("td / senator", "Elected-Oireachtas"),
    # Public Rep — common Irish abbreviation for TD/Senator (9 errors)
    ("Public Rep", "Elected-Oireachtas"),
    ("public rep", "Elected-Oireachtas"),
])
def test_task3_elected_representative_variants(raw, expected):
    """Additional elected-representative synonym forms."""
    assert canonicalize_requester_type(raw) == expected, f"Expected {raw!r} → {expected!r}"
