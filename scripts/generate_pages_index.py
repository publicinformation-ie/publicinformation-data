#!/usr/bin/env python3
"""Generate a plain static directory index for the Codeberg Pages build.

Walks a directory tree and writes an `index.html` into its root: a nested
listing of folders and files with relative links and file sizes. No JS, no
external assets, inline CSS only.

This only ever runs against the `pages` branch build snapshot (see
scripts/publish_pages.sh) — never against public/ on main.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

_HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>data.publicinformation.ie</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 60rem; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  ul { list-style: none; padding-left: 1.25rem; }
  li { margin: 0.15rem 0; }
  .dir > .name::after { content: "/"; }
  .dir > .name { font-weight: 600; }
  .size { color: #666; font-size: 0.85em; margin-left: 0.5em; }
  a { color: #0645ad; text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>data.publicinformation.ie</h1>
"""

_TAIL = """</body>
</html>
"""


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def _render_dir(dir_path: Path, root_dir: Path) -> str:
    entries = sorted(
        dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
    )
    lines = ["<ul>"]
    for entry in entries:
        if entry.name == "index.html" and entry.parent == root_dir:
            continue
        if entry.name.startswith("."):
            continue
        rel = entry.relative_to(root_dir).as_posix()
        name = html.escape(entry.name)
        if entry.is_dir():
            lines.append(f'<li class="dir"><a class="name" href="{rel}/">{name}</a>')
            lines.append(_render_dir(entry, root_dir))
            lines.append("</li>")
        else:
            size = _human_size(entry.stat().st_size)
            lines.append(
                f'<li class="file"><a class="name" href="{rel}">{name}</a>'
                f'<span class="size">{size}</span></li>'
            )
    lines.append("</ul>")
    return "\n".join(lines)


def generate_index(root_dir: Path) -> None:
    """Write index.html into root_dir listing its contents recursively."""
    body = _render_dir(root_dir, root_dir)
    (root_dir / "index.html").write_text(_HEAD + body + _TAIL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root_dir", type=Path, help="Directory to index")
    args = parser.parse_args()
    generate_index(args.root_dir)


if __name__ == "__main__":
    main()
