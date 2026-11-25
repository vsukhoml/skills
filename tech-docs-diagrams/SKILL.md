---
name: tech-docs-diagrams
description: >-
  Decides when a technical diagram earns its space and creates, revises,
  reviews, or triages source-backed diagrams (Mermaid and Graphviz DOT) in
  Markdown and Google Docs. Use when deciding whether to add a diagram,
  authoring, reviewing, or triaging comments on architecture, topology, state,
  or sequence diagrams in technical documents, or configuring editable diagrams
  in Google Docs. Don't use for numeric data charts or slide-only marketing
  visuals.
last_updated: 2026-11-24
---

# Diagrams from source code for technical documents

Optimize every diagram for human review, sound decisions, and low-effort updates
from text source. Draw a diagram only when 2D layout beats prose, a list, or a
table, and keep its source code synced with the document.

Each rule below has a stable ID (D1 to D11). In `{skill_dir}`, `diagram_lint.py`
checks measurable limits in Markdown, Mermaid, and Graphviz DOT files. Apply
`writing-tech-docs` to surrounding prose, lists, tables, and subsections, and
`tech-docs-comments` when posting or triaging inline review comments.

## Workflow

Table 1 selects the steps for writing, revising, reviewing, or triaging
diagrams.

Mode   | When                                                | Steps   | You deliver
------ | --------------------------------------------------- | ------- | -----------
Write  | Drafting a new document or adding diagrams.         | 1 to 6  | Source-backed diagrams, keyed text, lint check.
Revise | Updating diagrams in an existing draft.             | 1 to 6  | Updated diagrams in place and a change summary.
Review | Auditing diagrams without modifying files.          | 1 and 6 | Comments on key findings (D1 to D11).
Triage | Addressing others' comments on diagrams in a draft. | 1 to 6  | Updated diagram source/images and thread replies.

*Table 1: Review mode reports key diagram defects, while Triage mode updates
source-backed diagrams and replies per `tech-docs-comments`.*

Apply all rules (D1 to D11) and fix all findings in Write, Revise, and Triage.
On new documents or requested restructuring, audit the visual structure of the
whole draft. Replace unbacked pictures or ASCII art (D1), swap non-spatial
diagrams for lists or tables, and add diagrams where prose hides topology (D2).
Split crowded or mixed-zoom graphs into overview and child diagrams (D3, D4,
D11).

Without a restructuring request on an existing draft, apply D1 to D11 to added
or revised diagrams in place and note broader gaps. In Review mode on another
author's doc, report only key defects in visual fit, boundaries, zoom, capacity,
or roles, skipping minor nits.

1.  **Test spatial value and caption:** Check Table 2 (D2) and draft the 1-line
    takeaway caption first (D6), or use a list or table instead.
2.  **Pick zoom, spine, and splits:** Choose one zoom level and a top-down spine
    (D3), splitting large graphs into one parent overview and child diagrams
    (D4, D11).
3.  **Write portable diagram source:** Author plain `mermaid` or `dot` source
    following D1, D5, D7, and D8.
4.  **Encode categories:** Group roles with shapes, red-green-safe fills beside
    neutral context nodes, redundant cues, and optional flat icons (D9, D10).
5.  **Frame and key details:** Add the lead-in above, caption directly below,
    1-line legend if styles vary, and keyed contracts below (D6).
6.  **Lint and publish:** Run `diagram_lint.py`, verify the 5 manual checks, and
    embed fenced source or opaque-white Docs images (see
    [patterns and Google Docs setup](references/patterns_and_gdocs.md)).

## When to draw or skip a diagram

Table 2 separates structures where a diagram lowers reader effort from cases
where prose, lists, or tables work better (D2).

Content to communicate                          | Best container | Reason
----------------------------------------------- | -------------- | ------
Component or trust boundaries (`>= 3` units)    | Diagram        | Spatial containment shows perimeter crossings at once.
Branching flows, DAGs, or cyclic state machines | Diagram        | 2D paths avoid tracing nested conditional prose.
Multi-stage protection trees with chokepoints   | Diagram        | Converging paths expose shared bottlenecks visually.
Multi-actor timing or async protocols (`>= 3`)  | Diagram        | Lifelines align message order and timeouts.
Purely linear steps (`A -> B -> C`)             | Numbered list  | Boxes add vertical bulk without branching insight.
Two-component call or request-reply pair        | Prose or list  | One sentence states the contract in less space than 2 boxes.
Option comparisons or `if/then` attribute rules | 2D table       | Cells align attributes better than arrows.

