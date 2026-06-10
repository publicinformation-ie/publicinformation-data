#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

STEP_NAME = "sync_backlog"
CODEBERG_API = "https://codeberg.org/api/v1"
CODEBERG_REPO = os.getenv("CODEBERG_REPO", "publicinformation/publicinformation-data")

SEVERITY_WEIGHT = {"error": 3, "warning": 2, "info": 1}

REQUIRED_LABELS = [
    {"name": "pipeline-issue", "color": "#0075ca"},
    {"name": "severity:error", "color": "#d73a4a"},
    {"name": "severity:warning", "color": "#e4e669"},
    {"name": "severity:info", "color": "#cfd3d7"},
    {"name": "priority:high", "color": "#b60205"},
    {"name": "priority:medium", "color": "#fbca04"},
    {"name": "priority:low", "color": "#0075ca"},
]


def make_key(step_name: str, issue: dict) -> str:
    raw = issue.get("error_type") or issue.get("description", "")
    slug = raw.lower().replace(" ", "_").replace("/", "_")[:40]
    return f"{step_name}:{slug}"


def _step_weight(step_name: str, pipeline_steps: list) -> float:
    n = len(pipeline_steps)
    if n <= 1:
        return 2.0
    idx = pipeline_steps.index(step_name) if step_name in pipeline_steps else 0
    return 2.0 - idx / (n - 1)


def score_issue(step_name: str, issue: dict, pipeline_steps: list) -> float:
    sw = SEVERITY_WEIGHT.get(issue.get("severity", "info"), 1)
    affected = issue.get("affected_count") or 0
    pw = _step_weight(step_name, pipeline_steps)
    return sw * affected * pw
