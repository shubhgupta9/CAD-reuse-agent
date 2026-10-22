# CAD Reuse Assistant — Matching Approach (Design Note)

**Context.** The assistant takes a required (missing) part's specification and searches the PLM database (Cascadia) for an existing part that can be reused. This note addresses the feedback that the current matching is name-based only, and proposes how to make it match on **dimensions** and **functionality** instead.

## 1. The current limitation

Today the search matches the part *name* as a text substring (SQL `ILIKE`). The requirement's type, material, and function are reduced to keywords and looked for inside the name. This is string overlap — it carries no understanding of what a part *is*, how *large* it is, or whether it can *physically substitute* for the required part.

## 2. Why name matching is not enough

Two parts can share a name and be completely unusable as substitutes:

> *A search for a **truck tire** that also returns a **bicycle tire** is not useful — both contain the word "tire", but they differ by an order of magnitude in dimensions and load.*

The failure has a second form. Suppose the required part is **X**. The inventory does not have X, but it has:
- **X1** — a different name, but dimensionally and functionally very close to X (the correct reuse candidate), and
- **Y** — a similar *name* to X, but a different function/size.

Name search recommends **Y** (name overlap). The system *should* recommend **X1** (functional and dimensional closeness). Fixing this requires matching on specifications, not text.

## 3. Proposed approach — three layers

**Layer 1 — Structured specifications.** Compare parts on explicit fields rather than names: part type, bore/shaft diameter, length, thread size, load rating, material, mounting. These fields are what distinguish a truck tire from a bicycle tire even when both are called "tire".

**Layer 2 — Compatibility gate (hard filter on dimensions).** Reject any candidate that cannot physically substitute for the requirement — e.g. bore diameter outside a tolerance band, incompatible thread size, or insufficient load rating. This is the direct answer to the tire analogy: the bicycle tire fails the truck's dimensional gate and is never recommended, regardless of name similarity.

**Layer 3 — Closeness ranking (soft score on survivors).** Among candidates that pass the gate, rank by how close they are to the requirement: numeric distance on the key dimensions, plus **functional similarity**, plus material match. This is what lets **X1** outrank **Y** — X1 is near X in size and function; Y only shares a name.

For functional similarity, part descriptions are compared by **meaning** rather than words (embedding vectors), so "drive gear" and "transmission pinion" are recognised as similar functions even though they share no keywords.

## 4. Data constraint in the current demo

In the Cascadia demo database, part records have empty attribute fields — all specifications are embedded inside the part *name* string. Therefore a prerequisite step is to **parse the specifications out of the part names** into structured fields before Layers 1–3 can run. In a production PLM these attributes would already be populated; the parser compensates for the demo data only.

## 5. Revised pipeline

```
Required part  (structured spec, from the SysML model)
        │
        ▼
Retrieve candidates        ──  by function/type similarity (meaning-based),
                               broader than a name substring
        │
        ▼
Parse specs from names     ──  turn each candidate into structured fields
        │
        ▼
Compatibility gate (HARD)  ──  dimensional / interface tolerances
                               → truck-vs-bicycle-tire filter
        │
        ▼
Closeness ranking (SOFT)   ──  dimensional distance + functional similarity
                               + material  → X1 beats Y
        │
        ▼
Recommendation + rationale ──  best substitute, with trade-offs stated
```

## 6. What this requires

1. A **specification parser** for Cascadia part names (extract type, diameter, length, thread, material, …).
2. A small set of **compatibility tolerances** per part class (what counts as "fits"): e.g. bore diameter ±X %, exact thread match, load rating ≥ required.
3. A **closeness score** combining dimensional distance, functional similarity, and material.
4. Optional but recommended: **embedding-based retrieval** for functional similarity (available through the Ollama Cloud key).

## 7. Trade-offs and notes

- The dimensional gate makes results **defensible and explainable** (a part is rejected for a concrete reason), which is more useful for an engineer than a ranked list of name matches.
- Tolerances encode engineering judgement and should be reviewed with the domain expert; they are the main place where the system's "correctness" is decided.
- Embedding-based functional matching adds power (finds differently-named equivalents) at the cost of some setup and reproducibility; it can be added as a second phase after the dimensional gate is working.

---
*Prepared as a design note for discussion before implementation. The existing name-based pipeline and the agentic (tool-calling) variant remain available for comparison.*
