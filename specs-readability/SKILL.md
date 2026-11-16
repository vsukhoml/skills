---
name: specs-readability
description: >-
  Code readability, comment, and API documentation review for the SPECS suite,
  in any language, including governing-comment traceability. Use when
  reviewing changed source files or auditing the comments and docstrings of a
  codebase. Not for spec or design Markdown.
last_updated: 2026-11-15
---

# SPECS Readability & Documentation Review

Reviews implementation source files (and embedded docstrings / module READMEs)
for readability, high-signal comments, exact API contracts, plain international
English, and SPECS governing-comment traceability.

## Core Principles

1. **Clarity over cleverness:** Code is read far more often than written. Control
   flow and state transitions must be obvious without mentally simulating tricks.
2. **Codebase & glossary consistency:** Naming, formatting, and error idioms
   must match the surrounding repository, `ADR-0001`, and canonical domain terms
   in `GLOSSARY.md` / `GLOSSARY-MAP.md` — repository consistency and ubiquitous
   language outrank personal preference.
3. **Intent and invariants, never syntax:** Comments explain *why* a choice or
   constraint exists, physical units, byte offsets, or invariants — never what
   standard language syntax already says.
4. **High signal-to-noise:** Missing contracts create production bugs;
   play-by-play narration and multi-paragraph essays bury load-bearing warnings.
   Both are findings.
5. **Separate maintainer vs. caller scopes:** Inline comments serve engineers
   editing the implementation; public API docstrings state the exact
   caller/provider contract so callers never have to read the body.
6. **Literal, unambiguous English in comments & docstrings:** Write comments for
   busy engineers and non-native English readers: active component subjects +
   literal verbs (`rejects`, `persists`, `retries`, never `"handles"`), short
   sentences (`<= 25` words where practical), one term per concept, bounded
   numbers + units (`ms`, `KiB`, UTC) instead of vague praise (`"fast"`,
   `"lightweight"`, `"gracefully"`), and unambiguous modals (`must`, `must not`,
   `can`, `might`, `will`, `we expect` — never `should`, `may`, `could`, `would`,
   or opinion advice such as `we recommend` in contract guarantees).

## Workflow

### 1. Identify Targets

Inspect changed implementation files (`git diff --name-only` against the base
branch, or user-specified paths). Skip generated code; route standalone
`docs/**/*.md` specs, designs, and ADRs to `specs-grill` (if a module
`README.md` is in scope, also check it against the `specs` Document Quality &
Reviewability Standard).

### 2. Language-Aware Review

Consult repository linters, `ADR-0001`, and `GLOSSARY.md` / `GLOSSARY-MAP.md`
first, then check language idioms:

* **Go:** doc comments starting with the exported identifier name (`godoc`),
  explicit error wrapping, `context.Context` propagation, zero-value usability.
* **Python:** complete type annotations, PEP 257 / Sphinx-extractable docstrings,
  narrow exception handling, explicit resource lifetimes (`with`).
* **Rust:** `///` rustdoc with `# Errors` / `# Panics` / `# Safety` (for `unsafe`
  invariants), ownership clarity, narrow `unsafe` justification comments.
* **C/C++:** header contract comments (ownership, lifetime, alignment, thread
  safety, error return domain), bounds invariants.
* **Kotlin:** `KDoc` (`/** ... */`) on public classes/functions/properties,
  explicit nullability and immutability (`val`, read-only collections),
  structured coroutine/cancellation contracts (`suspend`, dispatcher safety),
  and sealed state/error modeling.
* **TypeScript/JS & Java:** `TSDoc` / JSDoc / Javadoc on exported types and
  methods, nullability/immutability guarantees, error/exception contracts.

### 3. Commenting & API Contract Standard

**Inline comments (maintainer scope):**

* **Placement & width:** Put comments on their own line **above** the statement
  (`<= 72`–`80` chars, indented with spaces matching surrounding code) rather
  than wide end-of-line trailing comments that wrap in side-by-side diffs or
  Google Docs snippets.
* **Required signal:**
  * Non-obvious invariants, lock ordering, memory/lifetime assumptions, or
    security boundaries (`INV-NNNN`).
  * Units, coordinate frames, endianness, byte offsets, and why a constant or
    timeout has its specific value.
  * Algorithms, protocol quirks, or performance trade-offs (1 to 3 sentences
    linking domain reason to code).

