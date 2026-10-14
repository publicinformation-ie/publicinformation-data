---
name: transport-governance
description: "Use when determining which Irish body plans, funds, specifies, consents, delivers, operates, maintains, regulates or enforces any part of transport in the Greater Dublin Area, or when writing public copy about who decides a transport matter."
---

# Transport governance (GDA)

A model of who does what in transport for the seven GDA local authorities: 17 subdomains × 10
functions, each row naming one A (approves and answers for the output), the R bodies (do the
work) and the C bodies (consulted).

## Routing

- What a term, body ID, function or subdomain means, and which subdomain a question belongs to →
  `vocabulary.md` (see its Boundary rules).
- Who does what → `raci-gda.md`. Grep instead of reading it whole:
  - one subdomain: `grep -n -A 25 '^### svc/spsv' raci-gda.md`
  - one body: `grep -n 'NTA' raci-gda.md`
- Changing or validating the model → `checks.md`. Read it only then.

## How to answer

1. Classify the question as subdomain × function, using the Boundary rules.
2. Answer with the row and its A and R, e.g.
   `infra/kerbside · Regulation · appointed stand → A: LA-members, R: LA-CE`.
   If the function is listed under `Not applicable`, say that no body has that role.
3. Every row is `verify` until the user confirms it. Say so when an answer rests on one.
4. The model covers the GDA only. Outside it, say the model does not apply.

## Registers

- Internal analysis and model files: canonical IDs and terms only.
- Public-facing copy: the Plain label column from `vocabulary.md`; no IDs, no row references.
- The Banned terms table in `vocabulary.md` applies to both registers.
