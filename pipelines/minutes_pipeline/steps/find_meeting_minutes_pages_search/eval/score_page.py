"""Shared PDF-yield scoring re-export.

The scorer moved to `steps/minutes_scoring` so the live crawl/search steps
can import one neutral module. This file re-exports `collect_yield` so all
existing importers (eval, experiments, tests) keep working unchanged.
"""
from steps.minutes_scoring import collect_yield  # noqa: E402