#!/usr/bin/env python3
"""Write the closed vocabularies the SPC meetings dataset publishes.

Usage:
    uv run python pipelines/spc_pipeline/scripts/build_vocabularies.py

The transport-subdomain list is derived from the committed reference data; the
small term lists are defined here. Each vocabulary is a CSV file plus CSVW
metadata, following public/vocabularies/. The transport-subdomain vocabulary is
retired: beside its unchanged CSV this script writes the SKOS Turtle, the human
page and the resolver page that record each term as deprecated and name its
replacement. COFOG is not written here: the cofog-1999 vocabulary is generated
by the root script `scripts/build_cofog_vocabulary.py`.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1]
REPO = PIPELINE.parents[1]
OUT = REPO / "public" / "vocabularies"
NS_DIR = REPO / "public" / "ns"

BASE = "https://data.publicinformation.ie/ns"
COLUMNS = [
    {"name": "uri", "titles": "URI", "datatype": "uri",
     "description": "Persistent URI for this term"},
    {"name": "notation", "titles": "Notation", "datatype": "string",
     "description": "Short notation used in the dataset"},
    {"name": "name", "titles": "Name", "datatype": "string",
     "description": "Human-readable name"},
    {"name": "description", "titles": "Description", "datatype": "string",
     "description": "Meaning of the term"},
]

SPC_TERMS = {
    "spc-attendance-status": ("spc", [
        ("present", "Present", "Recorded as attending the meeting."),
        ("apologies", "Apologies", "Listed under apologies or absent, so did not attend."),
        ("absent", "Absent", "Listed as not present, separately from any apologies."),
    ]),
    "spc-attendance-mode": ("spc", [
        ("remote", "Remote", "Attended online or via Teams."),
        ("in_person", "In person", "Attended in person."),
        ("not_stated", "Mode not stated", "The minutes do not say how the person attended."),
    ]),
    "spc-attendee-category": ("spc", [
        ("councillors", "Councillors", "Elected members of the committee."),
        ("sectoral_representatives", "Sectoral representatives", "Sectoral or PPN representatives."),
        ("apologies", "Apologies", "People listed as absent or sending apologies."),
        ("officials", "Officials", "Council officials present."),
        ("presenters", "Presenters", "People who made a presentation to the committee."),
        ("guests", "Guests", "Guests of the committee, listed apart from its members and officials."),
        ("absent", "Absent", "People listed as not present, separately from any apologies."),
    ]),
    "spc-text-source": ("spc", [
        ("text_layer", "Text layer", "Every page was read from the PDF's own text layer."),
        ("ocr", "OCR", "Every page is a scan, read by optical character recognition."),
        ("mixed", "Mixed", "Some pages were read from the text layer and some by OCR."),
    ]),
    "spc-decision-type": ("spc", [
        ("agreed", "Agreed", "The committee agreed a course of action."),
        ("adopted", "Adopted", "The committee adopted a document or policy."),
        ("recommended_to_council", "Recommended to council", "The committee recommended a matter to the full council."),
        ("referred", "Referred", "The committee referred an item onward or to a later meeting."),
        ("deferred", "Deferred", "The committee deferred an item."),
        ("appointment", "Appointment", "The committee appointed or elected someone to a role."),
    ]),
}


def write_vocabulary(name: str, namespace: str, rows: list[dict]) -> None:
    csv_path = OUT / f"{name}.csv"
    metadata_path = OUT / f"{name}.csv-metadata.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["uri", "notation", "name", "description"])
        writer.writeheader()
        writer.writerows(rows)
    metadata_path.write_text(json.dumps({
        "@context": "http://www.w3.org/ns/csvw",
        "url": csv_path.name,
        "tableSchema": {"columns": COLUMNS, "primaryKey": "uri",
                        "aboutUrl": "{uri}"},
    }, indent=2) + "\n", encoding="utf-8")


def spc_rows(namespace: str, terms) -> list[dict]:
    return [{
        "uri": f"{BASE}/{namespace}#{notation}",
        "notation": notation,
        "name": label,
        "description": description,
    } for notation, label, description in terms]


def subdomain_rows() -> list[dict]:
    data = json.loads((PIPELINE / "reference" / "transport_subdomains.json").read_text())
    return [{
        "uri": f"{BASE}/transport-subdomain#{entry['id']}",
        "notation": entry["id"],
        "name": entry["term"],
        "description": entry["plain_label"],
    } for entry in data["subdomains"]]


def subdomain_entries() -> list[dict]:
    """The committed crosswalk: retired terms with their replacement groupings."""
    data = json.loads((PIPELINE / "reference" / "transport_subdomains.json").read_text())
    return data["subdomains"]


def _ttl_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"@en'


def _replacement_note(entry: dict) -> str:
    groupings = entry.get("grouping_ids", [])
    if groupings:
        return f"Retired. Replaced by the transport-activity grouping {', '.join(groupings)}."
    return ("Retired. No transport-activity grouping replaces it: "
            + entry["no_replacement_reason"])


def subdomain_ttl(entries: list[dict]) -> str:
    """SKOS Turtle for the retired vocabulary: every term deprecated with its replacement."""
    lines = [
        "@prefix dct: <http://purl.org/dc/terms/> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        f"<{BASE}/transport-subdomain>",
        "    a skos:ConceptScheme ;",
        '    dct:title "Transport subdomains (retired)"@en ;',
        "    dct:license <https://creativecommons.org/licenses/by/4.0/> ;",
        "    dct:description "
        + _ttl_string(
            "Retired transport subdomain vocabulary. Each term is deprecated and linked "
            "to the transport-activity grouping that replaces it. The CSV and its CSVW "
            "metadata stay published unchanged at their existing URLs.")
        + " ;",
        "    skos:hasTopConcept "
        + ", ".join(f"<{BASE}/transport-subdomain#{entry['id']}>" for entry in entries)
        + " .",
    ]
    for entry in entries:
        lines += [
            "",
            f"<{BASE}/transport-subdomain#{entry['id']}>",
            "    a skos:Concept ;",
            f"    skos:notation {_ttl_string(entry['id'])} ;",
            f"    skos:prefLabel {_ttl_string(entry['term'])} ;",
            f"    skos:definition {_ttl_string(entry['plain_label'])} ;",
            f"    skos:note {_ttl_string(_replacement_note(entry))} ;",
            "    owl:deprecated true ;",
        ]
        replacements = entry.get("grouping_ids", [])
        if replacements:
            lines.append(
                "    dct:isReplacedBy "
                + ", ".join(f"<{BASE}/transport-activity#{grouping}>"
                            for grouping in replacements)
                + " ;")
        lines.append(f"    skos:inScheme <{BASE}/transport-subdomain> .")
    return "\n".join(lines) + "\n"


def subdomain_markdown(entries: list[dict]) -> str:
    lines = [
        "# Transport subdomains (retired)",
        "",
        "This vocabulary held 17 transport subdomain terms used to tag SPC agenda items.",
        "It is **retired**: the published replacement is",
        f"[transport-activity](transport-activity.md), and the SPC meetings dataset",
        "publishes `groupings` instead of `subdomains`.",
        "",
        "The CSV and its CSVW metadata stay published unchanged at their existing URLs,",
        "so an existing link keeps working. This page, the Turtle file and the resolver",
        "page record that each term is deprecated and what replaces it.",
        "",
        f"- Namespace: `{BASE}/transport-subdomain#`",
        f"- CSV: [transport-subdomain.csv](transport-subdomain.csv) "
        "(CSVW metadata: [transport-subdomain.csv-metadata.json]"
        "(transport-subdomain.csv-metadata.json))",
        "- SKOS Turtle: [transport-subdomain.ttl](transport-subdomain.ttl)",
        f"- Resolver page: [/ns/transport-subdomain/]({BASE}/ns/transport-subdomain)",
        "- Replacement vocabulary: [transport-activity.md](transport-activity.md)",
        "",
        "| Retired term | Replaced by |",
        "|---|---|",
    ]
    for entry in entries:
        groupings = entry.get("grouping_ids", [])
        replacement = (", ".join(f"`{grouping}`" for grouping in groupings)
                       if groupings else f"none: {entry['no_replacement_reason']}")
        lines.append(f"| `{entry['id']}` | {replacement} |")
    lines.append("")
    return "\n".join(lines)


def subdomain_resolver_page(entries: list[dict]) -> str:
    rows = "\n".join(
        f'  <tr><td><code>{entry["id"]}</code></td><td>{entry["term"]}</td><td>'
        + (", ".join(
            f'<a href="../transport-activity/#{grouping}">{grouping}</a>'
            for grouping in entry.get("grouping_ids", []))
           or f'none: {entry["no_replacement_reason"]}')
        + "</td></tr>"
        for entry in entries)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Transport subdomains (retired) — PublicInformation.ie</title>
<link rel="alternate" type="text/csv" title="Transport subdomains (CSV)" href="../../vocabularies/transport-subdomain.csv">
<link rel="describedby" type="application/ld+json" title="Transport subdomains (CSVW metadata)" href="../../vocabularies/transport-subdomain.csv-metadata.json">
<link rel="alternate" type="text/turtle" title="Transport subdomains (Turtle)" href="../../vocabularies/transport-subdomain.ttl">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 64rem; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ font-size: 1.6rem; }}
  p.lead {{ font-size: 1.05rem; color: #333; }}
  a {{ color: #0645ad; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; margin: 1rem 0; width: 100%; }}
  th, td {{ text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #ddd; font-size: 0.95em; vertical-align: top; }}
  th {{ color: #555; font-weight: 600; }}
  code {{ background: #f2f2f2; padding: 0.1em 0.35em; border-radius: 3px; }}
</style>
</head>
<body>
<h1>Transport subdomains (retired)</h1>
<p class="lead">This vocabulary is retired. The 17 terms below were used to tag SPC
agenda items; they are replaced by
<a href="../transport-activity/">transport-activity</a> groupings, and the SPC
meetings dataset publishes <code>groupings</code> instead of <code>subdomains</code>.
The <a href="../../vocabularies/transport-subdomain.csv">CSV</a> stays published
unchanged so an existing link keeps working.</p>

<h2>Downloads</h2>
<table>
  <tr><th>Format</th><th>File</th><th>Use it for</th></tr>
  <tr><td>CSV</td><td><a href="../../vocabularies/transport-subdomain.csv">transport-subdomain.csv</a></td>
      <td>The retired terms as published; CSVW metadata in
      <a href="../../vocabularies/transport-subdomain.csv-metadata.json">transport-subdomain.csv-metadata.json</a>.</td></tr>
  <tr><td>Turtle</td><td><a href="../../vocabularies/transport-subdomain.ttl">transport-subdomain.ttl</a></td>
      <td>SKOS with <code>owl:deprecated</code> and <code>dct:isReplacedBy</code>.</td></tr>
</table>

<h2>Retired terms and their replacements</h2>
<table>
  <tr><th>Term</th><th>Name</th><th>Replaced by</th></tr>
{rows}
</table>
</body>
</html>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (namespace, terms) in SPC_TERMS.items():
        write_vocabulary(name, namespace, spc_rows(namespace, terms))
    write_vocabulary("transport-subdomain", "transport-subdomain", subdomain_rows())
    entries = subdomain_entries()
    (OUT / "transport-subdomain.ttl").write_text(subdomain_ttl(entries), encoding="utf-8")
    (OUT / "transport-subdomain.md").write_text(subdomain_markdown(entries), encoding="utf-8")
    resolver = NS_DIR / "transport-subdomain"
    resolver.mkdir(parents=True, exist_ok=True)
    (resolver / "index.html").write_text(
        subdomain_resolver_page(entries), encoding="utf-8")
    print(f"Wrote vocabularies to {OUT}")


if __name__ == "__main__":
    main()