**Anti-patterns (flag these):**

* *Syntax echoing:* `i += 1  # increment i`, `// loop over users`. Delete on
  sight.
* *Narrative walls:* 15-line essays explaining tangled branching. Flag the code
  for extraction/refactoring into named helpers or a state table.
* *Vague/ambiguous contract words:* `"handles errors gracefully"`, `"should be
  thread-safe"`, `"fast lookup"`. Replace with exact behavior, locks/concurrency
  guarantees, and complexity/bounds.
* *Glossary drift:* Exported types, parameters, errors, or docstrings using
  `Avoid:` synonyms from `GLOSSARY.md` or overloading a domain noun (`account`,
  `transaction`) across bounded contexts.
* *Stale or contradictory comments:* A comment that disagrees with the code is a
  **blocking** defect.

```python
# BAD: syntax echo and vague modal/praise
def verify_age(age: int) -> bool:  # define age check
    # Should handle invalid ages gracefully.
    return age >= 21

# GOOD: answer-first contract, exact precondition, governing link
def verify_age(age_years: int) -> bool:
    """Return True if the buyer meets the 21-year statutory minimum.

    Caller must pass a non-negative integer in whole years; negative values
    raise ValueError.
    """
    # Governing: SPEC-0004, REQ-0002
    if age_years < 0:
        raise ValueError(f"age_years must be >= 0, got {age_years}")
    return age_years >= 21
```

**Public API documentation (consumer scope):**

* Every exported module, type, function, and method must have a structural
  docblock in the ecosystem's standard format (`godoc`, Sphinx/Google Python,
  rustdoc, Doxygen, `KDoc`, `TSDoc`/JSDoc, Javadoc).
* Start with a 1-sentence answer-first summary using a literal verb, then state
  **exact contracts**: caller preconditions, return guarantees, error/exception
  conditions, units, and concurrency/idempotency rules.
* Keep any embedded usage example inside a docstring minimal (`<= 15` lines,
  contract call only, spaces not `\t`, straight ASCII, `<= 72` chars/line).

### 4. Governing-Comment Traceability (SPECS Mandate)

In repositories using the SPECS traceability spine, every function or block
implementing a normative requirement must carry `// Governing: SPEC-XXXX,
REQ-YYYY` (using the language's comment syntax). Flag as **blocking** at the
exact `file:line`:

* Requirement-implementing code missing its governing comment.
* Governing comments citing a deleted ID or a requirement whose behavior no
  longer matches the code (drift).

### 5. Review Report Format

Order findings **blocking contract/traceability defects first, advisory
readability polish second**, deduplicating repeated patterns into one finding
with all `file:line` locations listed:

* **Blocking:** Stale/contradictory comments, missing or ambiguous (`should`,
  `may`, `could`, or `would`) public API contracts, missing/drifted governing
  comments, or opaque control flow hiding failure modes.
* **Advisory:** Syntax-echo cleanup, long-sentence tightening, or naming polish.
* Provide `file:line`, the one-sentence reason, and a concrete drop-in
  replacement (`<= 72` chars/line).
* End with an explicit verdict: either the prioritized findings list, or — when
  clean — **"`No action required: changes conform to the contract and
  readability standard.`"** Never end with silence.

## Review Checklist

| Verification item | Standard |
| --- | --- |
| Answer-first API contracts | Public interfaces state summary, caller preconditions, guarantees, units, and errors. |
| Unambiguous language | No `"handles"`, `"gracefully"`, `"fast"`, `"should"`, `"may"`, `"could"`, or `"would"` in contracts. |
| No syntax echoing | Inline comments state *why*, invariants, or units — never syntax narration. |
| Line-above placement & width | Comments and docstring examples sit above code and stay within 72–80 columns. |
| Comment freshness | Zero comments contradict current code paths. |
| Traceability | Requirement-implementing blocks carry accurate `Governing: SPEC-XXXX, REQ-YYYY` tags. |
| Codebase & glossary consistency | Idioms, docblock format, and domain names match `ADR-0001`, `GLOSSARY.md` (zero `Avoid:` synonyms), and project tooling. |