*Table 2: Draw a diagram only when 2D topology or multi-actor timing beats
text.*

## Rules

### Source, layout, and decomposition

-   **D1. Diagram from source code:** Author every diagram in text source.
    Default to plain Mermaid (`flowchart` or `sequenceDiagram`). Cap
    `sequenceDiagram` control blocks (alt, opt, loop, par) at 1 nesting level,
    and draw activation bars on overlapping async calls. Use `stateDiagram-v2`
    for state machines (at most 1 composite superstate level for shared error or
    timeout exits), or Graphviz DOT (`digraph`) for rank control. Never insert
    unbacked screenshots or ASCII box art. Export images on an opaque white
    background for dark-mode readers.
-   **D2. Spatial value test:** Draw a diagram only when Table 2 selects one,
    using Lists or Tables for linear chains, 2-node pairs, and comparisons.
-   **D3. One zoom level and spine-aligned flow:** Show one abstraction level
    and one edge meaning per diagram. Default to top-to-bottom (`TD` or `TB`)
    flow with at most 3 sibling boxes per rank. Declare normal-case nodes first
    so the main path runs straight down the central spine. Route fallback
    branches sideways, and use upward back-edges only for dashed (`-.->`)
    retries or error replies. Allow horizontal `LR` flow only for branched
    pipelines of at most 3 ranks (`<= 2` boxes per rank) under 468 pt wide.
-   **D4. Element, degree, direction, and crossing limits:** Size each diagram
    at 3 to 9 boxes (`3` to `5` sequence lifelines) and at most 12 arrows. Cap
    single-node fan-out and fan-in at 4 arrows. Start each arrow at the
    initiating actor. Never use bidirectional (`<-->`) or undirected (`---`)
    edges in directed flows (draw 1 initiator arrow or 2 request and reply
    arrows). Keep edge crossings at zero, or cross at 70 to 90 degrees when 1 or
    2 crossings remain unavoidable. Above 9 boxes or 12 arrows, split into one
    parent overview and child stage diagrams (D11).
-   **D11. Parent-to-child integration and state-pair contrast:** Preserve each
    parent box title, fill, and `[TAG]` prefix in its child heading or
    `subgraph`. Draw callers or targets crossing that perimeter as neutral
    boundary stubs in the child diagram so boundary arrows match 1 to 1. In
    "current" against "proposed" pairs, freeze unchanged nodes in muted gray and
    color only changed components and edges.

### Labels, multiplicity, and sub-elements

-   **D5. Short, ID-free canvas labels:** Label each box with a concrete noun
    phrase of 1 to 3 words (limit 5 words). Label each arrow with a verb and
    noun or concrete payload of 1 to 3 words (limit 5 words). Never use vague
    1-word noun labels such as "Data", "Request", "Response", or "Payload", or
    bare step numbers without words. Short numbered verb phrases on ordered
    arrows (`1. Sign challenge`) are permitted to index details below. Never put
    alphanumeric IDs (`REQ-04` or `INV-02`), function signatures, or sentences
    on the canvas.
-   **D6. Framed diagram and keyed details below:** Draft the 1-line italicized
    takeaway caption first to bound the diagram (`<= 5` key relationships), and
    place it directly below the figure. Introduce the diagram above with a
    complete sentence stating what projection it shows, and add a 1-line legend
    if arrow, border, or color styles vary. Google Docs stores diagram code in
    image Alt text, so state all relationships in the prose, caption, and keyed
    block for screen readers. Format keyed details past 5 words as a list,
    table, or subsections per `writing-tech-docs`, omitting facts already clear
    on the canvas.
