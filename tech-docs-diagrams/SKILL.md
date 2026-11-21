---
name: tech-docs-diagrams
description: >-
  Decides when a technical diagram earns its space and creates, revises, or
  reviews source-backed diagrams (Mermaid and Graphviz DOT) in Markdown and
  Google Docs. Enforces cognitive-load limits, short ID-free labels with keyed
  details below, compact multiplicity, structured sub-elements, optional flat
  icons, and red-green-safe semantic color with non-color cues. Use when
  deciding whether to add a diagram, authoring or reviewing architecture,
  topology, state, or sequence diagrams in technical documents, or configuring
  editable diagrams in Google Docs. Don't use for numeric data charts or
  slide-only marketing visuals.
last_updated: 2026-11-20
---

# Diagrams from source code for technical documents

Optimize every diagram for human review, sound decisions, and low-effort updates
from text source. A diagram is a structured projection of a system model, not
decoration. Draw a diagram only when 2D spatial layout costs the reader less
effort than prose, a list, or a table. Keep the diagram source code synced with
the document.

Each rule below has a stable ID (D1 to D10). In `{skill_dir}`, the bundled lint
script checks measurable limits in Markdown, Mermaid, and Graphviz DOT files.
Apply the `writing-tech-docs` skill to all prose, lists, tables, and subsections
around a diagram.

## Workflow

Table 1 selects the steps for writing, revising, or reviewing diagrams.

Mode   | When                                      | Steps   | You deliver
------ | ----------------------------------------- | ------- | -----------
Write  | Drafting a new document or adding graphs. | 1 to 6  | Source-backed diagrams, keyed text, lint check.
Revise | Revising an existing draft or diagrams.   | 1 to 6  | Restructured diagrams, container fixes, summary.
Review | Auditing diagrams without modifying text. | 1 and 6 | Comments on key findings (D1 to D10).

*Table 1: Review mode reports key diagram defects without editing the file.*

Apply all rules (D1 to D10) and fix all findings when creating or revising a
document, or on diagrams touched during a narrow edit. On an existing document,
audit the visual structure of the whole draft instead of patching existing
diagrams alone. Replace unbacked pictures or ASCII art (D1), turn non-spatial
diagrams into lists or tables, and add diagrams where prose hides topology (D2).
Split mixed-zoom or crowded graphs into overview and child diagrams (D3, D4).

When commenting on another author's document, inspect all checks and report key
defects in visual fit, missing diagrams, boundaries, zoom, capacity, or roles.
Skip minor styling or label-length nits unless the user asks for a full audit.

1.  **Test spatial value:** Check Table 2 (D2). If a list or table conveys the
    facts with less reader effort than a 2D graph, omit or replace the diagram.
    On an existing draft, also check prose for buried topology or multi-actor
    flows that need a diagram.
2.  **Pick zoom and orientation:** Choose one abstraction level, one arrow
    meaning, and top-down flow (D3). Above 9 boxes or 12 arrows, plan one
    overview diagram and child diagrams (D4).
3.  **Write portable diagram code:** Draft plain `mermaid` or `dot` source (D1).
    Use 1-to-3-word ID-free labels (D5), compact `0..N` multiplicity (D7), and
    nested sub-boxes or vertical sub-lists (D8).
4.  **Encode categories cleanly:** Group roles or trust zones with shapes, 3 to
    5 red-green-safe pastel colors, and non-color cues (D10). Add flat icons
    only if shapes and colors leave roles ambiguous (D9).
5.  **Frame and key the details:** Add a lead-in sentence above and a 1-line
    italicized conclusion caption below (D6). Add a 1-line legend if styles
    vary, and put details past 5 words in a keyed block below.
