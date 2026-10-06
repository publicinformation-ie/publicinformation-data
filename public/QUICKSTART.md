# Developer Quickstart

The smallest, most stable dataset — Public Bodies — is the easiest place to start.

## curl + jq

```sh
curl -s https://data.publicinformation.ie/latest/public-bodies/public-bodies.jsonld \
  | jq -r '.["@graph"][0].name'
```

## JavaScript fetch

```js
const res = await fetch(
  "https://data.publicinformation.ie/latest/public-bodies/public-bodies.jsonld"
);
const data = await res.json();
console.log(data["@graph"][0].name);
```

> This is JSON-LD — treat it as regular JSON unless you need `@context`.

## `latest/` vs a versioned path

`latest/public-bodies/` always points at the newest release — use
it for a stable URL that never breaks. A versioned path like
`v2.0.0/public-bodies/` is an immutable, pinned reference — use it
when you need to guarantee you're always reading exactly the same bytes,
regardless of future releases.

---

Full field-by-field reference and vocabularies: [Public Bodies](latest/public-bodies/README.md), [FOI Disclosures](latest/foi-disclosures/README.md), [FOI Request Files](latest/foi-request-files/README.md), [Who Does What](latest/who-does-what/README.md).

Before trusting a field in production, check [Data quality & contributing](DATA_QUALITY.md) for the machine-readable status/confidence signals.
