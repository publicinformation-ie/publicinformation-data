import sys
from pathlib import Path

# Add repo root to path so tests can import from src
repo_root = Path(__file__).parent.parent
for path in (repo_root, repo_root / "scripts", repo_root / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
