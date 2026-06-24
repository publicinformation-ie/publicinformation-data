def derive_category(body):
    if body.get("description_for_sub_sector") == "Local Authorities":
        return "local authority"
    if (body.get("legal_status") == "Vote"
            and body.get("government_department_id") == body.get("public_body_id")):
        return "government department"
    return "public body"
