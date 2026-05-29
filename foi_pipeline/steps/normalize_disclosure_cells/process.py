#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "normalize_disclosure_cells"
