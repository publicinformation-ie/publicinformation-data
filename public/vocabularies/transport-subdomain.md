# Transport subdomains (retired)

This vocabulary held 17 transport subdomain terms used to tag SPC agenda items.
It is **retired**: the published replacement is
[transport-activity](transport-activity.md), and the SPC meetings dataset
publishes `groupings` instead of `subdomains`.

The CSV and its CSVW metadata stay published unchanged at their existing URLs,
so an existing link keeps working. This page, the Turtle file and the resolver
page record that each term is deprecated and what replaces it.

- Namespace: `https://data.publicinformation.ie/ns/transport-subdomain#`
- CSV: [transport-subdomain.csv](transport-subdomain.csv) (CSVW metadata: [transport-subdomain.csv-metadata.json](transport-subdomain.csv-metadata.json))
- SKOS Turtle: [transport-subdomain.ttl](transport-subdomain.ttl)
- Resolver page: [/ns/transport-subdomain/](https://data.publicinformation.ie/ns/ns/transport-subdomain)
- Replacement vocabulary: [transport-activity.md](transport-activity.md)

| Retired term | Replaced by |
|---|---|
| `infra/national-roads` | `RT1` |
| `infra/regional-local-roads` | `RT1` |
| `infra/active-travel` | `RT2`, `RT3` |
| `infra/bus` | `RT4` |
| `infra/heavy-rail` | `RL1` |
| `infra/light-rail` | `RL2` |
| `infra/kerbside` | `RT7` |
| `infra/ports-airfields` | `WT1`, `AT1` |
| `svc/pso-bus` | `RT5` |
| `svc/commercial-bus` | `RT5` |
| `svc/rail` | `RL3` |
| `svc/light-rail` | none: The current model has urban rapid transit infrastructure (RL2) but no services grouping, so this retired term has no grouping equivalent. |
| `svc/spsv` | `RT5` |
| `svc/school-transport` | `X6` |
| `svc/shared-mobility` | `RT5` |
| `users/vehicles-drivers` | `RT8` |
| `users/traffic-law` | `X1` |
