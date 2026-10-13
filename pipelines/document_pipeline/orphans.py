"""Orphan-artefact manifest and guarded deletion for document_pipeline.

Two stages, on purpose: `manifest` writes the list of paths that would go and
changes nothing; `apply` deletes exactly the paths in an (approved) manifest,
and only if every one of them is inside an artefact root and not a kept slug.
All-or-nothing: one unsafe path aborts before anything is deleted.
"""
import argparse
import re
import shutil
from pathlib import Path

from documents import load_documents

STEP_ARTEFACT_DIRS = ("pdfs", "pages", "assets", "sections", "contact-sheets")
RETIRED_STEP_DIRS = ("find_plan_pdfs",)
PUBLIC_KEEP_FILES = ("index.json", "index.html")
DEFAULT_MANIFEST = (Path(__file__).resolve().parents[2]
                    / "docs" / "superpowers" / "research" / "2026-10-13-deletion-manifest.md")


def _slug_of(path: Path) -> str:
    return path.name[:-4] if path.name.endswith(".pdf") else path.name


def find_orphans(keep_slugs, pipeline_dir, public_documents_dir) -> list:
    pipeline_dir, public_documents_dir = Path(pipeline_dir), Path(public_documents_dir)
    found = []
    steps = pipeline_dir / "steps"
    for step in sorted(p for p in steps.iterdir() if p.is_dir()):
        if step.name in RETIRED_STEP_DIRS:
            found.append(step)
            continue
        for sub in STEP_ARTEFACT_DIRS:
            root = step / sub
            if root.is_dir():
                found += [c for c in sorted(root.iterdir()) if _slug_of(c) not in keep_slugs]
    if public_documents_dir.is_dir():
        found += [c for c in sorted(public_documents_dir.iterdir())
                  if c.name not in PUBLIC_KEEP_FILES and c.name not in keep_slugs]
    return sorted(found)


def _allowed(path: Path, pipeline_dir: Path, public_documents_dir: Path, keep_slugs) -> bool:
    if path.is_symlink() or path.resolve() != Path(path).absolute().resolve():
        return False
    resolved = path.resolve()
    parent = resolved.parent
    steps = pipeline_dir.resolve() / "steps"
    if parent == public_documents_dir.resolve():
        return resolved.name not in PUBLIC_KEEP_FILES and resolved.name not in keep_slugs
    if parent == steps:
        return resolved.name in RETIRED_STEP_DIRS
    if parent.name in STEP_ARTEFACT_DIRS and parent.parent.parent == steps:
        return _slug_of(resolved) not in keep_slugs
    return False


def apply_manifest(manifest_path, pipeline_dir, public_documents_dir, keep_slugs) -> list:
    pipeline_dir, public_documents_dir = Path(pipeline_dir), Path(public_documents_dir)
    listed = [Path(m) for m in re.findall(r"^- `([^`]+)`$",
                                          Path(manifest_path).read_text(encoding="utf-8"), re.M)]
    for path in listed:
        if not _allowed(path, pipeline_dir, public_documents_dir, keep_slugs):
            raise ValueError(f"refusing to delete {path}: not an orphaned artefact path")
    for path in listed:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)
    return listed


def _paths():
    pipeline_dir = Path(__file__).resolve().parent
    return pipeline_dir, pipeline_dir.parents[1] / "public" / "documents"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("manifest", "apply"))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    pipeline_dir, public_dir = _paths()
    keep = {d["doc_slug"] for d in load_documents()}
    if args.command == "manifest":
        orphans = find_orphans(keep, pipeline_dir, public_dir)
        lines = ["# Deletion manifest — NOT YET APPROVED", "",
                 f"Keeps {len(keep)} documents from documents.yml. Deleting {len(orphans)} paths.",
                 "", "## Paths", "", *[f"- `{p}`" for p in orphans], ""]
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {len(orphans)} paths to {args.manifest} (nothing deleted)")
    else:
        deleted = apply_manifest(args.manifest, pipeline_dir, public_dir, keep)
        print(f"Deleted {len(deleted)} paths")


if __name__ == "__main__":
    main()
