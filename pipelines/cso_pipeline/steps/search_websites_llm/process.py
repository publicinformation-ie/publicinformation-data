#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from lib.cli_utils import add_common_args, filter_by_public_body
from lib.file_utils import append_error, read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "search_websites_llm"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_MODEL = "mistral-small"
MISTRAL_TIMEOUT = 60

_SYSTEM_PROMPT = "You are a research assistant. Return ONLY valid JSON, no prose."
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_NULL_FIELDS = {"llm_website_url": None, "llm_url_type": None, "llm_confidence": None, "llm_notes": None}


def build_user_prompt(body: dict) -> str:
    return (
        "Find the official website for this Irish public body.\n\n"
        f"Name: {body.get('name', '')}\n"
        f"Legal status: {body.get('legal_status') or 'none'}\n"
        f"Parent organization: {body.get('parent_name') or 'none'}\n"
        f"Government department: {body.get('government_department') or 'none'}\n"
        f"CRO number: {body.get('cro') or 'none'}\n\n"
        'Return this JSON exactly:\n'
        '{\n'
        '  "url": "https://... or null",\n'
        '  "url_type": "direct" | "parent" | "related" | null,\n'
        '  "confidence": "high" | "low" | "not_found",\n'
        '  "notes": "one sentence"\n'
        '}\n\n'
        'url_type meanings:\n'
        '- "direct": this entity has its own standalone website\n'
        '- "parent": only the parent organization\'s website found\n'
        '- "related": a related/subsidiary site found\n'
        '- null: nothing found\n\n'
        'confidence meanings:\n'
        '- "high": confident this is the direct standalone website\n'
        '- "low": uncertain, or only parent/related found\n'
        '- "not_found": no website found (url must be null)'
    )


def parse_llm_response(text: str) -> dict:
    """Return parsed dict from LLM response. Raises ValueError if unparseable."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]!r}")


def call_mistral(user_prompt: str, api_key: str) -> dict:
    """Call Mistral chat completions and return parsed result dict. Raises on any error."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    try:
        resp = requests.post(MISTRAL_API_URL, headers=headers, json=payload, timeout=MISTRAL_TIMEOUT)
    except requests.exceptions.Timeout as e:
        raise TimeoutError("Mistral request timed out") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Request error: {e}") from e
    if resp.status_code in (401, 403):
        raise PermissionError(f"Mistral auth failed (HTTP {resp.status_code}): check MISTRAL_API_KEY")
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    raw = resp.json()["choices"][0]["message"]["content"]
    return parse_llm_response(raw)


def process(input_data, step_dir, writer, api_key: str, delay=1.0, verbose=False):
    write_json(Path(step_dir) / "errors.json", [])
    bodies = input_data.get("public_bodies") or input_data.get("results", [])
    first = True
    for body in bodies:
        body_id = body["public_body_id"]
        if writer.is_processed(body_id):
            continue
        if not first:
            time.sleep(delay)
        first = False
        try:
            result = call_mistral(build_user_prompt(body), api_key)
            enriched = {
                **body,
                "llm_website_url": result.get("url"),
                "llm_url_type": result.get("url_type"),
                "llm_confidence": result.get("confidence"),
                "llm_notes": result.get("notes"),
            }
        except PermissionError as e:
            print(f"Fatal: {e}", file=sys.stderr)
            sys.exit(1)
        except TimeoutError as e:
            append_error(step_dir, {
                "step": STEP_NAME, "error_type": "LLMTimeoutError",
                "error_message": str(e), "context": {"public_body_id": body_id},
            })
            enriched = {**body, **_NULL_FIELDS}
        except RuntimeError as e:
            append_error(step_dir, {
                "step": STEP_NAME, "error_type": "LLMAPIError",
                "error_message": str(e), "context": {"public_body_id": body_id},
            })
            enriched = {**body, **_NULL_FIELDS}
        except ValueError as e:
            append_error(step_dir, {
                "step": STEP_NAME, "error_type": "LLMParseError",
                "error_message": str(e), "context": {"public_body_id": body_id},
            })
            enriched = {**body, **_NULL_FIELDS}
        writer.append([enriched])
        if verbose:
            print(".", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="LLM website search for CSO public bodies via Mistral")
    add_common_args(parser)
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds to pause between Mistral calls (default: 1)")
    args = parser.parse_args()

    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("Fatal: MISTRAL_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    step_dir = Path(__file__).parent
    output_path = Path(args.output)
    try:
        input_data = read_json(args.input)
    except Exception as e:
        print(f"Fatal: could not read input: {e}", file=sys.stderr)
        sys.exit(1)
    input_data = filter_by_public_body(input_data, args.public_body)
    writer = IncrementalWriter(output_path, STEP_NAME, force=args.force,
                               override_path=step_dir / "override.json")
    if writer.processed_keys:
        print(f"Resuming: {len(writer.processed_keys)} already done, skipping...")
    process(input_data, step_dir, writer, api_key=api_key, delay=args.delay, verbose=args.verbose)
    count = writer.finalize()
    write_status(step_dir, count)
    if args.verbose:
        print()
    print(f"Wrote {count} records to {output_path}")


if __name__ == "__main__":
    main()
