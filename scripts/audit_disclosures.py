#!/usr/bin/env python3
"""Diagnostic script: rank FOI disclosure source files by data-quality error count."""

import argparse
import sys
from dataclasses import dataclass

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "src"))
from lib.db_client import DbClient


@dataclass
class Check:
    name: str
    description: str
    where_clause: str


CHECKS: list[Check] = [
    Check(
        name="blank_request_description",
        description="blank_request_description",
        where_clause="request_description IS NULL OR request_description = ''",
    ),
    Check(
        name="invalid_decision_date",
        description="invalid_decision_date",
        where_clause="decision_date IS NOT NULL AND date(decision_date) IS NULL",
    ),
    Check(
        name="invalid_date_received",
        description="invalid_date_received",
        where_clause="date_received IS NOT NULL AND date(date_received) IS NULL",
    ),
    Check(
        name="decision_status_is_date",
        description="decision_status_is_date",
        where_clause="decision_status IS NOT NULL AND date(decision_status) IS NOT NULL",
    ),
]


def get_check(name: str) -> "Check | None":
    for c in CHECKS:
        if c.name == name:
            return c
    return None