6.  **Lint and publish:** Run `diagram_lint.py` and verify the 5 manual checks.
    Embed fenced code in Markdown or source-backed images in Google Docs (see
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

### Source and scope

-   **D1. Diagram from source code:** Author every diagram in text source. Use
    plain Mermaid (`flowchart` or `sequenceDiagram`) by default. Use
    `stateDiagram-v2` for state machines, or Graphviz DOT (`digraph`) when rank
    or edge weights need tight control. Never insert an unbacked screenshot or
    ASCII box art. Keep fenced blocks inline in Markdown, and sync or store
    source in Alt text in Google Docs (see
    [patterns and Google Docs setup](references/patterns_and_gdocs.md)).
-   **D2. Spatial value test:** Include a diagram only when 2D position,
    containment, branching, cycles, or lifelines replace sequential text search
    (Table 2). Replace linear chains and non-spatial taxonomies with lists or
    tables.
-   **D3. One zoom level and top-down flow:** Show one abstraction level per
    diagram, such as system context, containers, or internal modules. Never mix
    levels or edge meanings in one diagram. Use top-to-bottom (`TD` or `TB`)
    flow with at most 3 sibling boxes per rank so diagrams fit portrait pages
    (under 468 pt). Use horizontal `LR` flow only for unbranched chains of 3 or
    4 boxes.
-   **D4. Element, arrow, and crossing limits:** Cap each diagram at 5 to 9
    primary boxes (`<= 5` lifelines in a sequence diagram) and at most 12
    arrows. Keep edge crossings at zero or near zero. Start each arrow at the
    actor that starts the action. Above 9 boxes or 12 arrows, put one parent
    overview diagram in the parent section and child stage diagrams in nested
    subsections.

### Labels, multiplicity, and sub-elements

-   **D5. Short, ID-free canvas labels:** Label each box with a concrete noun
    phrase of 1 to 3 words (limit 5 words). Label each arrow with a verb and
    noun or payload of 1 to 3 words (limit 5 words). Avoid vague 1-word arrow
    labels such as "Data" or "Request". Short step numbers on ordered arrows
    (`1. Sign challenge`, `2. Verify key`) are permitted to index details below.
    Never put alphanumeric IDs (`REQ-04` or `INV-02`), function signatures, or
    sentences inside boxes or arrows.
-   **D6. Framed diagram and keyed details below:** Introduce every diagram with
    a complete sentence stating what projection it shows. Place a 1-line
    italicized conclusion caption directly below the diagram, and explain labels
    in body text for machine translation. Add a 1-line legend if arrow, border,
    or color styles vary. When boxes or arrows carry contracts beyond 5 words,
    place a keyed list, table, or subsection block below per
    `writing-tech-docs`. Omit that block if surrounding prose already states
    every fact.
-   **D7. Compact multiplicity without duplicate boxes:** Show when 0 to many
    instances of an element exist without drawing 3 or more identical parallel
    boxes. Mark multiplicity in the box title ("Workers (1..N)"), or use a
    multi-instance shape (`[["Workers (1..N)"]]` in Mermaid, `box3d` in DOT).
    Draw "Worker 1", `...`, and "Worker N" only when arrows route differently to
    specific instances.
-   **D8. Sub-elements inside a container box:** Never write comma-separated
    inline lists of sub-elements inside a box. If sub-elements have distinct
    arrows, draw them as separate nested sub-boxes (`subgraph` in Mermaid or
    `cluster_` in DOT). If sub-elements share all arrows of the parent box, list
    2 to 5 short titles vertically inside the box. Keep each title to 1 to 3
    words (limit 5). Join lines with `<br/>` and prefix items with "• " or `1. `
    in Mermaid. Above 5 sub-elements, split into a child diagram.

### Icons and color

-   **D9. Flat category icons:** Express element roles with built-in shapes
    (cylinders, stadiums, hexagons) and semantic color first (D10). Add flat,
    single-hue silhouette icons only when shapes and colors leave roles hard to
    separate. Cap a diagram at 5 icon categories, and always pair every icon
    with a text label. Omit `@{ icon: ... }` syntax and Unicode emoji from
    inline Markdown Mermaid blocks. That syntax fails in GitHub, GitLab, and
    many Markdown and CLI renderers.
-   **D10. Red-green-safe color and non-color cues:** Use 3 to 5 semantic pastel
    fills (plus neutral white or gray) to group trust levels, execution rings,
    or roles. Pick hues distinguishable under common red-green colorblindness
    (deuteranopia and protanopia, without filtering for rare tritanopia). Use
    teal-green (`#E0F2F1`) for trusted items and vermilion-red (`#FCE8E6`) for
    untrusted or error items. Use blue (`#E8F0FE`) or amber (`#FEF7E0`) for
    execution tiers. Use purple (`#F3E8FD`) for hardware or keys, always with
    dark `#202124` text (see the reference palette). Pair each color with a
    non-color cue, starting with an enclosing `subgraph` or a solid against
    dashed border. When categories interleave, add a distinct shape or a short
    `[HW]` or `[K]` prefix (or an icon per D9). State full category facts in the
    legend and keyed text below so color is never required.

## Markdown and Google Docs delivery

Table 3 summarizes how to keep diagrams editable from source in Markdown and in
Google Docs. Full rendering commands, Alt-text steps, and palettes live in
[patterns and Google Docs setup](references/patterns_and_gdocs.md).

Surface                         | Authoring and sync path                                        | Source storage
------------------------------- | -------------------------------------------------------------- | --------------
Markdown (GitHub, GitLab, docs) | Inline fenced `mermaid` or `dot` block in the `.md` file.      | `.md` file in VCS
Google Docs (CLI render)        | Render PNG with `mmdc` or `dot`, insert image, store Alt text. | VCS and Alt text
Google Docs (manual update)     | Copy source from Alt text, edit, re-render, and replace image. | Image Alt text

*Table 3: Never insert static diagram pictures without storing editable diagram
source.*

## Check before review

### Automated diagram lint

Run the bundled linter on Markdown, `.mmd`, or `.dot` files:

```bash
python3 {skill_dir}/scripts/diagram_lint.py draft.md
python3 {skill_dir}/scripts/diagram_lint.py diagram.mmd
```

The script checks ASCII box art and raster diagram images in Markdown (D1),
branched or wide `LR` flows (D3), and node or arrow counts (D4). It also checks
label length and alphanumeric IDs (D5), plus comma-separated or excess sub-items
and `- ` bullets (D8). In addition, it flags inline `@{ icon: ... }` or emoji
(D9) and checks palette limits and red-green pairs (D10). Wrap intentional
counterexamples between `<!-- diagram-lint: off -->` and
`<!-- diagram-lint: on -->`.

### Manual checks

Verify these 5 points after running `diagram_lint.py`:

1.  **Spatial value check (D2):** Confirm that each diagram shows boundaries,
    branching, cycles, or multi-actor timing rather than a linear list or
    attribute table. On an existing draft, confirm that you replaced non-spatial
    diagrams and added diagrams where prose hid 2D structure.
2.  **Crossing and zoom check (D3, D4):** Confirm one abstraction level, one
    arrow meaning, actor-started arrows, and zero avoidable crossings (splitting
    into overview and child diagrams if crowded).
3.  **Self-contained labels and keyed text (D5, D6):** Verify that boxes and
    arrows read without consulting prose, while extra contracts live in a keyed
    block below without repetition.
4.  **Multiplicity and container check (D7, D8):** Confirm no repeated parallel
    boxes for `0..N` instances, and confirm nested sub-boxes whenever inner
    sub-elements own distinct arrows.
5.  **Colorblind and text-only check (D9, D10):** Hide colors mentally and
    verify that boundaries, borders, shapes, `[TAG]` prefixes, legend, and keyed
    text preserve every category distinction.

## References

-   Read [patterns and Google Docs setup](references/patterns_and_gdocs.md) for
    local rendering commands, Google Docs Alt-text storage, Mermaid and DOT
    palettes, and worked examples.
