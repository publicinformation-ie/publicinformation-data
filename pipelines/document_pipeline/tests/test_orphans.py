import pytest

from orphans import apply_manifest, find_orphans

KEEP = {"keep-me"}


@pytest.fixture
def tree(tmp_path):
    pipeline = tmp_path / "document_pipeline"
    public = tmp_path / "public" / "documents"
    for step, sub in (("fetch_pdfs", "pdfs"), ("extract_pages", "pages"),
                      ("assemble_sections", "sections"), ("extract_figures", "assets")):
        d = pipeline / "steps" / step / sub
        d.mkdir(parents=True)
        if sub == "pdfs":
            (d / "keep-me.pdf").write_bytes(b"x")
            (d / "stale-doc.pdf").write_bytes(b"x")
        else:
            (d / "keep-me").mkdir()
            (d / "stale-doc").mkdir()
            (d / "stale-doc" / "p1.png").write_bytes(b"x")
    (pipeline / "steps" / "find_plan_pdfs").mkdir()
    (pipeline / "steps" / "find_plan_pdfs" / "output.json").write_text("{}")
    public.mkdir(parents=True)
    (public / "index.json").write_text("{}")
    (public / "index.html").write_text("")
    (public / "keep-me").mkdir()
    (public / "stale-doc").mkdir()
    (public / "actions.json").write_text("[]")
    return pipeline, public


def test_find_orphans_lists_only_unkept_artefacts(tree):
    pipeline, public = tree
    found = {p.relative_to(pipeline.parent).as_posix() for p in find_orphans(KEEP, pipeline, public)}
    assert "document_pipeline/steps/fetch_pdfs/pdfs/stale-doc.pdf" in found
    assert "document_pipeline/steps/extract_pages/pages/stale-doc" in found
    assert "document_pipeline/steps/find_plan_pdfs" in found
    assert "public/documents/stale-doc" in found
    assert "public/documents/actions.json" in found
    assert not any("keep-me" in f for f in found)
    assert not any(f.endswith(("index.json", "index.html")) for f in found)


def test_apply_deletes_exactly_the_manifest(tree, tmp_path):
    pipeline, public = tree
    orphans = find_orphans(KEEP, pipeline, public)
    manifest = tmp_path / "m.md"
    manifest.write_text("# manifest\n" + "\n".join(f"- `{p}`" for p in orphans) + "\n")
    deleted = apply_manifest(manifest, pipeline, public, KEEP)
    assert set(deleted) == set(orphans)
    assert (public / "keep-me").exists() and (public / "index.json").exists()
    assert not (public / "stale-doc").exists()


@pytest.mark.parametrize("bad", [
    "../outside",                       # absolute path outside every root
    "steps/fetch_pdfs/pdfs/keep-me.pdf",  # a kept slug
    "steps/fetch_pdfs/output.json",     # not an artefact root
    "steps/fetch_pdfs/pdfs/../../fetch_pdfs/output.json",  # literal .. segment
    "steps/extract_figures/contact-sheets/keep-me.html",   # kept slug, html artefact
])
def test_apply_refuses_unsafe_paths_and_deletes_nothing(tree, tmp_path, bad):
    pipeline, public = tree
    target = (pipeline / bad) if not bad.startswith("..") else (tmp_path / "outside")
    target.parent.resolve().mkdir(parents=True, exist_ok=True)
    target.write_text("x")
    stale = pipeline / "steps" / "fetch_pdfs" / "pdfs" / "stale-doc.pdf"
    manifest = tmp_path / "m.md"
    manifest.write_text(f"- `{stale}`\n- `{target}`\n")
    with pytest.raises(ValueError):
        apply_manifest(manifest, pipeline, public, KEEP)
    assert target.exists() and stale.exists()          # all-or-nothing


def test_apply_refuses_a_symlink_that_escapes(tree, tmp_path):
    pipeline, public = tree
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    link = public / "stale-link"
    link.symlink_to(outside)
    manifest = tmp_path / "m.md"
    manifest.write_text(f"- `{link}`\n")
    with pytest.raises(ValueError):
        apply_manifest(manifest, pipeline, public, KEEP)
    assert outside.exists()


def test_contact_sheet_html_slugs(tree):
    pipeline, public = tree
    cs = pipeline / "steps" / "extract_figures" / "contact-sheets"
    cs.mkdir()
    (cs / "keep-me.html").write_text("x")
    (cs / "stale-one.html").write_text("x")
    found = {p.name for p in find_orphans(KEEP, pipeline, public)}
    assert "stale-one.html" in found and "keep-me.html" not in found


def test_apply_refuses_intermediate_symlink(tree, tmp_path):
    pipeline, public = tree
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "stale-doc").write_text("x")
    link = pipeline / "steps" / "extract_pages" / "pages" / "linkdir"
    link.symlink_to(outside)
    manifest = tmp_path / "m.md"
    manifest.write_text(f"- `{link / 'stale-doc'}`\n")
    with pytest.raises(ValueError):
        apply_manifest(manifest, pipeline, public, KEEP)
    assert (outside / "stale-doc").exists()