-   **D7. Compact multiplicity without duplicate boxes:** Show when 0 to many
    instances exist without drawing 3 or more identical parallel boxes. Mark
    multiplicity in the box title ("Workers (1..N)"), or use a multi-instance
    shape (`[["Workers (1..N)"]]` in Mermaid, `box3d` in DOT). Draw "Worker 1",
    `...`, and "Worker N" only when arrows route differently to specific
    instances.
-   **D8. Sub-elements and container depth:** Never write comma-separated inline
    lists inside a box. If sub-elements have distinct arrows, draw nested
    sub-boxes (`subgraph` in Mermaid or `cluster_` in DOT, capped at 2 nesting
    levels). When sub-elements share all parent arrows, stack 2 to 5 short
    titles with `<br/>` and "• " or `1. ` prefixes. Above 5 sub-elements, split
    into a child diagram.

### Icons and color

-   **D9. Flat category icons and graphic economy:** Express roles with shapes
    and semantic color first (D10). Cap distinct symbol classes across shapes,
    fills, and borders at 6 per diagram. Add flat, single-hue icons only when
    shapes and colors leave roles unclear (at most 5 icon categories, always
    labeled). Omit `@{ icon: ... }` syntax and Unicode emoji from inline
    Markdown Mermaid blocks, where GitHub, GitLab, and common Markdown renderers
    fail.
-   **D10. Red-green-safe color and redundant cues:** On multi-role flowcharts
    and graphs, use 1 to 4 semantic pastel fills (limit 5) beside neutral white
    or gray (`#F8F9FA`) context nodes. Zero fills are permitted when roles do
    not vary or in sequence and state diagrams. Never assign every box its own
    unique singleton color. Pick deuteranopia- and protanopia-safe fills with
    `#202124` text at `>= 4.5:1` contrast (see palette hexes in
    [patterns and Google Docs setup](references/patterns_and_gdocs.md)). Pair
    each color with a non-color cue encoding the **same** category redundantly.
    Prefer an enclosing `subgraph` first, border style or shape second, or a
    `[HW]` prefix (or icon per D9) when categories interleave. State full
    category facts in the legend and keyed text below.

## Markdown and Google Docs delivery

Table 3 summarizes source-backed delivery in Markdown and Google Docs (see
[patterns and Google Docs setup](references/patterns_and_gdocs.md) for CLI
commands and palettes).

Surface                         | Authoring and sync path                                        | Source storage
------------------------------- | -------------------------------------------------------------- | --------------
Markdown (GitHub, GitLab, docs) | Inline fenced `mermaid` or `dot` block in the `.md` file.      | `.md` file in VCS
Google Docs (CLI or sync)       | Render PNG with `mmdc` or `dot`, insert image, set Alt text.   | VCS and Alt text
Google Docs (in-place update)   | Copy source from Alt text, edit, re-render, and replace image. | Image Alt text

*Table 3: Never use cloud diagram add-ons on private docs or insert static
pictures without editable diagram source.*

## Check before review

### Automated diagram lint

Run the bundled linter on Markdown or diagram source files. Wrap intentional
counterexamples between `<!-- diagram-lint: off -->` and
`<!-- diagram-lint: on -->`:

```bash
python3 {skill_dir}/scripts/diagram_lint.py draft.md
python3 {skill_dir}/scripts/diagram_lint.py diagram.mmd
```

### Manual checks

Verify these 5 semantic checks after running `diagram_lint.py`:

1.  **Spatial value (D2):** The diagram shows boundaries, branching, cycles, or
    multi-actor timing rather than a linear list or attribute table.
2.  **Spine and integration (D3, D4, D11):** One zoom level, one arrow meaning,
    a straight normal-case spine, zero avoidable crossings, and matching titles
    and boundary stubs across parent and child diagrams.
3.  **Self-contained labels and accessible text (D5, D6):** Canvas labels read
    without prose, while prose, caption, and keyed details state every
    relationship without repeating obvious canvas facts.
4.  **Multiplicity and containers (D7, D8):** `0..N` pools avoid repeated
    parallel boxes, and inner sub-elements with distinct arrows use nested
    sub-boxes.
5.  **Redundant coding (D9, D10):** Hiding colors mentally leaves every category
    distinguishable via `<= 6` symbol classes, boundaries, borders, shapes,
    `[TAG]` prefixes, legend, and keyed text.
