#!/usr/bin/env python3
import sys
from pathlib import Path

# pipelines/cso_pipeline/process.py → .parent.parent.parent = repo root
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from lib.pipeline_runner import main

if __name__ == "__main__":
    main()
